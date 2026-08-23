"""Testes de unidade para valuation.ensemble (sem dependência da base).

Cobrem os contractos de segurança do ensemble:
  * estimativa de comparáveis ok → blend com ML/referência (triangulação);
  * fallback de referência só para base/sport_trim com ancoragem confiável;
  * performance real e ausência de âncora mantêm dados_insuficientes;
  * outliers de ML são descartados.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from valuation.comparables import MarketEstimate, _insufficient  # noqa: E402
from valuation.ensemble import (  # noqa: E402
    _REF_FALLBACK_MAX_CONF,
    _inlier,
    _label,
    blend_estimate,
)


BASE = SimpleNamespace(
    performance_class="base", fuel="gasolina", model_family="golf",
    brand="vw", year=2020,
)
SPORT = SimpleNamespace(
    performance_class="sport_trim", fuel="diesel", model_family="golf",
    brand="vw", year=2019,
)
PERF = SimpleNamespace(
    performance_class="performance", fuel="gasolina", model_family="a35",
    brand="Mercedes-Benz", year=2020,
)

VEH = {"price": 20000, "brand": "vw", "model": "golf", "year": 2020, "km": 10000,
       "vehicle_type": "carros", "fuel_type": "gasolina"}


def mk_comp(value=20000.0, conf=0.85, n=10):
    return MarketEstimate(
        value=value, low=value * 0.9, high=value * 1.1, status="ok",
        method="comparaveis_nivel_1", level=1, comparables_used=n,
        comparables_rejected=2, mean_similarity=0.8, dispersion_pct=10.0,
        confidence=conf, confidence_label="media", explanation="base",
        used=[], rejected=[], rejection_summary={}, notes=[],
    )


class FakePredictor:
    def __init__(self, value):
        self.value = value
        self.model_loaded_ok = True

    def predict(self, vehicle):
        return self.value


def _ref(value=18000.0, conf=0.90, matched="vw golf", age=3):
    return {"value": value, "low": value * 0.95, "high": value * 1.05,
            "confidence": conf, "matched_model": matched, "age": age}


def test_label_thresholds():
    assert _label(0.7) == "alta"
    assert _label(0.5) == "media"
    assert _label(0.3) == "baixa"
    assert _label(0.1) == "muito_baixa"


def test_inlier_band():
    assert _inlier(20000, 100000) is False
    assert _inlier(50000, 50000) is True
    assert _inlier(None, 100) is False
    assert _inlier(100, None) is False


def test_ok_comparables_triangulated_with_ml_and_reference():
    comp = mk_comp(value=20000.0, conf=0.5, n=10)
    pred = FakePredictor(20500.0)
    e = blend_estimate(dict(VEH), comp, predictor=pred, ref=_ref(20000.0, 0.8),
                       canon=BASE)
    assert e.status == "ok"
    assert e.comparables_used == 10
    assert e.ml_estimate == 20500.0
    assert e.reference_estimate is not None
    assert 20000 <= e.value <= 20500
    assert e.confidence >= 0.55


def test_high_confidence_comparables_do_not_query_ml():
    comp = mk_comp(conf=0.95)
    pred = FakePredictor(999_999.0)
    e = blend_estimate(dict(VEH), comp, predictor=pred, ref=None, canon=BASE)
    assert e.status == "ok"
    assert e.ml_estimate is None
    assert abs(e.value - 20000) < 1


def test_ml_outlier_is_dropped():
    comp = mk_comp(value=20000.0, conf=0.5)
    pred = FakePredictor(2_000_000.0)
    e = blend_estimate(dict(VEH), comp, predictor=pred, ref=None, canon=BASE)
    assert e.ml_estimate is None
    assert abs(e.value - 20000) < 1


def test_reference_outlier_is_dropped_from_blend():
    comp = mk_comp(value=20000.0, conf=0.5)
    e = blend_estimate(dict(VEH), comp,
                       predictor=FakePredictor(2_000_000.0),
                       ref=_ref(value=100000.0, conf=0.9), canon=BASE)
    assert e.status == "ok"
    assert e.reference_estimate is None
    assert abs(e.value - 20000) < 1


def test_low_confidence_reference_fallback_for_base():
    ins = _insufficient("sem dados", [], {}, ["n"])
    e = blend_estimate(dict(VEH, price=18000), ins, predictor=None,
                       ref=_ref(18000.0, 0.9), canon=BASE)
    assert e.status == "low_confidence"
    assert e.value == 18000.0
    assert e.comparables_used == 0
    assert e.confidence <= _REF_FALLBACK_MAX_CONF
    assert e.confidence_label == "baixa"
    assert e.ml_estimate is None  # ancora forte (0.9) → sem ML


def test_fallback_ml_triangulation_boosts_confidence():
    ins = _insufficient("sem dados", [], {}, ["n"])
    ref = _ref(18000.0, 0.58)
    pred = FakePredictor(18200.0)
    e = blend_estimate(dict(VEH, price=18000), ins, predictor=pred, ref=ref,
                       canon=BASE)
    assert e.status == "low_confidence"
    assert e.ml_estimate == 18200.0
    assert e.confidence == _REF_FALLBACK_MAX_CONF


def test_performance_variant_never_falls_back():
    ins = _insufficient("sem dados", [], {}, ["n"])
    e = blend_estimate(dict(VEH, price=50000, brand="Mercedes-Benz",
                            model="A 35 AMG"), ins, predictor=None,
                       ref=_ref(50000.0, 0.9), canon=PERF)
    assert e.status == "dados_insuficientes"
    assert e.value is None


def test_no_anchor_stays_insufficient():
    ins = _insufficient("sem dados", [], {}, ["n"])
    e = blend_estimate(dict(VEH, brand="Lexus", model="IS 220"), ins, ref={},
                       canon=BASE)
    assert e.status == "dados_insuficientes"
    assert e.value is None


def test_weak_anchor_below_threshold_stays_insufficient():
    ins = _insufficient("sem dados", [], {}, ["n"])
    e = blend_estimate(dict(VEH, price=20000), ins, ref=_ref(18000.0, 0.50),
                       canon=BASE)
    assert e.status == "dados_insuficientes"
    assert e.value is None


def test_diesel_base_anchors_via_fallback():
    ins = _insufficient("sem dados", [], {}, ["n"])
    vehicle = dict(VEH, price=16800, fuel_type="diesel")
    e = blend_estimate(vehicle, ins, predictor=None,
                       ref=_ref(16800.0, 0.85), canon=SPORT)
    assert e.status == "low_confidence"
    assert e.value == 16800.0
