from contextlib import contextmanager
import gzip
import sqlite3
import tempfile
from pathlib import Path

import pytest

from valuation.comparables import MarketEstimate
from valuation.listing_guard import ListingFlags
from valuation.opportunity import classify
from valuation.reliability import assess
from valuation.service import (
    VALUATION_VERSION,
    VehicleValuation,
    _default_net_profit,
)


def _estimate(*, value=15_000.0, low=14_000.0, n=25):
    return MarketEstimate(
        value=value,
        low=low,
        high=value + 1_000,
        status="ok",
        method="test",
        level=1,
        comparables_used=n,
        comparables_rejected=0,
        mean_similarity=0.8,
        dispersion_pct=8.0,
        confidence=0.8,
        confidence_label="alta",
        explanation="test",
    )


def test_default_net_profit_subtracts_asking_price_once():
    from valuation.pt_fiscal import calculate_selling_costs, calculate_transaction_costs

    vehicle = {
        "price": 10_000,
        "year": 2020,
        "engine_size": 1600,
        "fuel_type": "diesel",
        "vehicle_type": "carros",
        "is_national": True,
        "condition_score": 8.5,
    }
    estimate = _estimate(value=15_000, low=15_000)

    costs = calculate_transaction_costs(
        asking_price=10_000,
        engine_cc=1600,
        fuel_type="diesel",
        year=2020,
        vehicle_type="carros",
        is_national=True,
        condition_score=8.5,
    )
    selling = calculate_selling_costs(sale_price=15_000, vehicle_type="carros")
    margin = 15_000 - costs.total_cost - selling["total"]
    if margin > 0:
        margin -= margin * 0.23 / 1.23

    assert _default_net_profit(vehicle, estimate) == pytest.approx(margin, abs=0.01)
    assert _default_net_profit(vehicle, estimate) > 0


def test_health_scraper_status_distinguishes_registry_from_live_probe():
    from api.services.health_service import HealthService

    result = HealthService().check_scraper_registry()

    assert result["status"] == "healthy"
    assert result["configured_sources"] > 0
    assert result["invalid_sources"] == []
    assert result["live_health"] == "not_measured"
    assert all(source["healthy"] == "not_measured" for source in result["registry"]["sources"])


def test_external_legacy_sources_are_not_mislabelled_as_portuguese_retail():
    from scrapers.registry import build_registry_report

    report = build_registry_report(selected=["autohero", "wallapop", "autopt"])
    roles = {entry["dispatch_name"]: entry["role"] for entry in report["sources"]}

    assert roles["autohero"] == "importacao"
    assert roles["wallapop"] == "importacao"
    assert roles["autopt"] == "retalho"


def test_derived_profit_fields_use_net_profit_not_asking_gap():
    estimate = _estimate(value=12_000, low=11_000)
    opportunity = classify(
        listing_price=10_000,
        market_value=12_000,
        market_low=11_000,
        market_high=13_000,
        confidence=0.8,
        confidence_label="alta",
        comparables_count=25,
    )
    reliability = assess(10_000, 12_000, 25)
    valuation = VehicleValuation(
        vehicle_id=1,
        estimate=estimate,
        opportunity=opportunity,
        flags=ListingFlags(),
        canonical={},
        fingerprint="test",
        net_profit=400.0,
        reliability=reliability,
    )

    fields = valuation.derived_fields()
    assert fields["profit_potential"] == 400.0
    assert fields["credible_profit"] == 400.0
    assert fields["estimated_savings"] == 2_000.0
    assert fields["profit_percentage"] == pytest.approx(4.0)


def test_revalue_incremental_cleans_stale_ineligible_derivatives(monkeypatch):
    from valuation import service as valuation_service

    rows = [
        {
            "id": 1, "brand": "VW", "model": "Golf", "year": 2020,
            "km": 50_000, "price": 20_000, "price_kind": "total",
            "currency": "EUR", "quality_status": "valid", "source": "OLX",
            "title": "VW Golf", "url": "https://olx.pt/1",
            "vehicle_type": "carros",
            "valuation_details": {"valuation_version": VALUATION_VERSION},
        },
        {
            "id": 2, "brand": "VW", "model": "Golf", "year": 2020,
            "km": 50_000, "price": 0, "price_kind": "monthly",
            "currency": "EUR", "quality_status": "quarantined", "source": "OLX",
            "title": "VW Golf 299€/mês", "url": "https://olx.pt/2",
            "vehicle_type": "carros",
            "valuation_details": {"valuation_version": "v2.9"},
        },
    ]
    writes = []

    monkeypatch.setattr(
        valuation_service,
        "load_market_rows",
        lambda **kwargs: rows,
    )

    class FakeDB:
        def bulk_update_mappings(self, _model, mappings):
            writes.extend(mappings)

        def commit(self):
            return None

    @contextmanager
    def fake_db_context():
        yield FakeDB()

    monkeypatch.setattr("database.db.get_db_context", fake_db_context)

    stats = valuation_service.revalue_database(batch_size=10, force=False)

    assert stats["processed"] == 1
    assert writes and writes[0]["id"] == 2
    assert writes[0]["estimated_value"] is None
    assert writes[0]["credible_profit"] is None
    assert writes[0]["profit_is_publishable"] is False


def test_sqlite_backup_uses_consistent_snapshot_and_integrity_check():
    from database.backup import DatabaseBackup

    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        root = Path(temp_dir)
        db_path = root / "source.db"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO sample(value) VALUES ('durable')")
        conn.commit()
        conn.close()

        backup_path = DatabaseBackup(
            f"sqlite:///{db_path}", backup_dir=str(root / "backups")
        ).create_backup(compression=True)

        assert backup_path is not None
        compressed = Path(backup_path)
        with gzip.open(compressed, "rb") as source:
            restored_path = root / "restored.db"
            restored_path.write_bytes(source.read())
        restored = sqlite3.connect(restored_path)
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT value FROM sample").fetchone()[0] == "durable"
        restored.close()


