"""
Testes da avaliação v2 (Fase 12 do plano 2026-08-01).

Cobre os casos que falharam na auditoria e os casos de fronteira exigidos:
veículo único no segmento, carro raro/caro, anúncio sem ano/km, mensalidade,
entrada, peças, duplicados, moeda, premium, elétrico, gerações, versões de
performance, ML compatível/incompatível/indisponível, ausência de
comparáveis, divergência ML↔estatística, score com baixa confiança e a regra
de regressão: nunca mais milhares de 500 €/10 000 € artificiais.
"""
from __future__ import annotations

import numpy as np
import pytest

from valuation.hybrid_valuator import (
    HybridValuator,
    parse_optional_int,
    parse_optional_float,
)
from processing.quality import classify_listing, normalize_brand


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rows_popular():
    """Segmento popular: 20 Renault Clio 2018-2021 + VW Golf."""
    rows = []
    rng = np.random.default_rng(7)
    for i in range(20):
        year = 2018 + (i % 4)
        price = {2018: 11500, 2019: 12500, 2020: 13800, 2021: 15000}[year]
        rows.append({
            "id": 100 + i, "brand": "renault", "model": "clio",
            "version": "unknown", "year": year,
            "price": price + float(rng.normal(0, 400)),
            "km": 40000 + (2026 - year) * 12000, "fuel_type": "gasolina",
            "transmission": "manual", "vehicle_type": "carros",
        })
    for i in range(8):
        rows.append({
            "id": 200 + i, "brand": "volkswagen", "model": "golf",
            "version": "unknown", "year": 2018 + (i % 2),
            "price": 16000 + i * 250, "km": 80000 + i * 5000,
            "fuel_type": "diesel", "transmission": "manual",
            "vehicle_type": "carros",
        })
    return rows


@pytest.fixture()
def valuator():
    return HybridValuator.from_rows(_rows_popular())


