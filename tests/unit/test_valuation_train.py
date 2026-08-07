"""
Testes do pipeline de treino v2 (rápido: carregamento de dados e integridade
dos artefactos já treinados — o treino completo corre em `main.py train`).
"""
import json
from pathlib import Path

import pytest

from valuation.train_v2 import load_training_frame
from valuation.feature_store import FeatureStore


def test_load_training_frame_excludes_auctions():
    df = load_training_frame("carros")
    if df.empty:
        pytest.skip("sem dados de treino neste ambiente")
    assert (df["price"] > 300).all()
    assert df["year"].notna().all()
    # Ordenação temporal (splits sem leakage)
    assert df["first_seen"].is_monotonic_increasing


def test_feature_store_all_features_used():
    """O pipeline v2 usa SEMPRE todas as features permitidas (sem seleção
    que cause skew treino/inferência)."""
    fs = FeatureStore()
    fs.build_brand_index(["renault"])
    fs.build_model_index(["clio"])
    feats = fs.compute_features({"year": 2019, "km": 80000, "brand": "renault",
                                 "model": "clio", "fuel_type": "gasolina"})
    for col in FeatureStore.ALLOWED_FEATURES:
        assert col in feats


def test_trained_artifacts_consistent():
    """Metadados, artefacto e features têm de estar alinhados."""
    meta_path = Path("models/best_model_carros.json")
    if not meta_path.exists():
        pytest.skip("modelo não treinado neste ambiente")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert (Path("models") / meta["model_path"]).exists(), "artefacto do modelo em falta"
    assert meta.get("pipeline_version") == "v2"
    assert meta["feature_names"] == FeatureStore.ALLOWED_FEATURES
    assert meta["metrics"]["r2"] > 0.3
