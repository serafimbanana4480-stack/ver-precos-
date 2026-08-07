"""Testes da auditoria de realismo de preço e lucro.

Fixam as três correções que motivaram o módulo: preço pedido ≠ preço
transacionado, IVA da margem, e recusa de decidir sem evidência. Cada teste
descreve um cenário de negócio concreto, não um valor mágico.
"""
from __future__ import annotations

import pytest

from valuation.realism import (
    IVA_RATE,
    ProfitAudit,
    audit_deal,
    audit_from_valuation,
    realistic_sale_price,
)


BASE = dict(
    retail_estimate=15000.0,
    retail_low=14000.0,
    retail_high=16000.0,
    valuation_confidence=0.75,
    comparables_count=25,
    year=2017,
    km=140000,
    engine_cc=1598,
    co2_gkm=110.0,
    fuel_type="diesel",
    days_to_sell=50,
    is_national=True,
)


class TestRealisticSalePrice:
    def test_applies_negotiation_discount(self):
        # Ninguém vende ao preço mediano anunciado.
        assert realistic_sale_price(20000, days_to_sell=30) < 20000

    def test_slow_stock_sells_for_less(self):
        fast = realistic_sale_price(20000, days_to_sell=25)
        slow = realistic_sale_price(20000, days_to_sell=120)
        assert slow < fast

    def test_salvage_takes_a_large_haircut(self):
        clean = realistic_sale_price(20000, days_to_sell=50)
        salvage = realistic_sale_price(
            20000, days_to_sell=50, has_damage=True, damage_severity="total"
        )
        cosmetic = realistic_sale_price(
            20000, days_to_sell=50, has_damage=True, damage_severity="cosmetico"
        )
        assert salvage < cosmetic < clean

    def test_zero_estimate(self):
        assert realistic_sale_price(0) == 0.0


class TestNationalDeal:
    def test_gross_spread_is_not_profit(self):
        """O spread bruto de 3.000 € não é lucro: sobra uma fração."""
        audit = audit_deal(asking_price=12000, **BASE)
        assert audit.gross_spread == pytest.approx(3000.0)
        # O que fica depois de recondicionamento, registo, IPO, IVA e
        # custo de venda é uma ordem de grandeza menor.
        assert audit.net_profit < audit.gross_spread * 0.35
        assert audit.verdict in ("marginal", "sem_margem")

    def test_national_car_pays_no_isv(self):
        audit = audit_deal(asking_price=12000, **BASE)
        assert audit.cost_breakdown["isv"] == 0.0
        assert audit.cost_breakdown["registo_propriedade"] > 0

    def test_real_bargain_is_recognised(self):
        audit = audit_deal(asking_price=9500, **BASE)
        assert audit.verdict == "negocio"
        assert audit.net_profit > 750
        assert "Lucro líquido" in audit.reasons[0]

    def test_overpriced_car_has_no_margin(self):
        audit = audit_deal(asking_price=15500, **BASE)
        assert audit.verdict == "sem_margem"
        assert audit.net_profit < 0

    def test_break_even_is_actionable(self):
        # O preço de break-even é o número que serve para negociar.
        audit = audit_deal(asking_price=12000, **BASE)
        at_break_even = audit_deal(
            asking_price=audit.break_even_price, **BASE
        )
        assert at_break_even.net_profit == pytest.approx(0.0, abs=250.0)


class TestImportArbitrage:
    def test_import_pays_isv_transport_and_legalisation(self):
        args = dict(BASE)
        args["is_national"] = False
        audit = audit_deal(asking_price=12000, country="DE", **args)
        assert audit.cost_breakdown["isv"] > 0
        assert audit.cost_breakdown["transporte"] > 0
        assert audit.cost_breakdown["legalizacao"] > 0

    def test_same_price_import_is_worse_than_national(self):
        """O mesmo preço vindo da Alemanha é um negócio pior, não igual.

        Era exatamente esta diferença que desaparecia quando a fonte
        estrangeira não marcava ``is_national=False``.
        """
        national = audit_deal(asking_price=12000, **BASE)
        args = dict(BASE)
        args["is_national"] = False
        imported = audit_deal(asking_price=12000, country="DE", **args)
        assert imported.net_profit < national.net_profit
        assert national.net_profit - imported.net_profit > 2000

    def test_import_needs_a_deeper_discount_to_work(self):
        args = dict(BASE)
        args["is_national"] = False
        cheap = audit_deal(asking_price=7000, country="DE", **args)
        assert cheap.net_profit > 0

    def test_missing_co2_on_import_is_flagged(self):
        args = dict(BASE)
        args["is_national"] = False
        args["co2_gkm"] = None
        audit = audit_deal(asking_price=9000, country="DE", **args)
        assert any("CO2" in flag for flag in audit.risk_flags)

    def test_spain_is_cheaper_to_transport_than_germany(self):
        args = dict(BASE)
        args["is_national"] = False
        de = audit_deal(asking_price=10000, country="DE", **args)
        es = audit_deal(asking_price=10000, country="ES", **args)
        assert es.cost_breakdown["transporte"] < de.cost_breakdown["transporte"]
        assert es.net_profit > de.net_profit


