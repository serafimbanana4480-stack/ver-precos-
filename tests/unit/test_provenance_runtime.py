"""Focused offline regression tests for source and ingestion provenance."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, PriceHistory, ScrapingLog, Source, Vehicle
from scripts.verify_source_integrity import audit_source_rows
from utils.source_normalize import normalize_source, source_from_url


def _fake_database_context(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()

    @contextmanager
    def fake_context():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    monkeypatch.setattr("database.db.get_db_context", fake_context)
    return session


def _valid_listing(**overrides):
    listing = {
        "source_id": "provenance-runtime-1",
        "url": "https://www.olx.pt/d/anuncio/provenance-runtime-1",
        "brand": "Volkswagen",
        "model": "Golf",
        "year": 2020,
        "km": 50_000,
        "price": 15_000,
        "price_kind": "total",
        "currency": "EUR",
        "title": "Volkswagen Golf 2020",
        "vehicle_type": "carros",
        "fuel_type": "gasolina",
        "transmission": "manual",
    }
    listing.update(overrides)
    return listing


def test_source_aliases_are_canonical_and_unknown_hosts_do_not_default_to_olx():
    assert normalize_source("auto_uncle") == "AUTOUNCLE"
    assert normalize_source("auto-uncle.pt") == "AUTOUNCLE_PT"
    assert normalize_source("AUTOPT", "https://www.autouncle.pt/ad/1") == "AUTOUNCLE"
    assert normalize_source(None) == "UNKNOWN"
    assert normalize_source(None, "https://unknown.example/ad/1") == "UNKNOWN"
    assert normalize_source("", "https://unknown.example/ad/1") == "UNKNOWN"
    assert source_from_url("https://www.olx.pt.evil.example/ad/1") is None


def test_source_integrity_audit_reports_unverifiable_unknown_hosts():
    report = audit_source_rows([
        {"source": "OLX", "url": "https://unknown.example/ad/1"},
    ])

    assert report["status"] == "unhealthy"
    assert report["unknown_hosts"] == 1
    assert report["by_pair"] == {"OLX->UNKNOWN": 1}


def test_ingestion_advances_last_seen_and_history_only_for_valid_price_observations(monkeypatch):
    session = _fake_database_context(monkeypatch)
    from scrapers.parallel_runner import save_to_database

    first = _valid_listing()
    assert save_to_database([first], "olx") == 1
    row = session.query(Vehicle).one()
    assert row.source is Source.OLX
    assert row.price == 15_000
    assert row.price_kind == "total"
    assert session.query(PriceHistory).count() == 1

    # SQLite returns DateTime values without tzinfo even when the ORM receives
    # UTC-aware values; use the same representation for an unambiguous check.
    old_seen = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
    row.last_seen = old_seen
    session.commit()

    unchanged = _valid_listing()
    assert save_to_database([unchanged], "olx") == 1
    session.expire_all()
    row = session.query(Vehicle).one()
    unchanged_seen = row.last_seen
    assert unchanged_seen > old_seen
    assert session.query(PriceHistory).count() == 1

    invalid = _valid_listing(price=None)
    before_invalid_seen = row.last_seen
    before_invalid_price = row.price
    assert save_to_database([invalid], "olx") == 0
    session.expire_all()
    row = session.query(Vehicle).one()
    assert row.last_seen == before_invalid_seen
    assert row.price == before_invalid_price
    assert session.query(PriceHistory).count() == 1

    changed = _valid_listing(price=16_500)
    assert save_to_database([changed], "olx") == 1
    session.expire_all()
    row = session.query(Vehicle).one()
    assert row.price == 16_500
    assert row.last_seen > before_invalid_seen
    assert session.query(PriceHistory).count() == 2
    assert session.query(PriceHistory).order_by(PriceHistory.id).all()[-1].price == 16_500


def test_invalid_new_observation_does_not_create_zero_price_or_history(monkeypatch):
    session = _fake_database_context(monkeypatch)
    from scrapers.parallel_runner import save_to_database

    invalid = _valid_listing(source_id="provenance-runtime-invalid", price=None)
    assert save_to_database([invalid], "olx") == 0
    assert session.query(Vehicle).count() == 0
    assert session.query(PriceHistory).count() == 0


def test_scraping_run_log_is_durable_and_canonical(monkeypatch):
    session = _fake_database_context(monkeypatch)
    from scrapers.parallel_runner import ScrapingResult, _record_scraping_log

    result = ScrapingResult(
        scraper_name="legacy-olx",
        source="OLX",
        listings=[_valid_listing()],
        success=True,
        persisted=1,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        duration=1.0,
    )

    assert _record_scraping_log(result) is True
    log = session.query(ScrapingLog).one()
    assert log.source is Source.OLX
    assert log.status == "completed"
    assert log.listings_found == 1
    assert log.listings_added == 1
    assert log.finished_at is not None
    assert result.log_recorded is True
