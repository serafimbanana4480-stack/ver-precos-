"""Playwright stealth helper (playwright-stealth 1.x and 2.x compatible)."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

_stealth_instance: Any = None


def _get_stealth() -> Any:
    global _stealth_instance
    if _stealth_instance is None:
        try:
            from playwright_stealth import Stealth
            _stealth_instance = Stealth()
        except Exception as exc:
            logger.debug("playwright_stealth Stealth unavailable: %s", exc)
            _stealth_instance = None
    return _stealth_instance


async def apply_stealth_async(page: Any) -> None:
    """Apply anti-detection scripts to a Playwright page."""
    try:
        from playwright_stealth import stealth_async  # type: ignore[attr-defined]
        await stealth_async(page)
        return
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("stealth_async unavailable: %s", exc)
    try:
        stealth = _get_stealth()
        if stealth is not None:
            await stealth.apply_stealth_async(page)
        else:
            logger.debug("playwright_stealth not available, skipping stealth")
    except Exception as exc:
        logger.warning("Could not apply playwright stealth: %s", exc)
