"""Bounded resilience primitives for the scraper runtime.

The scraper runner is intentionally fail-closed: an empty result is not a
healthy scrape, terminal HTTP/auth failures are not retried, and a source
cannot make another source wait behind its circuit breaker.  The functions in
this module are synchronous because they are also used by the legacy runner;
the actual network clients remain responsible for closing their own sessions.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from utils.production_safeguards import CircuitBreaker, ProductionError

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_BLOCKED = "blocked"
STATUS_BLOCKED_CREDENTIALS = "blocked_credentials"
STATUS_TIMEOUT = "timeout"
STATUS_DEGRADED = "degraded"
STATUS_FAILED = "failed"

TERMINAL_STATUSES = frozenset({
    STATUS_BLOCKED,
    STATUS_BLOCKED_CREDENTIALS,
    STATUS_DEGRADED,
})


@dataclass(frozen=True)
class SourceRuntimePolicy:
    """Small, source-local execution budget."""

    timeout_seconds: float = 12.0
    max_attempts: int = 2
    retry_backoff_seconds: float = 0.10
    max_retry_backoff_seconds: float = 0.40
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0

    @property
    def timeout(self) -> float:
        return self.timeout_seconds


RUNTIME_POLICIES: Dict[str, SourceRuntimePolicy] = {
    "leilosoc": SourceRuntimePolicy(timeout_seconds=8.0, max_attempts=2),
    "autoscout24": SourceRuntimePolicy(timeout_seconds=10.0, max_attempts=2),
    "autohub": SourceRuntimePolicy(timeout_seconds=10.0, max_attempts=2),
}
DEFAULT_RUNTIME_POLICY = SourceRuntimePolicy()


def runtime_policy_for(name: str) -> SourceRuntimePolicy:
    """Return a policy for a source name (case-insensitive)."""
    key = str(name).lower()
    if key in RUNTIME_POLICIES:
        return RUNTIME_POLICIES[key]
    for source_name, policy in RUNTIME_POLICIES.items():
        if source_name in key:
            return policy
    return DEFAULT_RUNTIME_POLICY


class ScraperRuntimeError(ProductionError):
    """Typed, non-data error used to retain the operational source state."""

    def __init__(
        self,
        message: str,
        *,
        status: str = STATUS_FAILED,
        retryable: bool = False,
        source: Optional[str] = None,
    ) -> None:
        super().__init__(message, context={"status": status, "source": source})
        self.status = status
        self.retryable = retryable
        self.source = source


class SourceBlocked(ScraperRuntimeError):
    def __init__(self, message: str, *, source: Optional[str] = None) -> None:
        super().__init__(message, status=STATUS_BLOCKED, source=source)


class SourceCredentialsBlocked(ScraperRuntimeError):
    def __init__(self, message: str, *, source: Optional[str] = None) -> None:
        super().__init__(message, status=STATUS_BLOCKED_CREDENTIALS, source=source)


class SourceTimeout(ScraperRuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        source: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            status=STATUS_TIMEOUT,
            retryable=retryable,
            source=source,
        )


def status_for_http(status_code: int) -> Tuple[str, bool]:
    """Map an HTTP response to ``(state, retryable)`` without sleeping."""
    if status_code in (401, 407):
        return STATUS_BLOCKED_CREDENTIALS, False
    if status_code in (403, 429):
        return STATUS_BLOCKED, False
    if status_code == 404:
        return STATUS_DEGRADED, False
    if status_code in (408, 504):
        return STATUS_TIMEOUT, True
    if 500 <= status_code <= 599:
        return STATUS_FAILED, True
    return STATUS_FAILED, False


# Cache de último recurso (fallback em disco) por fonte.
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "scrape_cache"
_CACHE_TTL_SECONDS = 24 * 3600


def _cache_path(key: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
    return _CACHE_DIR / f"{safe}.json"


def _load_cache(key: str) -> Optional[list]:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - data.get("ts", 0) > _CACHE_TTL_SECONDS:
            return None
        listings = data.get("listings", [])
        return listings if isinstance(listings, list) else None
    except Exception as exc:  # noqa: BLE001 - cache is optional
        logger.warning("Falha ao ler cache %s: %s", key, exc)
        return None


def _save_cache(key: str, listings: list) -> None:
    try:
        _cache_path(key).write_text(
            json.dumps({"ts": time.time(), "listings": listings}, default=str),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - cache is optional
        logger.warning("Não gravou cache %s: %s", key, exc)


def _is_dns_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(token in text for token in (
        "getaddrinfo",
        "name or service not known",
        "temporary failure in name resolution",
        "failed to resolve",
        "nodename nor servname",
        "dns",
    ))


def _exception_state(exc: BaseException) -> Tuple[str, bool]:
    """Classify an exception without turning an unknown failure into data."""
    explicit = getattr(exc, "status", None)
    retryable = bool(getattr(exc, "retryable", False))
    if explicit:
        return str(explicit), retryable

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_for_http(status_code)

    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if any(token in text or token in name for token in (
        "credential_missing",
        "api_key",
        "authentication",
        "unauthorized",
    )):
        return STATUS_BLOCKED_CREDENTIALS, False
    if "forbidden" in text or "captcha" in text or "cloudflare" in text:
        return STATUS_BLOCKED, False
    if "timeout" in text or "timed out" in text or "timeout" in name:
        return STATUS_TIMEOUT, True
    if _is_dns_error(exc):
        return STATUS_FAILED, False
    if "connectionerror" in name or "connection reset" in text:
        return STATUS_FAILED, True
    if "server error" in text or "503" in text or "502" in text:
        return STATUS_FAILED, True
    return STATUS_FAILED, False


def _close_sync_object(obj: Any) -> None:
    """Best-effort close for a timed-out synchronous scraper target."""
    close = getattr(obj, "close", None)
    if not callable(close):
        return
    try:
        result = close()
        # Async close methods are owned by the async audit wrappers.
        if inspect.isawaitable(result):
            close_coroutine = getattr(result, "close", None)
            if callable(close_coroutine):
                close_coroutine()
    except Exception as exc:  # noqa: BLE001 - cleanup must not mask timeout
        logger.debug("Falha no cleanup de timeout: %s", exc)


def _close_callable_resources(func: Callable[[], list]) -> None:
    """Close bound/closure scraper resources after a hard timeout."""
    candidates: List[Any] = []
    target = getattr(func, "__self__", None)
    if target is not None:
        candidates.append(target)
    for cell in getattr(func, "__closure__", ()) or ():
        try:
            value = cell.cell_contents
        except ValueError:
            continue
        if hasattr(value, "session") or hasattr(value, "_session"):
            candidates.append(value)
    seen: set[int] = set()
    for obj in candidates:
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        _close_sync_object(obj)


def _call_with_timeout(
    func: Callable[[], list],
    timeout_seconds: float,
    *,
    source: str,
) -> list:
    """Run a sync callable with a hard return budget.

    Python cannot safely kill a running thread.  The worker is daemonised,
    source-owned sessions are closed on timeout, and network adapters also
    have request-level timeouts.  A cancelled socket is never treated as data.
    """
    if timeout_seconds <= 0:
        raise SourceTimeout(f"{source}: timeout budget exhausted", source=source)

    result_queue: "queue.Queue[Tuple[str, Any]]" = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            value = func()
            if inspect.isawaitable(value):
                value = asyncio.run(value)
            result_queue.put_nowait(("ok", value))
        except BaseException as exc:  # propagate the original typed error
            try:
                result_queue.put_nowait(("error", exc))
            except queue.Full:
                pass

    thread = threading.Thread(
        target=worker,
        name=f"scraper-{source}-bounded",
        daemon=True,
    )
    thread.start()
    try:
        kind, value = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        _close_callable_resources(func)
        raise SourceTimeout(
            f"{source}: execution exceeded {timeout_seconds:.2f}s",
            source=source,
        ) from exc
    if kind == "error":
        raise value
    return value if isinstance(value, list) else list(value or [])


def _callable_status(func: Callable[[], list]) -> Optional[str]:
    status = getattr(func, "last_status", None)
    if status:
        return str(status)
    target = getattr(func, "__self__", None)
    status = getattr(target, "last_status", None)
    return str(status) if status else None


def _cap_breaker_recovery(breaker: CircuitBreaker, policy: SourceRuntimePolicy) -> CircuitBreaker:
    # Existing callers pass a 300-second breaker.  It is not a sleep, but a
    # source-local bounded probe should not inherit a multi-minute recovery.
    try:
        breaker.recovery_timeout = min(
            float(breaker.recovery_timeout),
            max(0.1, float(policy.recovery_timeout_seconds)),
        )
    except (AttributeError, TypeError, ValueError):
        pass
    return breaker


def _new_breaker(policy: SourceRuntimePolicy) -> CircuitBreaker:
    return CircuitBreaker(
        failure_threshold=max(1, int(policy.failure_threshold)),
        recovery_timeout=max(0.1, float(policy.recovery_timeout_seconds)),
    )


def _attempt(
    func: Callable[[], list],
    breaker: CircuitBreaker,
    policy: Optional[SourceRuntimePolicy] = None,
    *,
    source: str = "source",
) -> list:
    """Execute one source with bounded retry and a source-local breaker."""
    effective = policy or DEFAULT_RUNTIME_POLICY
    _cap_breaker_recovery(breaker, effective)
    max_attempts = max(1, int(effective.max_attempts))
    last_error: Optional[BaseException] = None

    for attempt_number in range(1, max_attempts + 1):
        if not breaker.can_attempt():
            raise ScraperRuntimeError(
                f"{source}: circuit open",
                status=STATUS_BLOCKED,
                source=source,
            )
        try:
            result = _call_with_timeout(
                func,
                float(effective.timeout_seconds),
                source=source,
            )
            if result:
                breaker.record_success()
                return result
            # Empty is explicit and is never retried as a network failure.
            breaker.record_failure()
            return []
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            last_error = exc
            status, retryable = _exception_state(exc)
            breaker.record_failure()
            if (
                not retryable
                or attempt_number >= max_attempts
                or not breaker.can_attempt()
            ):
                raise
            delay = min(
                float(effective.max_retry_backoff_seconds),
                float(effective.retry_backoff_seconds)
                * (2 ** (attempt_number - 1)),
            )
            if delay > 0:
                time.sleep(delay)
            logger.debug(
                "[%s] retry %d/%d after %s (%s)",
                source,
                attempt_number,
                max_attempts,
                type(exc).__name__,
                status,
            )

    if last_error is not None:
        raise last_error
    return []


def _outcome_status(func: Callable[[], list], listings: list) -> str:
    status = _callable_status(func)
    if status:
        return status
    return STATUS_OK if listings else STATUS_EMPTY


class FallbackChain:
    """Try independent sources without sharing failure state between them."""

    def __init__(
        self,
        sources: List[tuple[str, Callable[[], list]]],
        cache_key: str,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.sources = sources
        self.cache_key = cache_key
        self._provided_breaker = circuit_breaker
        self.breakers: Dict[str, CircuitBreaker] = {}
        self.breaker = circuit_breaker  # backwards-compatible inspection hook
        self.failed: List[str] = []
        self.used_source: Optional[str] = None
        self.from_cache = False
        self.statuses: Dict[str, str] = {}
        self.errors: Dict[str, str] = {}
        self.status = STATUS_EMPTY

    def _breaker_for(self, name: str, policy: SourceRuntimePolicy) -> CircuitBreaker:
        if name in self.breakers:
            return self.breakers[name]
        if not self.breakers and self._provided_breaker is not None:
            breaker = self._provided_breaker
        else:
            breaker = _new_breaker(policy)
        self.breakers[name] = _cap_breaker_recovery(breaker, policy)
        if self.breaker is None:
            self.breaker = self.breakers[name]
        return self.breakers[name]

    def run(self) -> list:
        for name, func in self.sources:
            policy = runtime_policy_for(name)
            breaker = self._breaker_for(name, policy)
            try:
                listings = _attempt(func, breaker, policy, source=name)
                status = _outcome_status(func, listings)
                self.statuses[name] = status
                if listings and status not in TERMINAL_STATUSES and status != STATUS_TIMEOUT:
                    logger.info("FallbackChain: fonte '%s' OK (%d itens)", name, len(listings))
                    self.used_source = name
                    self.status = STATUS_OK
                    _save_cache(self.cache_key, listings)
                    return listings
                self.failed.append(name)
                self.errors[name] = status
                logger.warning("FallbackChain: '%s' terminou em %s", name, status)
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                status, _ = _exception_state(exc)
                self.statuses[name] = status
                self.errors[name] = str(exc)
                self.failed.append(name)
                logger.warning("FallbackChain: '%s' falhou (%s): %s", name, status, exc)

        cached = _load_cache(self.cache_key)
        if cached:
            logger.warning(
                "FallbackChain: a usar CACHE para '%s' (%d itens)",
                self.cache_key,
                len(cached),
            )
            self.from_cache = True
            self.used_source = "cache"
            self.status = STATUS_DEGRADED
            return cached

        self.status = STATUS_EMPTY if self.failed else STATUS_FAILED
        logger.error("FallbackChain: todas as fontes falharam (%s)", self.failed)
        return []


def scrape_with_resilience(
    name: str,
    func: Callable[[], list],
    breaker: Optional[CircuitBreaker] = None,
    *,
    policy: Optional[SourceRuntimePolicy] = None,
    return_status: bool = False,
) -> tuple[list, bool] | tuple[list, bool, str]:
    """Run one source and preserve its state without fabricating rows."""
    effective = policy or runtime_policy_for(name)
    br = _cap_breaker_recovery(breaker or _new_breaker(effective), effective)
    try:
        listings = _attempt(func, br, effective, source=name)
        status = _outcome_status(func, listings)
        success = bool(listings) and status not in TERMINAL_STATUSES and status != STATUS_TIMEOUT
        if not listings and status == STATUS_OK:
            status = STATUS_EMPTY
        value: tuple[list, bool, str] = (listings, success, status)
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        status, _ = _exception_state(exc)
        logger.error("scrape_with_resilience('%s') [%s] falhou: %s", name, status, exc)
        value = ([], False, status)
    return value if return_status else value[:2]
