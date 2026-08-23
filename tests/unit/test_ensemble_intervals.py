"""Intervalos no ensemble: banda ML calibrada + banda mínima garantida."""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from valuation.ensemble import _ensure_band, blend_estimate
from valuation.comparables import MarketEstimate


class _FakePredictorWithInterval:
    """Predictor com intervalo calibrado (como PricePredictor real)."""

    vehicle_type = "carros"

    def __init__(self, value=10000.0, spread_pct=0.18):
        self.value = value
        self.spread = spread_pct
        self.interval_calls = 0

    def predict(self, vehicle):
        return self.value

    def predict_with_interval(self, vehicle) -> Tuple[float, float, float]:
        self.interval_calls += 1
        v = self.value
        return (v * (1 - self.spread), v, v * (1 + self.spread))


class _FakePredictorPointOnly:
    vehicle_type = "carros"

    def predict(self, vehicle):
        return 10000.0


def _comparable_ok(value=12000.0, confidence=0.5, low=None, high=None, used=4):
    return MarketEstimate(
        value=value,
        low=low,
        high=high,
        status="ok",
        method="median",
        level=None,
        comparables_used=used,
        comparables_rejected=1,
        mean_similarity=0.85,
        dispersion_pct=8.0,
        confidence=confidence,
        confidence_label="media",
        explanation="test",
    )


class TestMlBandIntegration:
    def test_interval_method_is_used_when_available(self):
        predictor = _FakePredictorWithInterval(spread_pct=0.20)
        est = blend_estimate(
            {"vehicle_type": "carros", "price": 9000.0},
            _comparable_ok(),
            predictor=predictor,
            canon=None,
        )
        assert predictor.interval_calls == 1
        # A banda final incorpora o intervalo ML (±20 % do valor ML).
        assert est.high >= 10000.0 * 1.20 - 1.0
        assert est.low <= 10000.0 * 0.80 + 1.0

    def test_point_only_predictor_falls_back_to_10pct(self):
        est = blend_estimate(
            {"vehicle_type": "carros", "price": 9000.0},
            _comparable_ok(),
            predictor=_FakePredictorPointOnly(),
            canon=None,
        )
        # Banda nunca mais estreita que o default ±10 % em torno do ML.
        assert est.low <= 9000.0 + 1.0
        assert est.high >= 11000.0 - 1.0


class TestNeverZeroWidth:
    def test_missing_comparable_band_gets_minimum_width(self):
        """Bug histórico: sem banda de comparáveis devolvia low==high==valor."""
        est = blend_estimate(
            {"vehicle_type": "carros", "price": 9000.0},
            _comparable_ok(low=None, high=None),
            predictor=_FakePredictorPointOnly(),
            canon=None,
        )
        assert est.low is not None and est.high is not None
        width_pct = (est.high - est.low) / est.value
        assert width_pct > 0.05, f"banda degenerada: {est.low}..{est.high}"

    def test_crossed_band_is_discarded_not_trusted(self):
        est = blend_estimate(
            {"vehicle_type": "carros", "price": 9000.0},
            _comparable_ok(low=15000.0, high=8000.0),  # cruzada
            predictor=_FakePredictorPointOnly(),
            canon=None,
        )
        assert est.low < est.value < est.high

    def test_high_confidence_still_keeps_six_percent_floor(self):
        lo, hi = _ensure_band(None, None, center=20000.0, confidence=0.95)
        assert lo <= 20000.0 * (1 - 0.06) + 0.01
        assert hi >= 20000.0 * (1 + 0.06) - 0.01

    def test_low_confidence_widens_band(self):
        lo_conf, hi_conf = _ensure_band(None, None, 20000.0, confidence=0.2)
        hi_conf_lo, hi_conf_hi = _ensure_band(None, None, 20000.0, confidence=0.9)
        assert (hi_conf - lo_conf) > (hi_conf_hi - hi_conf_lo)

    def test_existing_good_band_is_only_widened_never_shrunk(self):
        lo, hi = _ensure_band(14000.0, 26000.0, center=20000.0, confidence=0.9)
        assert lo <= 14000.0
        assert hi >= 26000.0

    def test_ensure_band_handles_zero_center(self):
        lo, hi = _ensure_band(None, None, center=0.0, confidence=0.5)
        assert lo is None and hi is None


class TestBackwardsCompat:
    def test_blend_output_shape_unchanged(self):
        est = blend_estimate(
            {"vehicle_type": "carros", "price": 9000.0},
            _comparable_ok(low=10800.0, high=13200.0),
            predictor=_FakePredictorPointOnly(),
            canon=None,
        )
        assert est.status == "ok"
        assert est.method == "ensemble_comparaveis_ml_referencia"
        # Blend ponderado por confiança: (12000*0.5 + 10000*0.3) / 0.8.
        assert est.value == pytest_approx(11250.0, tol=1.0)
        assert est.ml_estimate == 10000.0
        assert est.low < est.value < est.high


def pytest_approx(expected, tol=1.0):
    class _Approx:
        def __eq__(self, other):
            return other is not None and abs(other - expected) <= tol

    return _Approx()
