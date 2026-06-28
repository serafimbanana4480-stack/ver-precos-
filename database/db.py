"""
Database connection and session management
"""
from __future__ import annotations
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from contextlib import contextmanager
from utils.retry import retry_database
from typing import Generator
import logging
from core.settings import settings
import sys

# Configure logging
_log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
_log_format = settings.log_format

if _log_format.lower() == "json":
    try:
        from pythonjsonlogger import jsonlogger
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(jsonlogger.JsonFormatter())
        logging.basicConfig(level=_log_level, handlers=[_handler])
    except ImportError:
        _log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logging.basicConfig(level=_log_level, format=_log_format)
else:
    if "asctime" not in _log_format and "%" in _log_format:
        _log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=_log_level,
        format=_log_format,
        handlers=[
            logging.FileHandler(settings.log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
logger = logging.getLogger(__name__)

# SQLite needs WAL mode + no connection pool to avoid "database is locked"
_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        settings.resolved_db_url,
        poolclass=NullPool,
        connect_args={"check_same_thread": False, "timeout": 15},
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA busy_timeout=15000")
else:
    engine = create_engine(
        settings.resolved_db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_db_initialized = False


def init_db() -> None:
    """Initialize database tables once."""
    global _db_initialized
    if _db_initialized:
        return
    
    from .models import Base
    from pathlib import Path
    from sqlalchemy import inspect
    
    # Check if tables exist first
    inspector = inspect(engine)
    if inspector.has_table("vehicles"):
        _db_initialized = True
        logger.info("Database already initialized")
        return
    
    try:
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config(Path(__file__).parent.parent / "alembic.ini")
        command.upgrade(alembic_cfg, "head")
        _db_initialized = True
        logger.info("Database schema up to date via Alembic migration")
        return
    except Exception as alembic_err:
        logger.warning(f"Alembic migration failed, falling back to create_all: {alembic_err}")
    
    try:
        import sqlalchemy as sa
        if not inspector.has_table("vehicles"):
            Base.metadata.create_all(bind=engine)
        _db_initialized = True
        logger.info("Database tables created via create_all (fallback)")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database sessions
    Use with FastAPI: Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions
    Usage:
        with get_db_context() as db:
            # do something with db
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


@retry_database(max_attempts=3, min_wait=2, max_wait=10)  # type: ignore[misc]
def health_check() -> bool:
    """Check if database connection is healthy"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
    print("Database initialized successfully!")
