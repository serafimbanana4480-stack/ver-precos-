"""
Scraping log utility — inserts entries into scraping_logs table.
All scrapers should call this to record activity.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def log_scrape_result(
    source: str,
    status: str,
    listings_found: int = 0,
    listings_added: int = 0,
    listings_updated: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """Insert a scraping log entry into the database.

    Args:
        source: Source name (e.g. 'AUTOPT', 'LEILOSOC', 'OLX')
        status: 'running', 'completed', or 'failed'
        listings_found: Total listings found in scrape
        listings_added: New listings added
        listings_updated: Existing listings updated
        error_message: Error message if failed
    """
    try:
        from database.db import get_db_context
        from database.models import ScrapingLog

        with get_db_context() as db:
            log = ScrapingLog(
                source=source.upper(),
                status=status,
                listings_found=listings_found,
                listings_added=listings_added,
                listings_updated=listings_updated,
                error_message=error_message,
                finished_at=datetime.now(timezone.utc) if status != "running" else None,
            )
            db.add(log)
            db.commit()
            logger.debug(f"[LOG] Scrape log inserted: {source} / {status}")
    except Exception as e:
        logger.warning(f"[LOG] Failed to insert scraping log: {e}")


def start_scrape_log(source: str) -> Optional[int]:
    """Create a 'running' log entry and return its ID.

    Args:
        source: Source name (e.g. 'AUTOPT')

    Returns:
        Log ID if successful, None otherwise
    """
    try:
        from database.db import get_db_context
        from database.models import ScrapingLog

        with get_db_context() as db:
            log = ScrapingLog(
                source=source.upper(),
                status="running",
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            logger.debug(f"[LOG] Started scrape log for {source}, id={log.id}")
            return log.id  # type: ignore[return-value]
    except Exception as e:
        logger.warning(f"[LOG] Failed to start scrape log: {e}")
        return None


def finish_scrape_log(
    log_id: int,
    status: str = "completed",
    listings_found: int = 0,
    listings_added: int = 0,
    listings_updated: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """Update a scrape log entry with completion data.

    Args:
        log_id: Log entry ID from start_scrape_log
        status: 'completed' or 'failed'
        listings_found: Total listings found
        listings_added: New listings added
        listings_updated: Existing listings updated
        error_message: Error message if failed
    """
    try:
        from database.db import get_db_context
        from database.models import ScrapingLog

        with get_db_context() as db:
            log = db.query(ScrapingLog).filter(ScrapingLog.id == log_id).first()
            if log:
                log.status = status  # type: ignore[assignment]
                log.finished_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                log.listings_found = listings_found  # type: ignore[assignment]
                log.listings_added = listings_added  # type: ignore[assignment]
                log.listings_updated = listings_updated  # type: ignore[assignment]
                log.error_message = error_message  # type: ignore[assignment]
                db.commit()
                logger.debug(f"[LOG] Finished scrape log {log_id}: {status}")
    except Exception as e:
        logger.warning(f"[LOG] Failed to finish scrape log: {e}")
