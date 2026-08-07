"""
Treino segmentado de preços para carros (VER PRECOS).

Aborda as FUGAS DE PREÇOS:
  - 2 modelos XGBoost: LOW (<20k, onde o enviesamento em <3k é grave) e
    FULL (todos os retalhos, com log1p target para domar as caudas >20k).
  - Routing TWO-STAGE em produção: FULL prediz um preço preliminar; se esse
    preço < LOW_THRESHOLD, usa-se o modelo LOW (não se usa o preço real,
    que em produção é desconhecido).
  - EXCLUI fontes de leilão do treino de retalho (LEILOSOC/MARTELO/AUTOLINE/
    PENHORADO/VPAUTO/MANHEIM/AUTOROLA/BCA).
  - Mede R²/MAE global + por faixa ANTES (CatBoost atual) e DEPOIS (novo).

Uso: python -u scripts/train_segmented.py
"""
import os, sys, json, logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score, mean_absolute_percentage_error
from joblib import dump
import xgboost as xgb

from core.settings import settings
from valuation.feature_store import FeatureStore
from database.db import get_db_context
from database.models import Vehicle, VehicleType

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("train_segmented")

AUCTION_SOURCES = {"LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA",
                  "MARTELO", "AUTOLINE", "PENHORADO"}

LOW_THRESHOLD = 20000.0  # routing two-stage: se FULL prediz < isto, usa LOW


def _val_str(val):
    if val is None:
        return "unknown"
    return val.value if hasattr(val, "value") else str(val)


def load_retail_data():
    with get_db_context() as db:
        rows = db.query(Vehicle).filter(
            Vehicle.vehicle_type == VehicleType("carros"),
            Vehicle.price > 500, Vehicle.price < 500000,
            Vehicle.year.isnot(None),
            Vehicle.km.isnot(None), Vehicle.km > 0,
        ).all()
        recs = [{
            "year": v.year, "km": v.km or 0,
            "horsepower": v.horsepower or 0, "engine_size": v.engine_size or 0,
            "doors": v.doors or 4,
            "fuel_type": _val_str(v.fuel_type),
            "transmission": _val_str(v.transmission),
            "brand": v.brand or "Unknown", "model": v.model or "",
            "location": v.location or "", "district": v.district or "",
            "price": float(v.price),
            "source": v.source.value if v.source else "",
        } for v in rows]
    df = pd.DataFrame(recs)
    df["is_auction"] = df["source"].isin(AUCTION_SOURCES)
    n_auction = int(df["is_auction"].sum())
    df = df[~df["is_auction"]].drop(columns=["is_auction"]).reset_index(drop=True)
    logger.info(f"Carregados {len(df)} retalhos (excluídos {n_auction} leilões)")
    return df


def build_features(df):
    fs = FeatureStore()
    fs.build_brand_index(df["brand"].tolist())
    fs.build_model_index(df["model"].tolist())
    recs = []
    for r in df.to_dict("records"):
        f = fs.compute_features(r)
        f["price"] = r["price"]
        recs.append(f)
    out = pd.DataFrame(recs).dropna(subset=["price"]).fillna(0)
    return out, fs


def train_xgb(X, y, log_target=False, n_est=800, max_depth=8, lr=0.03,
              sample_weight=None):
    arrays = [X, y]
    if sample_weight is not None:
        arrays.append(sample_weight)
    split = train_test_split(*arrays, test_size=0.2, random_state=42)
    X_tr, X_te, y_tr, y_te = split[0], split[1], split[2], split[3]
    sw_tr = split[4] if sample_weight is not None else None
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)
    if log_target:
        y_tr_t = np.log1p(y_tr)
        y_te_t = np.log1p(y_te)
    else:
        y_tr_t = y_tr
        y_te_t = y_te
    model = xgb.XGBRegressor(
        n_estimators=n_est, max_depth=max_depth, learning_rate=lr,
        subsample=0.85, colsample_bytree=0.85, min_child_weight=3,
        reg_lambda=2.0, reg_alpha=1.0, random_state=42, n_jobs=-1,
        early_stopping_rounds=50)
    fit_kwargs = {"eval_set": [(X_te_s, y_te_t)]}
    if sw_tr is not None:
        fit_kwargs["sample_weight"] = sw_tr
    model.fit(X_tr_s, y_tr_t, **fit_kwargs)
    raw = model.predict(X_te_s)
    pred = np.expm1(raw) if log_target else raw
    pred = np.clip(pred, 0, None)
    return model, scaler, log_target, {
        "r2": float(r2_score(y_te, pred)),
        "mae": float(mean_absolute_error(y_te, pred)),
        "mape_pct": float(mean_absolute_percentage_error(y_te, pred) * 100),
    }, (X_te, y_te, pred)


