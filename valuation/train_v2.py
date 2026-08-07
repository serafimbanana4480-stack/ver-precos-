"""
Pipeline de treino ML v2 (2026-08-01).

Corrige as falhas encontradas na auditoria:

* **Skew treino/inferência**: usa SEMPRE as 18 features do FeatureStore, sem
  seleção L1/KBest que alterava as colunas entre treino e inferência.
* **Artefactos incoerentes**: grava modelo + scaler + brand index + metadados
  de forma atómica e faz validação round-trip (recarrega o artefacto gravado
  e confirma que produz previsões com o número certo de features).
* **Leakage**: exclui fontes de leilão (preços ~8x abaixo do retalho),
  remove duplicados exatos e usa divisão temporal (ordenado por first_seen).
* **Comparação honesta**: XGBoost, LightGBM, CatBoost, RandomForest,
  ExtraTrees e regressão robusta (Huber) com TimeSeriesSplit; métricas
  globais + erro por faixa de preço (estabilidade por segmento).

Alvo: log1p(preço) — distribuições de preços são assimétricas; a inferência
faz expm1 (``full_log_target: true`` nos metadados).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from core.settings import settings
from valuation.feature_store import FeatureStore
from valuation.hybrid_valuator import AUCTION_SOURCES

logger = logging.getLogger(__name__)

MIN_R2_SAVE = 0.30


def _val_str(val) -> str:
    if val is None:
        return "unknown"
    if hasattr(val, "value"):
        return val.value
    return str(val)


def load_training_frame(vehicle_type: str = "carros") -> pd.DataFrame:
    """Carrega dados de treino limpos: sem leilões, sem preços absurdos,
    sem duplicados exatos, ordenado temporalmente."""
    from database.db import get_db_context
    from database.models import Vehicle, VehicleType

    with get_db_context() as db:
        query = db.query(Vehicle).filter(
            Vehicle.vehicle_type == VehicleType(vehicle_type),
            Vehicle.is_active == True,  # noqa: E712
            Vehicle.quality_status.in_(("valid", "valid_with_warning")),
            Vehicle.price_kind == "total",
            Vehicle.currency == "EUR",
            Vehicle.price > 300,
            Vehicle.price < 400000,
            Vehicle.year.isnot(None),
            Vehicle.year >= 1970,
            Vehicle.year <= datetime.now().year + 1,
        )
        if vehicle_type == "carros":
            query = query.filter(Vehicle.km.isnot(None), Vehicle.km >= 0)
        rows = query.all()

        records = []
        for v in rows:
            src = _val_str(v.source)
            if src in AUCTION_SOURCES:
                continue  # preços de leilão não são retalho
            records.append({
                "year": v.year, "km": v.km or 0,
                "horsepower": v.horsepower or 0, "engine_size": v.engine_size or 0,
                "doors": v.doors or 4,
                "fuel_type": _val_str(v.fuel_type),
                "transmission": _val_str(v.transmission),
                "brand": v.brand or "Unknown",
                "model": v.model or "",
                "location": v.location or "",
                "district": v.district or "",
                "price": float(v.price),
                "first_seen": v.first_seen,
            })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Dedupe: mesmo veículo republicado (marca/modelo/ano/km/preço iguais)
    before = len(df)
    df = df.drop_duplicates(subset=["brand", "model", "year", "km", "price"])
    logger.info("Dedupe: %d -> %d linhas", before, len(df))

    # Ordenação temporal para splits sem leakage
    df = df.sort_values("first_seen").reset_index(drop=True)
    logger.info("Loaded %d training rows for %s", len(df), vehicle_type)
    return df


def _make_candidates() -> Dict[str, Any]:
    cands: Dict[str, Any] = {}

    import xgboost as xgb
    cands["xgboost"] = xgb.XGBRegressor(
        n_estimators=600, max_depth=7, learning_rate=0.04,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
        reg_lambda=2.0, reg_alpha=1.0, random_state=42, n_jobs=-1,
    )
    try:
        import lightgbm as lgb
        cands["lightgbm"] = lgb.LGBMRegressor(
            n_estimators=600, max_depth=7, learning_rate=0.04,
            subsample=0.8, colsample_bytree=0.8, min_child_samples=5,
            reg_lambda=2.0, reg_alpha=1.0, random_state=42, verbose=-1, n_jobs=-1,
        )
    except ImportError:
        logger.warning("LightGBM não instalado")
    try:
        from catboost import CatBoostRegressor
        cands["catboost"] = CatBoostRegressor(
            iterations=600, depth=7, learning_rate=0.04,
            subsample=0.8, random_seed=42, verbose=False, l2_leaf_reg=2.0,
        )
    except ImportError:
        logger.warning("CatBoost não instalado")

    cands["random_forest"] = RandomForestRegressor(
        n_estimators=200, max_depth=18, min_samples_leaf=2,
        random_state=42, n_jobs=-1,
    )
    cands["extra_trees"] = ExtraTreesRegressor(
        n_estimators=200, max_depth=18, min_samples_leaf=2,
        random_state=42, n_jobs=-1,
    )
    cands["huber"] = HuberRegressor(max_iter=400)
    return cands


def _error_by_band(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """MAPE por faixa de preço — estabilidade por segmento."""
    bands = [(0, 5000), (5000, 15000), (15000, 30000), (30000, 60000), (60000, 1e9)]
    out = {}
    for lo, hi in bands:
        mask = (y_true >= lo) & (y_true < hi)
        if mask.sum() >= 5:
            ape = np.abs(y_true[mask] - y_pred[mask]) / np.maximum(y_true[mask], 1)
            out[f"mape_{int(lo/1000)}k_{'60k+' if hi > 1e8 else str(int(hi/1000)) + 'k'}"] = round(float(ape.mean() * 100), 1)
            out[f"n_{int(lo/1000)}k"] = int(mask.sum())
    return out


def _feature_matrix(frame: pd.DataFrame, fs: FeatureStore, feature_cols) -> np.ndarray:
    rows = [fs.compute_features(r) for r in frame.to_dict("records")]
    return np.array([[f.get(c, 0.0) for c in feature_cols] for f in rows], dtype=float)


def _evaluate(model, frame: pd.DataFrame, feature_cols, tscv) -> Dict[str, float]:
    """Evaluate without fitting encoders/scaler on future rows.

    The previous implementation fitted the StandardScaler and categorical
    indexes on the complete frame before TimeSeriesSplit. That did not expose
    the target directly, but it still leaked future distribution information
    into each validation fold.
    """
    r2s, maes, mapes, rmses, medaes = [], [], [], [], []
    band_metrics: Dict[str, list] = {}
    y = frame["price"].to_numpy(dtype=float)
    y_log = np.log1p(y)
    for tr, te in tscv.split(frame):
        fs = FeatureStore()
        fs.build_brand_index(frame.iloc[tr]["brand"].tolist())
        fs.build_model_index(frame.iloc[tr]["model"].tolist())
        x_train = _feature_matrix(frame.iloc[tr], fs, feature_cols)
        x_test = _feature_matrix(frame.iloc[te], fs, feature_cols)
        scaler = StandardScaler().fit(x_train)
        model.fit(scaler.transform(x_train), y_log[tr])
        pred = np.expm1(model.predict(scaler.transform(x_test)))
        pred = np.maximum(pred, 0)
        true = y[te]
        r2s.append(r2_score(true, pred))
        abs_err = np.abs(true - pred)
        maes.append(abs_err.mean())
        medaes.append(np.median(abs_err))
        rmses.append(float(np.sqrt(mean_squared_error(true, pred))))
        mapes.append(float((abs_err / np.maximum(true, 1)).mean() * 100))
        for k, v in _error_by_band(true, pred).items():
            band_metrics.setdefault(k, []).append(v)
    return {
        "r2": float(np.mean(r2s)),
        "mae": float(np.mean(maes)),
        "median_ae": float(np.mean(medaes)),
        "rmse": float(np.mean(rmses)),
        "mape_pct": float(np.mean(mapes)),
        **{k: round(float(np.mean(v)), 1) if not k.startswith("n_") else int(np.sum(v))
           for k, v in band_metrics.items()},
    }


def _save_artifacts(best_name: str, model, scaler, fs: FeatureStore,
                    feature_cols, metrics: Dict, n_samples: int,
                    vehicle_type: str) -> Path:
    """Grava artefactos de forma atómica + validação round-trip."""
    model_dir = Path(settings.models_dir)
    model_dir.mkdir(exist_ok=True)

    ext_map = {"xgboost": "json", "lightgbm": "txt", "catboost": "cbm",
               "random_forest": "joblib", "extra_trees": "joblib", "huber": "joblib"}
    ext = ext_map.get(best_name, "joblib")
    model_path = model_dir / f"model_{vehicle_type}.{ext}"
    tmp_path = model_dir / f".tmp_model_{vehicle_type}.{ext}"

    if best_name == "xgboost":
        model.save_model(str(tmp_path))
    elif best_name == "lightgbm":
        model.booster_.save_model(str(tmp_path))
    elif best_name == "catboost":
        model.save_model(str(tmp_path))
    else:
        dump(model, str(tmp_path))
    os.replace(tmp_path, model_path)

    dump(scaler, str(model_dir / f"scaler_{vehicle_type}.joblib"))
    fs.save_index(model_dir / f"brand_index_{vehicle_type}.json")

    import sklearn, xgboost
    metadata = {
        "model_type": best_name,
        "model_path": model_path.name,
        "scaler_path": f"scaler_{vehicle_type}.joblib",
        "brand_index_path": f"brand_index_{vehicle_type}.json",
        "vehicle_type": vehicle_type,
        "feature_names": list(feature_cols),
        "full_log_target": True,
        "metrics": metrics,
        "n_samples": n_samples,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "excludes_auctions": list(AUCTION_SOURCES),
        "pipeline_version": "v2",
        "library_versions": {
            "xgboost": xgboost.__version__,
            "sklearn": sklearn.__version__,
        },
    }
    meta_tmp = model_dir / f".tmp_best_model_{vehicle_type}.json"
    with open(meta_tmp, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    os.replace(meta_tmp, model_dir / f"best_model_{vehicle_type}.json")

    # ---- validação round-trip: recarrega como produção faria ----
    from valuation.predict import PricePredictor
    check = PricePredictor(vehicle_type)
    if not check.model_loaded_ok:
        raise RuntimeError(f"Round-trip falhou: {check.load_error}")
    probe = check.predict({"year": 2019, "km": 80000, "horsepower": 150,
                           "engine_size": 2000, "doors": 5, "fuel_type": "diesel",
                           "transmission": "manual", "brand": "volkswagen",
                           "model": "golf", "location": "lisboa"})
    if not probe or probe <= 0:
        raise RuntimeError(f"Round-trip produziu previsão inválida: {probe}")
    logger.info("Round-trip OK: previsão de teste = €%.0f", probe)
    return model_dir / f"best_model_{vehicle_type}.json"


def train_model_v2(vehicle_type: str = "carros") -> Optional[Dict[str, Any]]:
    df = load_training_frame(vehicle_type)
    if len(df) < settings.ml_min_samples:
        logger.warning("Apenas %d amostras para %s (mín. %s)",
                       len(df), vehicle_type, settings.ml_min_samples)
        return None

    feature_cols = list(FeatureStore.ALLOWED_FEATURES)
    fs = FeatureStore()
    fs.build_brand_index(df["brand"].tolist())
    fs.build_model_index(df["model"].tolist())

    X = _feature_matrix(df, fs, feature_cols)
    y = df["price"].values.astype(float)
    mask = y > 0
    X, y = X[mask], y[mask]
    y_log = np.log1p(y)

    tscv = TimeSeriesSplit(n_splits=5)
    results: Dict[str, Dict[str, float]] = {}
    models = _make_candidates()
    trained: Dict[str, Any] = {}

    for name, model in models.items():
        try:
            metrics = _evaluate(model, df, feature_cols, tscv)
            results[name] = metrics
            trained[name] = model
            logger.info(
                "%-14s R²=%.4f MAE=€%.0f MedAE=€%.0f RMSE=€%.0f MAPE=%.1f%%",
                name, metrics["r2"], metrics["mae"], metrics["median_ae"],
                metrics["rmse"], metrics["mape_pct"],
            )
        except Exception as e:
            logger.error("%s falhou na avaliação: %s: %s", name, type(e).__name__, e)

    if not results:
        logger.error("Nenhum modelo avaliado com sucesso")
        return None

    best_name = max(results, key=lambda k: results[k]["r2"])
    best_metrics = results[best_name]
    logger.info("Melhor modelo: %s (R²=%.4f)", best_name, best_metrics["r2"])
    for k, v in best_metrics.items():
        if k.startswith("mape_"):
            logger.info("  %s: %s", k, v)

    if best_metrics["r2"] < MIN_R2_SAVE:
        logger.warning(
            "R²=%.3f abaixo do mínimo %.2f — artefactos NÃO gravados; "
            "a componente ML fica desativada e o sistema usa estatística+referência.",
            best_metrics["r2"], MIN_R2_SAVE,
        )
        return {"status": "below_threshold", "results": results}

    # Treino final em todos os dados
    best_model = trained[best_name]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    best_model.fit(X_scaled, y_log)

    meta_path = _save_artifacts(
        best_name, best_model, scaler, fs, feature_cols,
        best_metrics, len(df), vehicle_type,
    )
    logger.info("Artefactos gravados: %s", meta_path)
    return {"status": "ok", "best": best_name, "metrics": best_metrics, "results": results}


def train_all(force: bool = False) -> Dict[str, Optional[Dict[str, Any]]]:
    out = {}
    for vtype in ("carros", "motos"):
        logger.info("=== Treino %s ===", vtype)
        metadata = Path(settings.models_dir) / f"best_model_{vtype}.json"
        if metadata.exists() and not force:
            out[vtype] = {"status": "skipped_existing", "metadata": str(metadata)}
        else:
            out[vtype] = train_model_v2(vtype)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    res = train_all(force=True)
    print(json.dumps({k: (v.get("best"), v.get("metrics")) if v and v.get("status") == "ok" else v
                      for k, v in res.items()}, indent=2, default=str))