class TestVat:
    def test_professional_pays_margin_vat(self):
        pro = audit_deal(asking_price=9500, professional_reseller=True, **BASE)
        private = audit_deal(asking_price=9500, professional_reseller=False, **BASE)
        assert pro.iva_margem > 0
        assert private.iva_margem == 0.0
        assert pro.net_profit < private.net_profit

    def test_vat_is_charged_on_margin_not_on_price(self):
        audit = audit_deal(asking_price=9500, **BASE)
        margin = audit.realistic_sale_price - audit.total_acquisition_cost
        expected = margin * IVA_RATE / (1 + IVA_RATE)
        assert audit.iva_margem == pytest.approx(expected, rel=0.01)

    def test_no_vat_when_there_is_no_margin(self):
        audit = audit_deal(asking_price=16000, **BASE)
        assert audit.iva_margem == 0.0


class TestEvidenceGating:
    def test_refuses_to_decide_without_evidence(self):
        args = dict(BASE)
        args.update(comparables_count=2, valuation_confidence=0.2)
        audit = audit_deal(asking_price=9000, **args)
        assert audit.verdict == "indeterminado"
        assert audit.confidence <= 0.3
        assert "insuficiente" in audit.reasons[0].lower()

    def test_wide_interval_lowers_confidence(self):
        args = dict(BASE)
        args.update(retail_low=8000.0, retail_high=22000.0)
        audit = audit_deal(asking_price=9500, **args)
        assert any("largo" in reason for reason in audit.reasons)

    def test_worst_case_downgrades_a_thin_deal(self):
        # Lucro positivo no cenário central mas negativo no limite inferior:
        # não é um negócio, é uma aposta.
        args = dict(BASE)
        args.update(retail_low=11000.0, retail_high=17000.0)
        audit = audit_deal(asking_price=11000, **args)
        if audit.net_profit > 0 and audit.net_profit_worst_case < 0:
            assert audit.verdict == "marginal"

    def test_no_price_is_indeterminate(self):
        assert audit_deal(asking_price=0, **BASE).verdict == "indeterminado"

    def test_no_estimate_is_indeterminate(self):
        args = dict(BASE)
        args["retail_estimate"] = 0.0
        assert audit_deal(asking_price=12000, **args).verdict == "indeterminado"


class TestFraudDetection:
    def test_absurd_discount_is_suspect_not_a_bargain(self):
        audit = audit_deal(asking_price=3000, **BASE)
        assert audit.verdict == "suspeito"
        assert audit.risk_flags
        assert any("abaixo do mercado" in f for f in audit.risk_flags)

    def test_implausible_roi_is_flagged(self):
        audit = audit_deal(asking_price=4000, **BASE)
        assert audit.verdict == "suspeito"
        assert any("ROI" in f for f in audit.risk_flags)

    def test_declared_damage_is_flagged_and_costed(self):
        clean = audit_deal(asking_price=9500, **BASE)
        damaged = audit_deal(
            asking_price=9500, has_damage=True, damage_severity="total", **BASE
        )
        assert damaged.net_profit < clean.net_profit
        assert any("Dano" in f for f in damaged.risk_flags)

    def test_extreme_mileage_is_flagged(self):
        args = dict(BASE)
        args["km"] = 450000
        audit = audit_deal(asking_price=9500, **args)
        assert any("km/ano" in f for f in audit.risk_flags)


class TestAdapter:
    def test_maps_valuator_output(self):
        vehicle = {
            "price": 12000, "year": 2017, "km": 140000, "engine_size": 1598,
            "fuel_type": "diesel", "is_national": True, "seller_type": "particular",
            "vehicle_type": "carros",
        }
        valuation = {
            "estimated_value": 15000, "value_low": 14000, "value_high": 16000,
            "confidence": 0.7, "comparables_count": 20,
        }
        audit = audit_from_valuation(vehicle, valuation)
        assert isinstance(audit, ProfitAudit)
        assert audit.asking_price == 12000
        assert audit.retail_estimate == 15000
        assert audit.verdict != "indeterminado"

    def test_serialisable(self):
        audit = audit_deal(asking_price=12000, **BASE)
        payload = audit.to_dict()
        assert payload["verdict"] == audit.verdict
        assert isinstance(payload["cost_breakdown"], dict)


class TestMonotonicity:
    """Propriedades que têm de valer sempre, não só nos exemplos escolhidos."""

    @pytest.mark.parametrize("price", [8000, 9000, 10000, 11000, 12000, 13000])
    def test_profit_decreases_with_price(self, price):
        cheaper = audit_deal(asking_price=price - 500, **BASE)
        dearer = audit_deal(asking_price=price, **BASE)
        assert cheaper.net_profit > dearer.net_profit

    @pytest.mark.parametrize("days", [30, 60, 90, 150])
    def test_slower_sale_never_improves_profit(self, days):
        args = dict(BASE)
        args["days_to_sell"] = days
        audit = audit_deal(asking_price=9500, **args)
        args["days_to_sell"] = days + 30
        slower = audit_deal(asking_price=9500, **args)
        assert slower.net_profit <= audit.net_profit