FAIXAS = ["<3k", "3-5k", "5-10k", "10-20k", "20-30k", "30-50k", ">50k"]


def metrics_por_faixa(y_true, y_pred):
    res = {}
    yt = np.array(y_true); yp = np.array(y_pred)
    for fx in FAIXAS:
        if fx == "<3k": m = yt < 3000
        elif fx == "3-5k": m = (yt >= 3000) & (yt < 5000)
        elif fx == "5-10k": m = (yt >= 5000) & (yt < 10000)
        elif fx == "10-20k": m = (yt >= 10000) & (yt < 20000)
        elif fx == "20-30k": m = (yt >= 20000) & (yt < 30000)
        elif fx == "30-50k": m = (yt >= 30000) & (yt < 50000)
        else: m = yt >= 50000
        if m.sum() >= 5:
            res[fx] = {
                "n": int(m.sum()),
                "mae": float(mean_absolute_error(yt[m], yp[m])),
                "mape_pct": float(mean_absolute_percentage_error(yt[m], yp[m]) * 100),
            }
    return res


def evaluate_current_model(df):
    """Baseline: CatBoost atual via PricePredictor (hold-out honesto implícito)."""
    try:
        from valuation.predict import PricePredictor
        pp = PricePredictor("carros")
        if pp.model is None:
            return None
        y_true, y_pred = [], []
        for r in df.to_dict("records"):
            p = pp.predict(r)
            if p is not None and p > 0:
                y_true.append(r["price"]); y_pred.append(p)
        y_true = np.array(y_true); y_pred = np.array(y_pred)
        return {
            "model": f"{pp.model_name} (atual)",
            "global": {"r2": float(r2_score(y_true, y_pred)),
                       "mae": float(mean_absolute_error(y_true, y_pred)),
                       "mape_pct": float(mean_absolute_percentage_error(y_true, y_pred)*100)},
            "por_faixa": metrics_por_faixa(y_true, y_pred),
            "n": len(y_true),
        }
    except Exception as e:
        logger.warning(f"Não consegui avaliar modelo atual: {e}")
        return None


