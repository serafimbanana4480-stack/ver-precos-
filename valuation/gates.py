"""Hard gates — vereditos estruturais que nenhum score alto contorna.

Um Opportunity Score alto não pode esconder um risco grave: os gates são
avaliados ANTES e FORA do score. Cada gate falhado degrada o veredito para
WATCH / REVIEW / PASS mesmo que o desconto seja enorme.

Regras (P0 do plano de produto):
  * confiança de valuation < 60 %        -> nunca BUY;
  * lucro esperado < 1000 €              -> nunca BUY;
  * risco > 70/100                       -> PASS;
  * incerteza de reparação > 50 %        -> MANUAL REVIEW;
  * desconto vs mercado > 55 %           -> PASS ("barato demais = armadilha",
    mesma filosofia do realism.py);
  * pedido acima do max buy + janela     -> PASS; dentro da janela -> NEGOTIATE.

O veredito é fail-closed: dados em falta tratam-se como reprovados, nunca
como aprovados.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["apply_hard_gates", "GATE_THRESHOLDS"]

#: Limiares centralizados — uma única fonte de verdade para testes e UI.
GATE_THRESHOLDS: Dict[str, float] = {
    "min_confidence": 0.60,
    "min_expected_profit_eur": 1000.0,
    "max_risk_score": 70.0,
    "max_repair_uncertainty": 0.50,
    "max_discount_vs_market": 55.0,
}

_VERDICT_ORDER = {"PASS": 0, "REVIEW": 1, "NEGOTIATE": 2, "WATCH": 3, "BUY": 4}


def _worst(verdicts: List[str]) -> str:
    return min(verdicts, key=lambda v: _VERDICT_ORDER.get(v, -1)) if verdicts else "PASS"


def apply_hard_gates(
    *,
    confidence: Optional[float],
    expected_profit: Optional[float],
    risk_score: Optional[float] = None,
    repair_uncertainty: Optional[float] = None,
    discount_pct: Optional[float] = None,
    asking_price: Optional[float] = None,
    max_buy_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Aplica os gates e devolve veredito + trilha auditável.

    Returns:
        dict com ``verdict`` (BUY | WATCH | NEGOTIATE | REVIEW | PASS),
        ``checks`` (um booleano por gate, incluindo o valor avaliado) e
        ``reasons`` (motivos legíveis por cada gate não aprovado).
    """
    checks: Dict[str, Dict[str, Any]] = {}
    reasons: List[str] = []
    verdicts: List[str] = []
    t = GATE_THRESHOLDS

    # -- Gate: confiança ---------------------------------------------------
    if confidence is None:
        checks["valuation_confidence"] = {"ok": False, "value": None}
        reasons.append("confiança de valuation desconhecida")
        verdicts.append("WATCH")
    else:
        ok = confidence >= t["min_confidence"]
        checks["valuation_confidence"] = {
            "ok": ok,
            "value": round(confidence, 3),
            "threshold": t["min_confidence"],
        }
        if not ok:
            reasons.append(
                f"confiança {confidence:.0%} < {t['min_confidence']:.0%}"
            )
            verdicts.append("WATCH")

    # -- Gate: lucro esperado ----------------------------------------------
    if expected_profit is None:
        checks["expected_profit"] = {"ok": False, "value": None}
        reasons.append("lucro esperado desconhecido")
        verdicts.append("PASS")
    else:
        ok = expected_profit >= t["min_expected_profit_eur"]
        checks["expected_profit"] = {
            "ok": ok,
            "value": round(expected_profit, 2),
            "threshold": t["min_expected_profit_eur"],
        }
        if not ok:
            reasons.append(
                f"lucro esperado {expected_profit:.0f}€ < {t['min_expected_profit_eur']:.0f}€"
            )
            verdicts.append("PASS" if expected_profit <= 0 else "WATCH")

    # -- Gate: risco ---------------------------------------------------------
    if risk_score is not None and risk_score > t["max_risk_score"]:
        checks["risk"] = {
            "ok": False,
            "value": risk_score,
            "threshold": t["max_risk_score"],
        }
        reasons.append(f"risco {risk_score:.0f} > {t['max_risk_score']:.0f}")
        verdicts.append("PASS")
    elif risk_score is not None:
        checks["risk"] = {"ok": True, "value": risk_score, "threshold": t["max_risk_score"]}

    # -- Gate: incerteza de reparação ----------------------------------------
    if repair_uncertainty is not None and repair_uncertainty > t["max_repair_uncertainty"]:
        checks["repair_uncertainty"] = {
            "ok": False,
            "value": repair_uncertainty,
            "threshold": t["max_repair_uncertainty"],
        }
        reasons.append(
            f"incerteza de reparação {repair_uncertainty:.0%} > {t['max_repair_uncertainty']:.0%}"
        )
        verdicts.append("REVIEW")
    elif repair_uncertainty is not None:
        checks["repair_uncertainty"] = {
            "ok": True,
            "value": repair_uncertainty,
            "threshold": t["max_repair_uncertainty"],
        }

    # -- Gate: desconto implausível (too-good-is-a-trap) ----------------------
    if discount_pct is not None and discount_pct > t["max_discount_vs_market"]:
        checks["discount_plausibility"] = {
            "ok": False,
            "value": discount_pct,
            "threshold": t["max_discount_vs_market"],
        }
        reasons.append(
            f"desconto {discount_pct:.1f}% > {t['max_discount_vs_market']:.0f}% "
            "(barato demais é suspeito)"
        )
        verdicts.append("PASS")
    elif discount_pct is not None:
        checks["discount_plausibility"] = {
            "ok": True,
            "value": discount_pct,
            "threshold": t["max_discount_vs_market"],
        }

    # -- Gate: preço face ao max buy ------------------------------------------
    if asking_price and max_buy_price:
        if asking_price <= max_buy_price:
            checks["price_vs_max_buy"] = {
                "ok": True,
                "asking": asking_price,
                "max_buy": max_buy_price,
                "window_pct": 0.0,
            }
            verdicts.append("BUY")
        else:
            window = (asking_price - max_buy_price) / max_buy_price * 100.0
            in_window = window <= 10.0
            checks["price_vs_max_buy"] = {
                "ok": in_window,
                "asking": asking_price,
                "max_buy": max_buy_price,
                "window_pct": round(window, 2),
            }
            if in_window:
                reasons.append("pedido dentro da janela de negociação acima do max buy")
                verdicts.append("NEGOTIATE")
            else:
                reasons.append(
                    f"pedido {asking_price:.0f}€ excede max buy {max_buy_price:.0f}€"
                )
                verdicts.append("PASS")

    verdict = _worst(verdicts)
    return {
        "verdict": verdict,
        "checks": checks,
        "reasons": reasons,
    }
