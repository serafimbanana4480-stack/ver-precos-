"""Testes do motor Max Buy Price (valuation/economics.py)."""
from __future__ import annotations

import math

import pytest

from valuation.economics import (
    DEFAULT_EXIT_DISCOUNT_PCT,
    DEFAULT_MIN_ROI,
    DEFAULT_SAFETY_MARGIN_PCT,
    DEFAULT_TARGET_PROFIT_EUR,
    buy_verdict,
    calculate_max_buy_price,
)


def _national_car(**overrides):
    base = dict(
        vehicle_type="carros",
        engine_cc=1600,
        co2_gkm=120.0,
        fuel_type="gasolina",
        age_years=6,
        is_national=True,
        repair_costs=0.0,
        transport_cost=0.0,
        days_to_sell=45,
    )
    base.update(overrides)
    return base


class TestFailClosed:
    def test_no_estimate_returns_none_not_number(self):
        result = calculate_max_buy_price(None, **_national_car())
        assert result["max_buy_price"] is None
        assert result["reason"] == "no_estimate"

    def test_zero_estimate_fails_closed(self):
        result = calculate_max_buy_price(0.0, **_national_car())
        assert result["max_buy_price"] is None


class TestFeasibleCases:
    def test_market_value_yields_positive_max_buy(self):
        """Um carro avaliado em 15 000 € nacional tem de ter max buy > 0."""
        result = calculate_max_buy_price(
            15000.0, **_national_car(repair_costs=400.0)
        )
        assert result["max_buy_price"] is not None
        assert 0 < result["max_buy_price"] < 15000.0
        assert result["reason"] is None
        # A saída conservadora é estritamente abaixo do valor de referência.
        expected_exit = 15000.0 * (1 - DEFAULT_EXIT_DISCOUNT_PCT) * (
            1 - DEFAULT_SAFETY_MARGIN_PCT
        )
        assert result["exit_value"] == pytest.approx(expected_exit, rel=0.01)

    def test_max_buy_respects_target_profit_at_solution(self):
        """No máximo devolvido, o lucro líquido >= alvo - tolerância."""
        target = 1500.0
        result = calculate_max_buy_price(
            18000.0, **_national_car(), target_profit_eur=target
        )
        assert result["max_buy_price"] is not None
        # Tolerância de 60 €: a bisseção para a 50 cêntimos + custos discretos.
        assert result["net_profit_at_max"] >= target - 60.0

    def test_higher_target_lowens_max_buy(self):
        low = calculate_max_buy_price(
            15000.0, **_national_car(), target_profit_eur=500.0
        )
        high = calculate_max_buy_price(
            15000.0, **_national_car(), target_profit_eur=3000.0
        )
        assert low["max_buy_price"] and high["max_buy_price"]
        assert high["max_buy_price"] < low["max_buy_price"]

    def test_min_roi_constraint_binds_for_cheap_cars(self):
        """Com ROI mínimo alto, max buy fica abaixo da solução só-lucro."""
        relaxed = calculate_max_buy_price(
            6000.0, **_national_car(), min_roi=0.05
        )
        strict = calculate_max_buy_price(
            6000.0, **_national_car(), min_roi=0.60
        )
        assert strict["max_buy_price"] <= relaxed["max_buy_price"]
        # No ponto estrito o ROI tem de respeitar o piso (±tolerância).
        if strict["roi_at_max"] is not None:
            assert strict["roi_at_max"] >= 0.60 * 100 * 0.95 - 1.5

    def test_breakdown_sums_are_consistent(self):
        result = calculate_max_buy_price(
            20000.0, **_national_car(repair_costs=500.0)
        )
        bd = result["breakdown"]
        assert bd is not None
        invested = bd["purchase"] + bd["taxes_fees"] + bd["repairs"] + bd["transport"]
        assert invested == pytest.approx(bd["total_invested"], abs=1.5)


class TestInfeasible:
    def test_toy_price_market_cannot_hit_target(self):
        """Mercado de 900 € não permite lucro de 1000 € nem comprando grátis."""
        result = calculate_max_buy_price(900.0, **_national_car())
        assert result["max_buy_price"] is None
        assert result["reason"] == "infeasible_even_free"


class TestBuyVerdict:
    def _cap(self, price=12000.0):
        return {"max_buy_price": price}

    def test_below_cap_is_buy_zone(self):
        assert buy_verdict(11000.0, self._cap()) == "BUY_ZONE"

    def test_within_ten_percent_window_negotiates(self):
        assert buy_verdict(12700.0, self._cap()) == "NEGOTIATE"

    def test_far_above_cap_passes(self):
        assert buy_verdict(15000.0, self._cap()) == "PASS"

    def test_missing_data_never_buys(self):
        assert buy_verdict(5000.0, None) == "PASS"
        assert buy_verdict(None, self._cap()) == "PASS"
        assert buy_verdict(5000.0, {"max_buy_price": None}) == "PASS"
