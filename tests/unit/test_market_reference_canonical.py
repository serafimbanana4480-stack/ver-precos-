"""Regressão do matching canónico de âncoras de referência.

Protege o fix da auditoria 2026-07-31 §2.1: anúncios reais dizem
"BMW 320d"/"Mercedes C220" e as âncoras são nameplates ("bmw serie 3",
"mercedes-benz classe c"). Sem o gate do token de marca, o fuzzy match
mandava "bmw 320d" para "bmw x1" com confiança 0.6 — contaminando
referência, sanity check e deal score.
"""
from __future__ import annotations

import pytest

from valuation.market_reference import (
    _canonical_key,
    estimate_reference_value,
    find_model_entry,
)


class TestCanonicalKey:
    @pytest.mark.parametrize(
        "model,expected",
        [
            ("320d", "bmw serie 3"),
            ("318i", "bmw serie 3"),
            ("330e", "bmw serie 3"),
            ("116d", "bmw serie 1"),
            ("520d", "bmw serie 5"),
            ("740i", "bmw serie 7"),
        ],
    )
    def test_bmw_numeric_badges_map_to_series(self, model, expected):
        assert _canonical_key("bmw", model) == expected

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("c220", "mercedes-benz classe c"),
            ("c220 cdi", "mercedes-benz classe c"),
            ("e220d", "mercedes-benz classe e"),
            ("a180", "mercedes-benz classe a"),
            ("s500", "mercedes-benz classe s"),
        ],
    )
    def test_mercedes_badges_map_to_class(self, model, expected):
        assert _canonical_key("mercedes-benz", model) == expected

    def test_cross_brand_never_matches(self):
        """Um badge BMW não pode resolver para Mercedes e vice-versa."""
        assert _canonical_key("bmw", "c220") is None
        assert _canonical_key("mercedes-benz", "320d") is None

    def test_unknown_models_return_none(self):
        assert _canonical_key("renault", "clio") is None
        assert _canonical_key("bmw", "") is None


class TestAnchorResolution:
    """O alias tem de chegar à entrada certa com confiança alta."""

    @pytest.mark.parametrize(
        "brand,model,anchor",
        [
            ("BMW", "320d", "bmw serie 3"),
            ("bmw", "530e", "bmw serie 5"),
            ("Mercedes-Benz", "C220", "mercedes-benz classe c"),
            ("mercedes", "E220d", "mercedes-benz classe e"),
        ],
    )
    def test_trim_badge_hits_right_nameplate(self, brand, model, anchor):
        entry, matched, conf = find_model_entry(brand, model)
        assert entry is not None
        assert matched == anchor
        assert conf >= 0.85

    @pytest.mark.parametrize(
        "brand,model",
        [
            ("Renault", "Master"),
            ("Peugeot", "Boxer"),
            ("Fiat", "Ducato"),
            ("Toyota", "Proace"),
            ("Volkswagen", "Caddy"),
        ],
    )
    def test_commercial_anchors_exist(self, brand, model):
        """Comerciais ligeiros adicionados ao leque de âncoras (2026)."""
        entry, matched, conf = find_model_entry(brand, model)
        assert entry is not None, f"âncora em falta: {brand} {model}"
        assert conf >= 0.9


class TestReferenceValuesAreRealistic:
    def test_bmws_320d_valuation_is_sane(self):
        result = estimate_reference_value(
            "BMW", "320d", 2020, 80000, "diesel", "carros"
        )
        value = result.get("value")
        assert value is not None
        # Mercado PT 2026: um 320d de 2020 com 80k km não custa menos de 12k
        # nem mais de 45k.
        assert 12000 <= value <= 45000

    def test_commercial_van_valuation_is_sane(self):
        result = estimate_reference_value(
            "Renault", "Master", 2019, 150000, "diesel", "carros"
        )
        value = result.get("value")
        assert value is not None
        assert 6000 <= value <= 40000
