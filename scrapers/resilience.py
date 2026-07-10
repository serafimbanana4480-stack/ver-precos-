"""
VER PRECOS — Resiliência de Scrapers: Retry + Circuit Breaker + Fallback Chain
===========================================================================
Fornece:
  1. `scrape_with_resilience()` — aplica retry (tenacity) + circuit breaker
     (utils.production_safeguards.CircuitBreaker) a qualquer scraper.
  2. `FallbackChain` — tenta scrapers por ordem; se um falha (exceção OU
     lista vazia), usa o próximo; em último caso devolve cache em disco.

Isto fecha as falhas identificadas em parallel_runner.py e scrapers/* que
NÃO usavam nem retry_network nem CircuitBreaker (ambos já existiam).

Uso típico (ver parallel_runner.py para integração):
    from scrapers.resilience import FallbackChain, scrape_with_resilience
    chain = FallbackChain([
        ("olx", lambda: OLXScraper().scrape_listings("carros", max_listings=50)),
        ("standvirtual", lambda: StandvirtualScraper().scrape_listings(...)),
    ], cache_key="carros_olx")
    listings = chain.run()
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable, List, Optional

from utils.retry import retry_network
from utils.production_safeguards import CircuitBreaker, ProductionError

logger = logging.getLogger(__name__)

# Cache de último recurso (fallback em disco) por fonte
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "scrape_cache"
_CACHE_TTL_SECONDS = 24 * 3600  # 1 dia


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
        ts = data.get("ts", 0)
        if time.time() - ts > _CACHE_TTL_SECONDS:
            return None
        return data.get("listings", [])
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao ler cache %s: %s", key, e)
        return None


def _save_cache(key: str, listings: list) -> None:
    try:
        _cache_path(key).write_text(
            json.dumps({"ts": time.time(), "listings": listings}, default=str),
            encoding="utf-8",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Não gravou cache %s: %s", key, e)


@retry_network(max_attempts=3, min_wait=2, max_wait=15)
def _attempt(func: Callable[[], list], breaker: CircuitBreaker) -> list:
    """Executa func com circuit breaker. Lança se circuito aberto ou erro."""
    if not breaker.can_attempt():
        if not breaker.allow_transient_bypass():
            logger.error("Circuit breaker ABERTO — a ignorar fonte.")
            raise ProductionError("circuit open")
    try:
        result = func()
        breaker.record_success()
        return result or []
    except Exception as e:  # noqa: BLE001
        breaker.record_failure()
        raise


class FallbackChain:
    """
    Cadeia de fallback para scrapers.

    Tenta cada fonte (callable) por ordem. Se uma levanta exceção ou
    devolve lista vazia, passa à seguinte. Se todas falharem, devolve o
    cache em disco (se existir e for recente). Sempre devolve uma lista
    (vazia em último caso), NUNCA levanta.
    """

    def __init__(
        self,
        sources: List[tuple[str, Callable[[], list]]],
        cache_key: str,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.sources = sources
        self.cache_key = cache_key
        # Um circuit breaker partilhado por toda a cadeia (ou um novo)
        self.breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=300
        )
        self.failed: List[str] = []
        self.used_source: Optional[str] = None
        self.from_cache = False

    def run(self) -> list:
        for name, fn in self.sources:
            try:
                listings = _attempt(fn, self.breaker)
                if listings:
                    logger.info("FallbackChain: fonte '%s' OK (%d itens)", name, len(listings))
                    self.used_source = name
                    _save_cache(self.cache_key, listings)
                    return listings
                else:
                    logger.warning("FallbackChain: '%s' devolveu 0 itens", name)
                    self.failed.append(name)
            except Exception as e:  # noqa: BLE001
                logger.warning("FallbackChain: '%s' falhou: %s", name, e)
                self.failed.append(name)

        # Todas as fontes falharam → tenta cache
        cached = _load_cache(self.cache_key)
        if cached:
            logger.warning(
                "FallbackChain: a usar CACHE para '%s' (%d itens)",
                self.cache_key, len(cached),
            )
            self.from_cache = True
            self.used_source = "cache"
            return cached

        logger.error("FallbackChain: todas as fontes falharam (%s)", self.failed)
        return []


def scrape_with_resilience(
    name: str, func: Callable[[], list], breaker: Optional[CircuitBreaker] = None
) -> tuple[list, bool]:
    """
    Scrape único com retry + circuit breaker.

    Devolve (listings, sucesso). Nunca levanta.
    """
    br = breaker or CircuitBreaker(failure_threshold=3, recovery_timeout=300)
    try:
        listings = _attempt(func, br)
        return listings, bool(listings)
    except Exception as e:  # noqa: BLE001
        logger.error("scrape_with_resilience('%s') falhou: %s", name, e)
        return [], False
