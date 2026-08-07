"""Testes das portas de fiabilidade que travam as fugas de preço.

Cada teste corresponde a um modo de falha real encontrado em produção na
base ``data/autodeal.db`` (4 957 viaturas) — ver ``docs/auditoria_precos.md``.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import directo do ficheiro: valuation/__init__.py puxa sklearn/lightgbm e
# estes testes têm de correr sem o stack de ML instalado.
_spec = importlib.util.spec_from_file_location(
    "_reliability_under_test", os.path.join(_ROOT, "valuation", "reliability.py")
)
reliability = importlib.util.module_from_spec(_spec)
sys.modules["_reliability_under_test"] = reliability
_spec.loader.exec_module(reliability)

assess = reliability.assess
ConfidenceTier = reliability.ConfidenceTier
MAX_CREDIBLE_GAP_PCT = reliability.MAX_CREDIBLE_GAP_PCT


# ── Porta 1: sem preço retail não há profit ──────────────────────────────────

@pytest.mark.parametrize("price", [0, 0.0, None, -1])
def test_sem_preco_nao_gera_profit(price):
    """A fuga original: price=0 em leilões produzia profit = valor estimado.

    990 viaturas (AUTOLINE, LEILOSOC) somavam 5,4 M€ de lucro inexistente.
    """
    a = assess(price, estimated_value=25_000, n_comparables=40)
    assert a.credible_profit is None
    assert a.adjusted_estimated_value is None
    assert a.confidence == ConfidenceTier.NONE
    assert not a.is_publishable
    assert "sem_preco_retail" in a.reasons


def test_preco_de_leilao_nao_e_retail():
    """Base de leilão não é comparável com valor de mercado retail."""
    a = assess(5_000, estimated_value=25_000, n_comparables=40,
               price_is_retail=False)
    assert a.credible_profit is None
    assert "preco_nao_retail" in a.reasons


def test_sem_avaliacao_nao_gera_profit():
    a = assess(15_000, estimated_value=None, n_comparables=40)
    assert a.credible_profit is None
    assert "sem_avaliacao" in a.reasons


# ── Porta 2: shrinkage por densidade de comparáveis ──────────────────────────

def test_poucos_comparaveis_encolhem_o_lucro():
    """Com <3 comparáveis o MAPE medido é 24,6 % vs 6,9 % com 20+.

    O gap tem de ser fortemente descontado para não dominar o ranking.
    """
    thin = assess(10_000, estimated_value=13_000, n_comparables=1)
    dense = assess(10_000, estimated_value=13_000, n_comparables=40)

    assert thin.comparable_tier == "thin"
    assert dense.comparable_tier == "dense"
    # Mesmo gap bruto, lucro credível muito menor com poucos comparáveis.
    assert thin.credible_profit < dense.credible_profit
    assert thin.credible_profit < 0.35 * dense.credible_profit


def test_tier_denso_nao_e_encolhido():
    """O tier mais fiável é o piso de ruído: lambda = 1, sem desconto."""
    a = assess(10_000, estimated_value=12_000, n_comparables=50)
    assert a.shrink_lambda == pytest.approx(1.0)
    assert a.credible_profit == pytest.approx(2_000, abs=1.0)


def test_shrinkage_preserva_o_sinal_de_negocio():
    """Encolher nunca deve inverter o sinal do gap."""
    bom = assess(10_000, estimated_value=12_000, n_comparables=2)
    mau = assess(10_000, estimated_value=8_000, n_comparables=2)
    assert bom.credible_profit > 0
    assert mau.credible_profit < 0


# ── Porta 3: truncatura do gap incrível ──────────────────────────────────────

def test_gap_absurdo_e_truncado():
    """Gaps >50 % têm MAPE de 86 % — são erro, não negócio.

    O gap é truncado no máximo credível e o deal fica marcado como truncado —
    nunca é publicado como oportunidade real.
    """
    a = assess(10_000, estimated_value=14_000, n_comparables=50)
    assert a.capped is True
    assert a.adjusted_gap_pct == pytest.approx(MAX_CREDIBLE_GAP_PCT)
    assert a.credible_profit == pytest.approx(10_000 * MAX_CREDIBLE_GAP_PCT / 100)
    assert not a.is_publishable
    assert "gap_truncado" in " ".join(a.reasons)


def test_gap_normal_nao_e_truncado():
    a = assess(10_000, estimated_value=11_500, n_comparables=50)
    assert a.capped is False
    assert a.is_publishable


# ── Porta 3.5: gap bruto incrível → anúncio anómalo, nunca um negócio ─────────

def test_gap_bruto_incredivel_nao_e_publicavel():
    """BMW 320d 2015 a 5 000 € avaliado em 12 500 € (gap bruto 150 %).

    Preço abaixo de ~40 % do valor justo é fraude/salvado/peças/erro — mesmo
    com dezenas de comparáveis o profit tem de ser zero.
    """
    a = assess(5_000, estimated_value=12_500, n_comparables=15)
    assert a.capped is True
    assert a.credible_profit == 0.0
    assert not a.is_publishable
    assert any("gap_bruto_incredivel" in r for r in a.reasons)


def test_gap_bruto_limite_ainda_e_analisado():
    """Gap bruto de 40 % com comparáveis densos: shrink, cap, mas sem publicação."""
    a = assess(10_000, estimated_value=14_000, n_comparables=40)
    assert not a.is_publishable
    assert a.credible_profit > 0
    assert a.capped is True


# ── Publicabilidade ──────────────────────────────────────────────────────────

def test_deal_com_poucos_comparaveis_nao_e_publicavel():
    a = assess(10_000, estimated_value=13_000, n_comparables=1)
    assert not a.is_publishable
    assert "comparaveis_insuficientes" in a.reasons


def test_deal_solido_e_publicavel():
    a = assess(10_000, estimated_value=12_000, n_comparables=25)
    assert a.is_publishable
    assert a.confidence == ConfidenceTier.HIGH


def test_deal_sem_lucro_nao_e_publicavel():
    a = assess(10_000, estimated_value=9_000, n_comparables=25)
    assert not a.is_publishable


# ── Ajuste dos lambdas ───────────────────────────────────────────────────────

def test_fit_lambdas_desconta_mais_os_tiers_ruidosos():
    """Tiers com maior dispersão residual têm de receber lambda menor."""
    obs = []
    # tier denso: erro pequeno (±2 %)
    for i in range(200):
        noise = 0.02 * math.sin(i)
        obs.append((10_000.0, 10_000.0 * math.exp(noise), 30))
    # tier thin: erro grande (±40 %)
    for i in range(200):
        noise = 0.40 * math.sin(i)
        obs.append((10_000.0, 10_000.0 * math.exp(noise), 1))

    lambdas = reliability.fit_shrinkage_lambdas(obs)
    assert lambdas["dense"] == pytest.approx(1.0)
    assert lambdas["thin"] < 0.2


def test_fit_lambdas_ignora_dados_invalidos():
    """Preços a zero não podem entrar no ajuste."""
    obs = [(0, 10_000, 30), (None, 5_000, 1), (10_000, 0, 5)]
    lambdas = reliability.fit_shrinkage_lambdas(obs)
    assert lambdas == reliability.DEFAULT_LAMBDAS


# ── Regressão: a winner's curse ──────────────────────────────────────────────

def test_ranking_deixa_de_ser_dominado_por_dados_ralos():
    """Regressão do bug central: ordenar por gap bruto punha no topo as
    viaturas com menos comparáveis (63 % do top-100 tinha <3 comparáveis).
    """
    candidatos = [
        # (preço, valor estimado, comparáveis) — gap bruto idêntico de 40 %
        (10_000, 14_000, 1),    # dados ralos → provavelmente ruído
        (10_000, 14_000, 40),   # bem suportado → negócio provável
    ]
    resultados = [assess(p, e, n) for p, e, n in candidatos]
    ordenado = sorted(resultados, key=lambda a: -a.credible_profit)
    assert ordenado[0].comparables == 40, (
        "o deal bem suportado tem de ficar à frente do de dados ralos"
    )
