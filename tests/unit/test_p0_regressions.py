import json
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.verify_model_artifacts import verify_model_artifacts
from scripts.verify_source_integrity import audit_source_rows
from utils.source_normalize import normalize_source
from validation.normalizers import normalize_vehicle_data
from valuation.comparables import Comparable


def test_comparable_dataclass_keeps_positional_rejection_reason():
    comparable = Comparable(1, 10_000.0, 2020, 50_000, "OLX", 0.8, 0.7, "outlier")

    assert comparable.reason == "outlier"
    assert comparable.horsepower is None


def test_model_artifact_verifier_fails_when_metadata_points_to_missing_files():
    # The default pytest temp root is not writable in the hardened Windows
    # runner; use a short-lived directory inside the checked-out workspace.
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        model_dir = Path(temp_dir)
        (model_dir / "best_model_carros.json").write_text(
            json.dumps({
                "model_type": "extra_trees",
                "model_path": "model_carros.joblib",
                "scaler_path": "scaler_carros.joblib",
                "brand_index_path": "brand_index_carros.json",
            }),
            encoding="utf-8",
        )
        report = verify_model_artifacts(model_dir, vehicle_types=("carros",))

    assert report["status"] == "unhealthy"
    assert report["missing"] == [
        "carros:model",
        "carros:scaler",
        "carros:brand_index",
    ]


def test_model_artifact_verifier_rejects_paths_outside_model_directory():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        model_dir = Path(temp_dir)
        (model_dir / "best_model_carros.json").write_text(
            json.dumps({
                "model_type": "extra_trees",
                "model_path": "../outside.joblib",
                "scaler_path": "scaler.joblib",
                "brand_index_path": "brand.json",
            }),
            encoding="utf-8",
        )
        report = verify_model_artifacts(model_dir, vehicle_types=("carros",))

    assert report["status"] == "unhealthy"
    assert "carros:model" in report["missing"]


def test_model_artifact_verifier_rejects_empty_binary_and_invalid_brand_index():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        model_dir = Path(temp_dir)
        (model_dir / "best_model_carros.json").write_text(
            json.dumps({
                "model_type": "extra_trees",
                "model_path": "model.joblib",
                "scaler_path": "scaler.joblib",
                "brand_index_path": "brand.json",
            }),
            encoding="utf-8",
        )
        (model_dir / "model.joblib").write_bytes(b"")
        (model_dir / "scaler.joblib").write_bytes(b"valid")
        (model_dir / "brand.json").write_text("[]", encoding="utf-8")
        report = verify_model_artifacts(model_dir, vehicle_types=("carros",))

    assert report["status"] == "unhealthy"
    assert "carros:model:empty" in report["invalid"]
    assert "carros:brand_index:not_object" in report["invalid"]


def test_source_url_prevents_autouncle_autopt_contamination():
    assert normalize_source("AUTOPT", "https://www.autouncle.pt/anuncio/123") == "AUTOUNCLE"
    assert normalize_source("AUTOUNCLE", "https://www.auto.pt/viatura/123") == "AUTOPT"
    assert normalize_vehicle_data({
        "source": "autopt", "url": "https://www.autouncle.pt/anuncio/123"
    })["source"] == "autouncle"


def test_source_integrity_audit_finds_cross_source_url_labels():
    report = audit_source_rows([
        {"source": "AUTOPT", "url": "https://www.autouncle.pt/anuncio/1"},
        {"source": "AUTOPT", "url": "https://www.auto.pt/viatura/2"},
        {"source": "OLX", "url": "https://www.olx.pt/item/3"},
    ])

    assert report["status"] == "unhealthy"
    assert report["mismatches"] == 1
    assert report["by_pair"] == {"AUTOPT->AUTOUNCLE": 1}


def test_data_freshness_reports_stale_and_missing_active_rows(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [(now,), (now - timedelta(hours=72),), (None,)]

    class FakeSession:
        def query(self, *_args):
            return self

        def filter(self, *_args):
            return self

        def all(self):
            return rows

    @contextmanager
    def fake_db_context():
        yield FakeSession()

    monkeypatch.setattr("database.db.get_db_context", fake_db_context)

    from api.services.health_service import HealthService

    report = HealthService().check_data_freshness(max_age_hours=48)

    assert report["status"] == "unhealthy"
    assert report["active_total"] == 3
    assert report["stale_count"] == 1
    assert report["missing_last_seen"] == 1
    assert report["stale_ratio"] == round(1 / 3, 4)


def test_legacy_listing_router_protects_writes_and_orders_static_paths():
    from api.dependencies import get_current_user, require_admin
    from api.routes.listings import listings_router

    routes = [route for route in listings_router.routes if hasattr(route, "path")]
    detail_index = next(
        index for index, route in enumerate(routes)
        if route.path == "/listings/{listing_id}" and "GET" in route.methods
    )
    for static_path in ("/listings/featured", "/listings/recent", "/listings/stats"):
        static_index = next(
            index for index, route in enumerate(routes) if route.path == static_path
        )
        assert static_index < detail_index

    for route in routes:
        if "GET" in route.methods and route.path in {"/listings/", "/listings/{listing_id}", "/listings/{listing_id}/similar", "/listings/featured", "/listings/recent", "/listings/stats", "/listings/search/suggestions"}:
            assert any(dependency.call == get_current_user for dependency in route.dependant.dependencies)

    for route in routes:
        if route.path in {"/listings/", "/listings/{listing_id}", "/listings/bulk"} and {"POST", "PUT", "DELETE"}.intersection(route.methods):
            assert any(dependency.call == require_admin for dependency in route.dependant.dependencies)


def test_cache_delete_pattern_invalidates_only_matching_listing_keys():
    from ingestion.storage.cache_storage import CacheStorage

    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        cache = CacheStorage(cache_dir=temp_dir)
        cache.set("listing:7:OLX", {"id": 7})
        cache.set("listing:7:STANDVIRTUAL", {"id": 7})
        cache.set("listing:8:OLX", {"id": 8})

        assert cache.delete_pattern("listing:7:*") == 2
        assert cache.get("listing:7:OLX") is None
        assert cache.get("listing:7:STANDVIRTUAL") is None
        assert cache.get("listing:8:OLX") == {"id": 8}


def test_health_legacy_methods_do_not_claim_unmeasured_states_are_healthy():
    from api.services.health_service import HealthService

    service = HealthService()
    assert service.check_data_freshness(0)["status"] == "unhealthy"
    assert service.toggle_maintenance_mode(True)["status"] == "not_configured"
    assert service.trigger_backup()["status"] == "not_implemented"
    assert service.get_sla_metrics()["availability"] is None
    assert isinstance(service.get_health_alerts(limit=10), list)