def test_scraper_registry_has_a_real_dispatch_path_for_every_source():
    from scrapers.parallel_runner import DEFAULT_SOURCES
    from scrapers.registry import build_registry_report

    report = build_registry_report(selected=DEFAULT_SOURCES)
    assert report["status"] == "healthy", report["invalid_sources"]
    vpauto = next(row for row in report["sources"] if row["dispatch_name"] == "vpauto")
    assert vpauto["enum_exists"] is True
    assert vpauto["implementation_exists"] is True
    assert vpauto["dispatchable"] is True
    assert vpauto["requires_js"] is True


def test_scraper_persistence_flushes_valid_rows_as_a_batch(monkeypatch):
    from database.models import FuelType, Transmission, Vehicle, VehicleType
    from scrapers.parallel_runner import save_to_database

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()

    @contextmanager
    def fake_db_context():
        yield session

    monkeypatch.setattr("database.db.get_db_context", fake_db_context)
    listings = [
        {
            "source_id": "batch-1", "url": "https://olx.pt/batch-1",
            "brand": "Volkswagen", "model": "Golf", "year": 2020,
            "km": 50_000, "price": 15_000, "price_kind": "total",
            "currency": "EUR", "vehicle_type": VehicleType.carros,
            "fuel_type": FuelType.GASOLINE, "transmission": Transmission.MANUAL,
            "title": "Volkswagen Golf 2020", "location": "Porto",
        },
        {
            "source_id": "batch-2", "url": "https://olx.pt/batch-2",
            "brand": "Renault", "model": "Clio", "year": 2021,
            "km": 30_000, "price": 13_000, "price_kind": "total",
            "currency": "EUR", "vehicle_type": VehicleType.carros,
            "fuel_type": FuelType.GASOLINE, "transmission": Transmission.MANUAL,
            "title": "Renault Clio 2021", "location": "Lisboa",
        },
    ]
    metrics = {}

    assert save_to_database(listings, "olx", metrics, batch_size=2) == 2
    assert metrics["persisted"] == 2
    assert session.query(Vehicle).count() == 2
    session.close()


def test_scraper_persistence_maps_spoticar_pt_and_deduplicates_batch(monkeypatch):
    from database.models import Vehicle, VehicleType
    from scrapers.parallel_runner import save_to_database

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()

    @contextmanager
    def fake_db_context():
        yield session

    monkeypatch.setattr("database.db.get_db_context", fake_db_context)
    listing = {
        "source_id": "spoticar-1", "url": "https://www.spoticar.pt/spoticar-1",
        "brand": "Peugeot", "model": "308", "year": 2022,
        "km": 20_000, "price": 18_500, "price_kind": "total",
        "currency": "EUR", "vehicle_type": VehicleType.carros,
        "title": "Peugeot 308 2022", "location": "Lisboa",
    }

    duplicate = dict(listing, url="https://www.spoticar.pt/spoticar-1-copy")
    metrics = {}

    assert save_to_database([listing, duplicate], "spoticar_pt", metrics, batch_size=2) == 1
    assert metrics["persisted"] == 1
    assert metrics["duplicates"] == 1
    assert session.query(Vehicle).count() == 1
    assert session.query(Vehicle).one().source.value == "SPOTICAR_PT"
    session.close()


def test_scraper_persistence_refreshes_core_fields_without_erasing_missing_values(monkeypatch):
    from database.models import Source, Vehicle, VehicleType
    from scrapers.parallel_runner import save_to_database

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    existing = Vehicle(
        source=Source.OLX,
        source_id="refresh-1",
        url="https://www.olx.pt/refresh-1",
        vehicle_type=VehicleType.carros,
        brand="Volkswagen",
        model="Golf",
        year=2020,
        km=80_000,
        price=15_000,
        title="Volkswagen Golf 2020",
        description="descrição anterior",
        location="Porto",
        is_active=False,
        scrape_count=1,
    )
    session.add(existing)
    session.commit()

    @contextmanager
    def fake_db_context():
        yield session

    monkeypatch.setattr("database.db.get_db_context", fake_db_context)
    listing = {
        "source_id": "refresh-1", "url": "https://www.olx.pt/refresh-1",
        "brand": "Volkswagen", "model": "Golf", "year": 2021,
        "km": 45_000, "price": 16_500, "price_kind": "total",
        "currency": "EUR", "vehicle_type": VehicleType.carros,
        "title": "Volkswagen Golf 2021", "location": "Lisboa",
    }

    metrics = {}
    assert save_to_database([listing], "olx", metrics) == 1
    refreshed = session.query(Vehicle).one()
    assert metrics["updated"] == 1
    assert refreshed.year == 2021
    assert refreshed.km == 45_000
    assert refreshed.price == 16_500
    assert refreshed.title == "Volkswagen Golf 2021"
    assert refreshed.description == "descrição anterior"
    assert refreshed.is_active is True
    assert refreshed.scrape_count == 2
    session.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_per_scraper": 0},
        {"max_workers": 0},
        {"vehicle_type": "boats"},
    ],
)
def test_parallel_runner_rejects_invalid_operational_limits(kwargs):
    from scrapers.parallel_runner import run_all_scrapers

    with pytest.raises(ValueError):
        run_all_scrapers(save_to_db=False, **kwargs)