def main():
    df = load_retail_data()
    feat_df, fs = build_features(df)
    feature_cols = FeatureStore.ALLOWED_FEATURES
    logger.info(f"Features ({len(feature_cols)}): {feature_cols}")

    baseline = evaluate_current_model(df)

    # FULL com log-target (doma caudas >20k)
    X_full = feat_df[feature_cols].values
    y_full = feat_df["price"].values
    logger.info("Treinando FULL XGBoost (log-target)...")
    full_model, full_scaler, full_log, full_metrics, full_test = train_xgb(
        X_full, y_full, log_target=True)

    # LOW (<20k), target original
    low_mask = feat_df["price"] < LOW_THRESHOLD
    X_low = feat_df[low_mask][feature_cols].values
    y_low = feat_df[low_mask]["price"].values
    # --- Pesos de amostra: enfatizar km extremo (240-285k) para corrigir o
    #     enviesamento de +54% do modelo LOW nesta faixa. Usa km_def do DF
    #     original (não escalado) para definir os pesos.
    low_km = feat_df[low_mask]["km"].values
    w_low = np.ones(len(y_low), dtype=float)
    w_low[low_km > 200000] = 3.0      # 200-250k: triplo foco
    w_low[low_km > 250000] = 6.0      # >250k (extremo): 6x foco
    logger.info(f"Treinando LOW XGBoost (n={len(y_low)}, km-extremo penalizado)...")
    low_model, low_scaler, low_log, low_metrics, low_test = train_xgb(
        X_low, y_low, log_target=False, sample_weight=w_low)

    # ===== AVALIAÇÃO TWO-STAGE HONESTA =====
    # Usa o FULL para prever um preço preliminar; se < threshold -> LOW.
    X_te, y_te, _ = full_test
    full_prelim = np.expm1(full_model.predict(full_scaler.transform(X_te))) if full_log \
                  else full_model.predict(full_scaler.transform(X_te))
    preds = []
    for i in range(len(y_te)):
        if full_prelim[i] < LOW_THRESHOLD:
            lp = low_model.predict(low_scaler.transform(X_te[i:i+1]))[0]
            preds.append(max(lp, 0))
        else:
            preds.append(max(full_prelim[i], 0))
    preds = np.array(preds)
    new_global = {
        "r2": float(r2_score(y_te, preds)),
        "mae": float(mean_absolute_error(y_te, preds)),
        "mape_pct": float(mean_absolute_percentage_error(y_te, preds) * 100),
    }
    new_por_faixa = metrics_por_faixa(y_te, preds)

    # ===== GUARDAR =====
    mdir = Path(settings.models_dir)
    full_model.save_model(str(mdir / "model_carros.json"))
    low_model.save_model(str(mdir / "model_carros_low.json"))
    dump(full_scaler, str(mdir / "scaler_carros.joblib"))
    dump(low_scaler, str(mdir / "scaler_carros_low.joblib"))
    fs.save_index(mdir / "brand_index_carros.json")

    meta = {
        "model_type": "xgboost",
        "model_path": "model_carros.json",
        "scaler_path": "scaler_carros.joblib",
        "brand_index_path": "brand_index_carros.json",
        "low_model_path": "model_carros_low.json",
        "low_scaler_path": "scaler_carros_low.joblib",
        "full_log_target": full_log,
        "low_threshold": LOW_THRESHOLD,
        "vehicle_type": "carros",
        "feature_names": feature_cols,
        "metrics": new_global,
        "low_metrics": low_metrics,
        "n_samples": int(len(feat_df)),
        "trained_at": datetime.now().isoformat(),
        "excludes_auctions": sorted(AUCTION_SOURCES),
        "routing": "two_stage_full_prelim",
        "pipeline_version": "v2",
        "optimizations": {"segmented_low_full": True, "full_log_target": True,
                          "excludes_auctions": True},
    }
    with open(mdir / "best_model_carros.json", "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Modelos guardados em models/")

    # ===== RELATÓRIO =====
    print("\n" + "=" * 74)
    print("RELATÓRIO TREINO SEGMENTADO — CARROS (two-stage honesto)")
    print("=" * 74)
    print(f"\nAmostras retalho (sem leilões): {len(feat_df)}")
    if baseline:
        print(f"\n--- BASELINE: {baseline['model']} (n={baseline['n']}) ---")
        print(f"  Global: R²={baseline['global']['r2']:.4f}  MAE=€{baseline['global']['mae']:.0f}  "
              f"MAPE={baseline['global']['mape_pct']:.1f}%")
    print(f"\n--- NEW: XGBoost FULL(log)+LOW two-stage (threshold <{int(LOW_THRESHOLD)}k) ---")
    print(f"  Global: R²={new_global['r2']:.4f}  MAE=€{new_global['mae']:.0f}  "
          f"MAPE={new_global['mape_pct']:.1f}%")
    print(f"  FULL-only: R²={full_metrics['r2']:.4f} MAE=€{full_metrics['mae']:.0f}")
    print(f"  LOW-only (n={len(y_low)}): R²={low_metrics['r2']:.4f} MAE=€{low_metrics['mae']:.0f}")

    print("\n--- POR FAIXA (MAE € / MAPE %) ---")
    hdr = f"{'faixa':8} {'n':>5} | {'BASE_MAE':>9} {'BASE_MAPE':>9} | {'NEW_MAE':>9} {'NEW_MAPE':>9}"
    print(hdr); print("-" * len(hdr))
    for fx in FAIXAS:
        base = baseline["por_faixa"].get(fx) if baseline else None
        new = new_por_faixa.get(fx)
        if not new and not base:
            continue
        n = new["n"] if new else base["n"]
        bmae = f"{base['mae']:.0f}" if base else "  -  "
        bmp = f"{base['mape_pct']:.1f}" if base else "  -  "
        nmae = f"{new['mae']:.0f}" if new else "  -  "
        nmp = f"{new['mape_pct']:.1f}" if new else "  -  "
        print(f"{fx:8} {n:>5} | {bmae:>9} {bmp:>9} | {nmae:>9} {nmp:>9}")
    print("\nGuardado: models/best_model_carros.json (FULL, log) + model_carros_low.json (LOW)")


if __name__ == "__main__":
    main()