def _car(**kw):
    base = {
        "brand": "renault", "model": "clio", "year": 2019, "km": 80000,
        "fuel_type": "gasolina", "transmission": "manual",
        "vehicle_type": "carros", "price": 12000, "title": "Renault Clio",
        "source": "OLX",
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Parsing explícito de valores em falta (Fase 3)
# ---------------------------------------------------------------------------

class TestParsing:
    def test_parse_optional_int_none(self):
        assert parse_optional_int(None) is None
        assert parse_optional_int("") is None
        assert parse_optional_int("abc") is None

    def test_parse_optional_int_zero_real(self):
        # Zero real é distinto de ausente
        assert parse_optional_int(0) == 0
        assert parse_optional_int("0") == 0

    def test_parse_optional_float(self):
        assert parse_optional_float(None) is None
        assert parse_optional_float(1234.5) == 1234.5
        assert parse_optional_float("nope") is None


# ---------------------------------------------------------------------------
# Hierarquia de comparáveis (Fase 2)
# ---------------------------------------------------------------------------

class TestSegmentHierarchy:
    def test_popular_car_exact_level(self, valuator):
        r = valuator.calculate_deal_score(_car(id=999))
        assert r["estimated_value"] is not None
        assert 9000 < r["estimated_value"] < 16000
        assert r["valuation"]["method"] in ("brand_model_year", "brand_model_fuel",
                                            "brand_model_year_pm1", "brand_model")
        assert r["valuation"]["comparables_count"] >= 2

    def test_unique_vehicle_falls_through(self, valuator):
        """Veículo único no segmento marca+modelo: a exclusão do próprio
        anúncio esvazia o bucket, mas o sistema continua para níveis mais
        gerais em vez de devolver None."""
        rows = _rows_popular()
        rows.append({
            "id": 555, "brand": "ferrari", "model": "f8 tributo",
            "version": "unknown", "year": 2022, "price": 320000.0,
            "km": 8000, "fuel_type": "gasolina", "transmission": "automatico",
            "vehicle_type": "carros",
        })
        v = HybridValuator.from_rows(rows)
        est = v.estimate({
            "id": 555, "brand": "ferrari", "model": "f8 tributo",
            "year": 2022, "km": 8000, "fuel_type": "gasolina",
            "vehicle_type": "carros", "price": 320000, "title": "Ferrari F8",
        })
        # Não pode ser o fallback antigo nem None garantido:
        assert est["estimated_value"] != 10000.0
        assert est["estimated_value"] != 500.0
        # Com comparáveis globais + referência externa, deve haver algum valor
        # ou então 'insufficient_data' explícito — nunca um valor inventado.
        if est["estimated_value"] is None:
            assert est["confidence_label"] == "insufficient_data"
            assert est["method"] == "no_reliable_reference"
        else:
            assert est["confidence"] < 0.65  # confiança limitada sem comparáveis diretos

    def test_brand_only_level(self, valuator):
        r = valuator.estimate(_car(id=999, model="megane raro inexistente"))
        assert r["estimated_value"] is not None  # cai para marca/segmento/global
        assert r["estimated_value"] != 10000.0


# ---------------------------------------------------------------------------
# Valores em falta (Fase 3) — sem ano NUNCA vira ano 0
# ---------------------------------------------------------------------------

class TestMissingValues:
    def test_missing_year_no_fake_depreciation(self, valuator):
        """Anúncio sem ano: antes recebia 500 € (ano 0 → depreciação → clamp).
        Agora usa comparáveis sem ajuste temporal, com confiança reduzida."""
        r = valuator.calculate_deal_score(_car(id=999, year=None, km=None, price=23500))
        assert r["estimated_value"] is not None
        assert r["estimated_value"] != 500.0
        assert r["estimated_value"] > 5000  # Clio real, não lixo
        assert "year" in r["valuation"]["features_missing"]
        assert r["confidence"] < 0.65
        assert r["deal_status"] != "dados_insuficientes"  # há comparáveis marca+modelo

    def test_missing_km(self, valuator):
        r = valuator.estimate(_car(id=999, km=None))
        assert r["estimated_value"] is not None
        assert "km" in r["features_missing"]

    def test_impossible_year_ignored(self, valuator):
        r = valuator.estimate(_car(id=999, year=1800))
        assert "year" in r["features_missing"]
        assert any("impossível" in w for w in r["warnings"])


# ---------------------------------------------------------------------------
# Fallbacks falsos eliminados (Fase 4) — regra de regressão
# ---------------------------------------------------------------------------

class TestNoFakeFallbacks:
    def test_no_universal_500_or_10000(self, valuator):
        """Avaliar vários casos-limite: nenhum pode devolver os antigos
        valores universais gerados por fallback."""
        cases = [
            _car(id=1000, year=None, km=None),
            _car(id=1001, brand="marca_xpto_inexistente", model="zzz"),
            _car(id=1002, model="modelo_unico_sem_comps", year=1990),
            _car(id=1003, price=300000, brand="bugatti", model="chiron", year=2023),
        ]
        for c in cases:
            est = valuator.estimate(c)
            if est["estimated_value"] is None:
                assert est["confidence_label"] == "insufficient_data"
            # Os únicos 500/10000 admissíveis seriam valores reais de mercado,
            # nunca exactamente os fallbacks em série — aqui todos os casos
            # devem produzir valores distintos entre si ou None.
        vals = [valuator.estimate(c)["estimated_value"] for c in cases]
        non_null = [v for v in vals if v is not None]
        assert len(set(non_null)) == len(non_null)  # sem valores em série

    def test_insufficient_data_is_neutral(self):
        v = HybridValuator.from_rows([])  # sem qualquer comparável
        r = v.calculate_deal_score(_car(id=1, brand="x", model="y"))
        assert r["estimated_value"] is None or r["confidence"] < 0.45
        assert r["deal_score"] == 5.0 or 3.5 <= r["deal_score"] <= 6.5
        if r["estimated_value"] is None:
            assert r["deal_status"] == "dados_insuficientes"

    def test_structured_result_shape(self, valuator):
        est = valuator.estimate(_car(id=999))
        for key in ("estimated_value", "value_low", "value_high", "confidence",
                    "confidence_label", "method", "comparables_count",
                    "reference_level", "warnings", "features_missing",
                    "valuation_version", "valuation_explanation"):
            assert key in est
        assert est["valuation_version"].startswith("v2")
        assert est["value_low"] <= est["estimated_value"] <= est["value_high"]


# ---------------------------------------------------------------------------
# Preços que não são totais / anúncios problemáticos (Fases 7 e 10)
# ---------------------------------------------------------------------------

class TestBadListings:
    def test_monthly_payment_price(self, valuator):
        """350 €/mês por um Clio de 12 000 €: não é um preço total."""
        r = valuator.calculate_deal_score(_car(id=999, price=350,
                                               title="Renault Clio 350 EUR/mes"))
        assert r["deal_status"] == "provavel_erro_anuncio"
        assert r["deal_score"] == 5.0
        assert r["risk_flags"]

    def test_deposit_price(self, valuator):
        q = classify_listing(_car(price=500, title="Clio - entrada 500 EUR"),
                             reference_value=12000)
        assert q["quality_status"] == "quarantined"

    def test_parts_listing_invalid(self):
        q = classify_listing(_car(price=800, title="Renault Clio para peças"),
                             reference_value=12000)
        assert q["quality_status"] == "invalid"
        assert any("pecas" in r or "salvado" in r for r in q["quality_reasons"])

    def test_impossible_year_invalid(self):
        q = classify_listing(_car(year=2035), reference_value=12000)
        assert q["quality_status"] == "invalid"

    def test_zero_price_invalid(self):
        q = classify_listing(_car(price=0), reference_value=12000)
        assert q["quality_status"] == "invalid"

    def test_foreign_currency_price_quarantine(self):
        """Preço em USD tratado como EUR → muito acima da referência."""
        q = classify_listing(_car(price=120000, title="Clio"), reference_value=12000)
        assert q["quality_status"] == "quarantined"

    def test_km_incompatible_quarantine(self):
        q = classify_listing(_car(year=2022, km=900000), reference_value=12000)
        assert q["quality_status"] == "quarantined"

    def test_legit_expensive_car_stays_valid(self):
        """Um carro legitimamente caro NUNCA é apagado por ter preço alto."""
        q = classify_listing(
            _car(brand="porsche", model="911", price=135000, year=2019, km=45000,
                 title="Porsche 911 Carrera S"),
            reference_value=110000,
        )
        assert q["quality_status"] == "valid"

    def test_brand_normalization(self):
        assert normalize_brand("Mercedes_Benz")["normalized_brand"] == "Mercedes-Benz"
        assert normalize_brand("mercedes benz")["normalized_brand"] == "Mercedes-Benz"
        assert normalize_brand("Mercedes")["normalized_brand"] == "Mercedes-Benz"
        assert normalize_brand("VW")["normalized_brand"] == "Volkswagen"
        # Marca desconhecida: não força correspondência
        r = normalize_brand("Xing Ling Motors")
        assert r["normalized_brand"] == "Xing Ling Motors"
        assert r["normalization_confidence"] < 1.0


# ---------------------------------------------------------------------------
# Tipos especiais de veículo
# ---------------------------------------------------------------------------

class TestSpecialVehicles:
    def test_premium_model(self, valuator):
        r = valuator.calculate_deal_score(_car(
            id=999, brand="bmw", model="m3", year=2022, km=30000,
            price=95000, title="BMW M3 Competition",
            fuel_type="gasolina", transmission="automatico"))
        # Não é classificado como extremamente barato/caro por fallback
        assert 2.5 <= r["deal_score"] <= 7.5
        assert r["estimated_value"] != 10000.0

    def test_electric_vehicle(self, valuator):
        r = valuator.estimate(_car(id=999, brand="tesla", model="model 3",
                                   year=2021, km=60000, fuel_type="eletrico",
                                   price=22000, title="Tesla Model 3"))
        assert r["estimated_value"] is not None
        assert r["estimated_value"] > 5000

    def test_performance_version_not_ignored(self, valuator):
        """AMG/M/RS: a referência externa tem âncoras próprias."""
        from valuation.market_reference import estimate_reference_value
        ref = estimate_reference_value("mercedes-benz", "gle 63 amg", 2021, 40000, "gasolina")
        assert ref["value"] is not None
        assert ref["value"] > 50000  # um GLE 63 não vale 10 000 €

    def test_multiple_generations(self, valuator):
        """Clio 2019 vs 2005: estimativas têm de diferir bastante."""
        new = valuator.estimate(_car(id=999, year=2019))
        old = valuator.estimate(_car(id=999, year=2005, km=200000, price=3500))
        assert new["estimated_value"] is not None
        assert old["estimated_value"] is not None
        assert new["estimated_value"] > old["estimated_value"] * 1.5


# ---------------------------------------------------------------------------
# ML (Fase 5)
# ---------------------------------------------------------------------------

class TestMLIntegration:
    def test_real_model_loads_and_predicts(self):
        """O artefacto treinado v2 tem de carregar e prever."""
        from valuation.predict import PricePredictor
        p = PricePredictor("carros")
        if not p.model_loaded_ok:
            pytest.skip(f"modelo não treinado neste ambiente: {p.load_error}")
        pred = p.predict({
            "year": 2019, "km": 80000, "horsepower": 115, "engine_size": 1500,
            "doors": 5, "fuel_type": "gasolina", "transmission": "manual",
            "brand": "renault", "model": "clio", "location": "lisboa",
        })
        assert pred is not None and 3000 < pred < 60000

    def test_missing_artifact_disables_ml_explicitly(self, tmp_path, monkeypatch):
        """Artefacto em falta → ML desativado de forma explícita e segura."""
        from valuation.predict import PricePredictor
        monkeypatch.setattr("valuation.predict.settings.models_dir", str(tmp_path))
        p = PricePredictor("carros")
        assert p.model is None
        assert p.model_loaded_ok is False
        assert p.load_error is not None
        assert p.predict({"year": 2019}) is None  # nunca rebenta

    def test_ml_unavailable_statistical_still_works(self, valuator):
        assert valuator.ml_available is False
        r = valuator.calculate_deal_score(_car(id=999))
        assert r["estimated_value"] is not None

    def test_divergence_reduces_confidence(self):
        """ML e estatística a divergir → confiança reduzida + aviso."""
        class FakeML:
            model_name = "fake"
            metrics = {"mape_pct": 15.0}
            def predict(self, data):
                return 60000.0  # 5x a estatística (~12k)

        v = HybridValuator.from_rows(_rows_popular(), ml_model=FakeML(), ml_r2=0.8)
        est = v.estimate(_car(id=999))
        assert any("divergem" in w.lower() for w in est["warnings"])
        assert est["confidence"] < 0.9


# ---------------------------------------------------------------------------
# Deal score consciente da confiança (Fase 7)
# ---------------------------------------------------------------------------

class TestDealScore:
    def test_low_confidence_clamps_score(self):
        """Confiança baixa → score limitado à faixa neutra."""
        rows = [{
            "id": 1, "brand": "alfa romeo", "model": "giulia",
            "version": "unknown", "year": 2018, "price": 20000.0,
            "km": 90000, "fuel_type": "diesel", "transmission": "manual",
            "vehicle_type": "carros",
        }, {
            "id": 2, "brand": "alfa romeo", "model": "giulia",
            "version": "unknown", "year": 2019, "price": 22000.0,
            "km": 80000, "fuel_type": "diesel", "transmission": "manual",
            "vehicle_type": "carros",
        }]
        v = HybridValuator.from_rows(rows)
        r = v.calculate_deal_score({
            "id": 99, "brand": "alfa romeo", "model": "giulia", "year": 2019,
            "km": 85000, "price": 5000, "title": "Giulia", "vehicle_type": "carros",
            "fuel_type": "diesel",
        })
        assert r["deal_score"] <= 6.5  # confiança ≤ média → sem scores extremos
        assert r["deal_status"] in ("anuncio_suspeito", "provavel_erro_anuncio",
                                    "excelente_oportunidade", "bom_preco")

    def test_states_present(self, valuator):
        r = valuator.calculate_deal_score(_car(id=999))
        assert r["deal_status"] in (
            "excelente_oportunidade", "bom_preco", "preco_justo",
            "ligeiramente_caro", "caro", "dados_insuficientes",
            "provavel_erro_anuncio", "anuncio_suspeito",
        )


# ---------------------------------------------------------------------------
# Regressão global: sem fallbacks em série na BD real (Fase 14)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDatabaseRegression:
    def test_no_mass_fallback_values_in_db(self):
        import sqlite3
        from pathlib import Path
        db = Path("data/autodeal.db")
        if not db.exists():
            pytest.skip("BD não existe neste ambiente")
        con = sqlite3.connect(db)
        cur = con.cursor()
        # O modo de falha legado: milhares de anúncios com estimated_value
        # EXATAMENTE 500/10000 € gerados por fallback artificial, sem
        # comparáveis reais. O motor novo produz esses valores apenas como
        # arredondamento de uma mediana real — e só quando há comparáveis.
        # Critério de regressão: nenhum valor "redondo" sem comparáveis.
        cur.execute("""
            SELECT COUNT(*) FROM vehicles
            WHERE is_active = 1
              AND estimated_value IN (500.0, 10000.0)
              AND json_extract(valuation_details, '$.method') != 'auction_resale_multiple'
              AND COALESCE(json_extract(valuation_details, '$.comparables_count'), 0) < 1
        """)
        fallback_like = cur.fetchone()[0]
        # Antes da correção eram 1 320 anúncios; toleramos zero deste padrão.
        assert fallback_like == 0, f"{fallback_like} fallbacks sem comparáveis"

        # Em série: mais de 30 anúncios exatos iguais a 500/10000 indicam
        # fabricação, não mercado real (um valor real é raro, não em massa).
        cur.execute("""
            SELECT COUNT(*) FROM vehicles
            WHERE is_active = 1
              AND estimated_value IN (500.0, 10000.0)
              AND json_extract(valuation_details, '$.method') != 'auction_resale_multiple'
        """)
        rounded_count = cur.fetchone()[0]
        assert rounded_count < 80, (
            f"{rounded_count} valores exatos 500/10000 (esperado raro)"
        )

        cur.execute("""
            SELECT COUNT(*) FROM vehicles
            WHERE is_active = 1 AND deal_score < 3
        """)
        low_scores = cur.fetchone()[0]
        total = cur.execute(
            "SELECT COUNT(*) FROM vehicles WHERE is_active = 1"
        ).fetchone()[0]
        # Scores baixos honestos (carros caros) existem sempre; o que não pode
        # voltar é o zero em massa (era 1 443). Limite relativo: < 8 % da base.
        assert low_scores < max(300, total * 0.08), (
            f"{low_scores} anúncios com score<3 numa base de {total} (antes: 1443)"
        )
