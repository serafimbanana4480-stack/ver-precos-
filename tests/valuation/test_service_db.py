"""Testes de integração contra a base real (data/autodeal.db).

Validam que os veículos-problema do enunciado deixam de produzir estimativas
falsas e que não há NaN/inf/valores fixos na saída.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from valuation.service import ValuationService, load_market_rows
from valuation.opportunity import OpportunityLabel


@pytest.fixture(scope="module")
def svc():
    rows = load_market_rows()
    return ValuationService.from_rows(rows), {r["id"]: r for r in rows}


def _eval(svc, by_id, vid):
    r = by_id.get(vid)
    if r is None:
        pytest.skip(f"id {vid} ausente")
    return svc.evaluate(r)


# Veículos do enunciado que NUNCA devem ter estimativa falsa.
PROBLEM_IDS = [5358, 4285, 4864, 5272, 2736, 5080, 695, 5106]


def test_no_fake_estimates_for_problem_vehicles(svc):
    s, by_id = svc
    for vid in PROBLEM_IDS:
        v = _eval(s, by_id, vid)
        e = v.estimate
        # Se a estimativa existe, tem de ter comparáveis e intervalo;
        # se não existe, a etiqueta é de insuficiência (nunca excelente).
        if e.value is not None:
            assert e.comparables_used >= 3
            assert e.low is not None and e.high is not None
        else:
            assert v.opportunity.label in (
                OpportunityLabel.INSUFFICIENT, OpportunityLabel.NEEDS_REVIEW,
                OpportunityLabel.SUSPICIOUS,
            )


def test_bmw_ix_duplicates_not_self_comparable(svc):
    s, by_id = svc
    # O grupo iX (476/588/704/2100) são anúncios distintos; nenhum deles
    # pode usar o seu próprio preço como comparável do outro (verificação
    # indireta: o número de comparáveis não inclui o próprio id).
    for vid in (476, 588, 704, 2100):
        v = _eval(s, by_id, vid)
        used_ids = {c.id for c in v.estimate.used}
        assert vid not in used_ids


def test_mercedes_amg_not_base(svc):
    s, by_id = svc
    v = _eval(s, by_id, 5358)  # A 35 AMG
    assert v.canonical["performance_class"] == "performance"
    assert "classe a" in v.canonical["comparability_key"]

def test_no_nan_in_any_derived_field(svc):
    s, by_id = svc
    for vid in list(by_id)[:200]:
        v = s.evaluate(by_id[vid])
        out = v.derived_fields()
        assert out["valuation_details"] is not None
        # json_safe converte NaN/inf em None; o texto serializado não os contém.
        import json as _json
        safe = _json.dumps(out, default=str)
        assert "NaN" not in safe and "Infinity" not in safe


def test_overpriced_vehicle_never_excellent(svc):
    s, by_id = svc
    # Encontrar um anúncio cujo preço esteja acima do limite superior.
    for vid, r in by_id.items():
        v = s.evaluate(r)
        e = v.estimate
        if e.value is None or e.high is None or r["price"] is None:
            continue
        if r["price"] > e.high * 1.1:
            assert v.opportunity.label != OpportunityLabel.EXCELLENT
            assert not v.opportunity.is_opportunity
            return
    pytest.skip("nenhum sobrepreço encontrado no topo")


def test_coverage_reasonable(svc):
    """Pelo menos 40% dos anúncios ativos devem ter estimativa coerente."""
    s, by_id = svc
    n = len(by_id)
    with_est = sum(1 for r in by_id.values() if s.evaluate(r).estimate.value is not None)
    assert with_est / n >= 0.40, f"cobertura {with_est/n:.1%} abaixo de 40%"
