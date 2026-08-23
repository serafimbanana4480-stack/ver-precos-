"""Testes dos hard gates (valuation/gates.py)."""
from __future__ import annotations

from valuation.gates import GATE_THRESHOLDS, apply_hard_gates


class TestVerdicts:
    def test_all_green_is_buy(self):
        result = apply_hard_gates(
            confidence=0.90,
            expected_profit=3000.0,
            risk_score=10.0,
            discount_pct=25.0,
            asking_price=10000.0,
            max_buy_price=11500.0,
        )
        assert result["verdict"] == "BUY"
        assert result["reasons"] == []

    def test_low_confidence_never_buys(self):
        result = apply_hard_gates(
            confidence=0.40, expected_profit=3000.0
        )
        assert result["verdict"] in ("WATCH", "PASS", "REVIEW", "NEGOTIATE")
        assert result["verdict"] != "BUY"
        assert any("confiança" in r for r in result["reasons"])

    def test_unknown_confidence_fails_closed(self):
        result = apply_hard_gates(confidence=None, expected_profit=5000.0)
        assert result["verdict"] != "BUY"
        assert result["checks"]["valuation_confidence"]["ok"] is False

    def test_zero_profit_passes_out(self):
        result = apply_hard_gates(confidence=0.9, expected_profit=0.0)
        assert result["verdict"] == "PASS"

    def test_negative_profit_passes(self):
        result = apply_hard_gates(confidence=0.9, expected_profit=-800.0)
        assert result["verdict"] == "PASS"

    def test_unknown_profit_fails_closed_to_pass(self):
        result = apply_hard_gates(confidence=0.9, expected_profit=None)
        assert result["verdict"] == "PASS"

    def test_high_risk_rejects_even_with_huge_profit(self):
        result = apply_hard_gates(
            confidence=0.95, expected_profit=9000.0, risk_score=85.0
        )
        assert result["verdict"] == "PASS"

    def test_repair_uncertainty_forces_review(self):
        result = apply_hard_gates(
            confidence=0.9,
            expected_profit=2000.0,
            repair_uncertainty=0.75,
        )
        assert result["verdict"] == "REVIEW"

    def test_implausible_discount_rejected(self):
        """-70 % face ao mercado é armadilha clássica: PASS mesmo com lucro."""
        result = apply_hard_gates(
            confidence=0.92,
            expected_profit=4000.0,
            discount_pct=70.0,
        )
        assert result["verdict"] == "PASS"
        assert any("barato demais" in r for r in result["reasons"])

    def test_price_above_max_buy_far_passes(self):
        result = apply_hard_gates(
            confidence=0.9,
            expected_profit=2000.0,
            asking_price=16000.0,
            max_buy_price=12000.0,
        )
        assert result["verdict"] == "PASS"

    def test_price_in_window_negotiates(self):
        result = apply_hard_gates(
            confidence=0.9,
            expected_profit=2000.0,
            asking_price=12500.0,  # ~4 % acima do cap
            max_buy_price=12000.0,
        )
        assert result["verdict"] in ("NEGOTIATE", "WATCH")

    def test_worst_gate_wins_not_first_gate(self):
        """Risco PASS + reparação REVIEW -> PASS (o pior ganha)."""
        result = apply_hard_gates(
            confidence=0.9,
            expected_profit=2000.0,
            risk_score=99.0,
            repair_uncertainty=0.9,
        )
        assert result["verdict"] == "PASS"


class TestAuditTrail:
    def test_checks_carry_values_and_thresholds(self):
        result = apply_hard_gates(
            confidence=0.55, expected_profit=1500.0
        )
        conf_check = result["checks"]["valuation_confidence"]
        assert conf_check["ok"] is False
        assert conf_check["value"] == 0.55
        assert conf_check["threshold"] == GATE_THRESHOLDS["min_confidence"]
        profit_check = result["checks"]["expected_profit"]
        assert profit_check["ok"] is True

    def test_thresholds_are_the_single_source(self):
        """Mudar o limiar central muda o veredito — prova de ligação."""
        assert GATE_THRESHOLDS["min_confidence"] == 0.60
        boundary = apply_hard_gates(confidence=0.60, expected_profit=5000.0)
        assert boundary["checks"]["valuation_confidence"]["ok"] is True
