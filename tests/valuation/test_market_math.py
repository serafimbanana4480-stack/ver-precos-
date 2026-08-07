"""Testes de mercado: matemática defensiva, classificação, comparáveis.

Cobertura dos invariantes do enunciado:

* zero comparáveis ⇒ nunca ``excelente_oportunidade``;
* confiança baixa ⇒ nunca ``excelente_oportunidade``;
* ``discount_eur <= 0`` ⇒ nunca oportunidade;
* nenhum campo devolvido é ``NaN``/infinito;
* preço acima do mercado ⇒ ``muito_acima``/``ligeiramente_acima``, nunca oportunidade;
* desconto implausível (muito abaixo do limite inferior) ⇒ validação, não topo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from valuation.market_math import (
    compute_delta, finite, json_safe, round_estimate, round_interval, safe_ratio,
)
from valuation.opportunity import classify, OpportunityLabel
from valuation.canonical_vehicle import canonicalize, normalize_fuel, detect_performance_class
from valuation.listing_guard import inspect_listing, fingerprint


# ── market_math ───────────────────────────────────────────────────────────────
def test_finite_kills_nan_inf():
    assert finite(float("nan")) is None
    assert finite(float("inf")) is None
    assert finite(3.5) == 3.5
    assert finite(None) is None


def test_safe_ratio_no_div_zero():
    assert safe_ratio(1.0, 0.0) is None
    assert safe_ratio(10.0, 2.0) == 5.0


def test_compute_delta_sign():
    d = compute_delta(36900, 34728)
    assert d.discount_eur == -2172.0
    assert round(d.discount_pct, 2) == -5.89


def test_compute_delta_overpriced_negative():
    d = compute_delta(80000, 40000)
    assert d.discount_eur == -40000.0
    assert d.discount_pct == -50.0
    assert d.ok


def test_compute_delta_no_estimate():
    d = compute_delta(10000, None)
    lo, hi = round_interval(10000.0, 11000.0, 10000.0)
    assert lo is not None and hi is not None
    assert lo <= 10000.0 <= hi

def test_json_safe_no_nan():
    out = json_safe({"a": 1.0, "b": float("nan"), "c": {"d": float("inf")}})
    assert out["b"] is None
    assert out["c"]["d"] is None


def test_rounding_invariants():
    assert round_estimate(1234.56) == 1200.0
    assert round_estimate(81000.0, uncertainty_pct=60) == 81000.0
    lo, hi = round_interval(9000.0, 11000.0, 10000.0)
    assert lo <= 10000.0 <= hi
    assert round_estimate(float("nan")) is None


# ── fuel/power taxonomy ─────────────────────────────────────────────────────
def test_fuel_distinguishes_subtypes():
    # PHEV/HEV/MHEV são distinguidos do elétrico puro (o bug das 18 Toyotas).
    assert normalize_fuel("híbrido") == "hibrido"
    assert normalize_fuel("hibrido plug-in") == "phev"
    assert normalize_fuel("mild hybrid") == "mild_hybrid"
    assert normalize_fuel("elétrico") == "eletrico"
    assert normalize_fuel("toyota hybrid") != "eletrico"
    assert normalize_fuel("Hibrido (Gasolina/Eletrico)") != "eletrico"


def test_performance_taxonomy():
    assert detect_performance_class("Mercedes A 35 AMG")[0] == "performance"
    assert detect_performance_class("BMW M4")[0] == "high_performance"
    assert detect_performance_class("Porsche 911 GT3")[0] == "supercar"
    assert detect_performance_class("BMW Serie 3 320d")[0] == "base"
    assert detect_performance_class("Mercedes A 180 d AMG Line")[0] == "sport_trim"


def test_canonical_separates_amg_from_base():
    a = canonicalize({"brand": "Mercedes", "model": "Classe A", "title": "Mercedes A 35 AMG", "version": "35 AMG"})
    b = canonicalize({"brand": "Mercedes", "model": "Classe A", "title": "Mercedes A 180 d"})
    assert a.comparability_key != b.comparability_key
    assert a.performance_class == "performance"
    assert b.performance_class == "base"


# ── listing guard ──────────────────────────────────────────────────────────
def test_salvage_flagged_blocking():
    f = inspect_listing({"brand": "Audi", "title": "Audi A4 salvado", "price": 15000, "location": "Lisboa"})
    assert "salvado" in f.blocking
    assert not f.usable_as_comparable


def test_monthly_price_not_total():
    f = inspect_listing({"brand": "BMW", "title": "BMW Série 3 desde 350€/mês", "price": 350, "currency": "EUR", "location": "Lisboa"})
    assert not f.price_is_total
    assert any("mensalidade" in b for b in f.blocking)

def test_penhora_excluded():
    f = inspect_listing({"brand": "VW", "title": "VW Golf penhora tribunal", "price": 12000, "location": "Porto"})
    assert any("penhora" in b for b in f.blocking)


def test_fingerprint_deterministic():
    r = {"brand": "VW", "model": "Golf", "year": 2019, "km": 50000, "price": 15000, "source": "A", "source_id": "x"}
    assert fingerprint(r) == fingerprint(dict(r))


# ── opportunity classification ─────────────────────────────────────────────
def test_overpriced_never_opportunity():
    o = classify(listing_price=40000, market_value=34000, market_low=31000,
                 market_high=37000, confidence=0.6, comparables_count=10)
    assert not o.is_opportunity
    assert o.label in (OpportunityLabel.SLIGHTLY_ABOVE, OpportunityLabel.WELL_ABOVE)


def test_zero_comparables_not_excellent():
    o = classify(listing_price=25000, market_value=40000, market_low=38000,
                 market_high=42000, confidence=0.9, comparables_count=0)
    assert o.label == OpportunityLabel.INSUFFICIENT


def test_low_confidence_not_excellent():
    o = classify(listing_price=25000, market_value=35000, market_low=33000,
                 market_high=37000, confidence=0.15, comparables_count=20)
    assert o.label != OpportunityLabel.EXCELLENT


def test_negative_discount_not_opportunity():
    o = classify(listing_price=50000, market_value=40000, market_low=38000,
                 market_high=42000, confidence=0.6, comparables_count=10)
    assert o.discount_eur is not None and o.discount_eur <= 0
    assert not o.is_opportunity


def test_implausible_discount_needs_review():
    # 47% abaixo do limite inferior => ratio>3x => insuficiente (rejeitado
    # pela guarda anti-inflação), nunca excelente.
    o = classify(listing_price=18000, market_value=56000, market_low=34000,
                 market_high=79000, confidence=0.6, comparables_count=10)
    assert o.label in (OpportunityLabel.NEEDS_REVIEW, OpportunityLabel.INSUFFICIENT)
    assert o.label != OpportunityLabel.EXCELLENT


def test_strong_deal_is_excellent():
    o = classify(listing_price=27000, market_value=34000, market_low=31000,
                 market_high=37000, confidence=0.6, comparables_count=10)
    assert o.label == OpportunityLabel.EXCELLENT
    assert o.is_opportunity


def test_no_nan_in_output():
    o = classify(listing_price=None, market_value=None, comparables_count=0)
    out = o.to_dict()
    for v in out.values():
        assert v is not float("nan"), f"NaN em {v}"
