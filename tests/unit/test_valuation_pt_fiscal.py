"""
Regression tests: deal profit taxes use the real PT fiscal engine.

Regression scenario (plan): the old deal_profit_calculator charged a flat
~15.5% (IMT 5% + ISV 10% + stamp duty 0.5%) on every vehicle. Portugal
charges NO IMT/stamp duty on vehicle sales: a national used car only pays
registo de propriedade (55,30 € online) + IPO. ISV + legalização (550 €)
apply exclusively to imports. These tests pin the correct 2026 values
against valuation.pt_fiscal.calculate_transaction_costs() — the engine is
NOT mocked.
"""
import pytest

from intelligence.profit.deal_profit_calculator import DealProfitCalculator


def _golf_2018() -> dict:
    return {"price": 18000, "year": 2018, "fuel_type": "gasolina", "vehicle_type": "carros", "engine_size": 1500, "km": 80000, "condition_score": 7.0}


@pytest.fixture(scope="module")
def calculator() -> DealProfitCalculator:
    return DealProfitCalculator()


class TestDealProfitTaxes:
    """Regression: national used cars are NOT taxed at 15.5% of the price."""

    def test_national_car_taxes_registo_plus_ipo(self, calculator: DealProfitCalculator):
        # Regression scenario: was 0.155 * 18000 = €2,790; must now be ~87.30
        # (registo 55.30 online + IPO ligeiro 32.00).
        taxes = calculator._calculate_taxes(_golf_2018(), 18000)
        assert taxes == pytest.approx(87.30, abs=0.01)
        assert taxes < 100  # NOT €2,790

    def test_national_moto_taxes_lower_ipo(self, calculator: DealProfitCalculator):
        # Moto: registo 55.30 + IPO moto 22.00 = 77.30.
        moto = _golf_2018()
        moto["vehicle_type"] = "motos"
        taxes = calculator._calculate_taxes(moto, 18000)
        assert taxes == pytest.approx(77.30, abs=0.01)

    def test_import_car_taxes_include_legalization_and_isv(self, calculator: DealProfitCalculator):
        # Import: legalização 550 + ISV (2018, 1500 cm3, gasolina) + registo 55.30
        # + IPO 32.00 — must exceed 550 and be far above the national 87.30.
        imported = _golf_2018()
        imported["is_import"] = True
        taxes = calculator._calculate_taxes(imported, 18000)
        assert taxes > 550.0
        assert taxes > 87.30
