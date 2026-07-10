"""
Treino de modelo CatBoost DEDICADO para veículos HIGH-END — VER PRECOS.

Motivação (crítico):
  - O XGBoost FULL (log-target) subestima as caudas altas, sobretudo >50k.
  - CatBoost com CATEGORICAL FEATURES NATIVAS (brand/model/district/fuel/transmission)
    + log-target recupera as caudas altas (ver relatório no fim).
  - Routing produção-honesto (3 vias): FULL prevê preço preliminar; se >= HIGH_THRESHOLD
    usa HIGH (CatBoost); se < LOW_THRESHOLD usa LOW. Nunca usa o preço real.
  - EXCLUI leilões (LEILOSOC/MARTELO/AUTOLINE/PENHORADO/VPAUTO/MANHEIM/AUTOROLA/BCA).
  - Usa o MESMO brand_index de produção e as MESMAS feature_names da metadata
    (best_model_carros.json) para não haver training-serving skew.

NOTA: o CatBoost é treinado em amostras com price >= HIGH_TRAIN_THRESHOLD (15k),
incluindo a zona 15-20k para aprender melhor a fronteira, mas em produção só é
invocado quando o preliminar do FULL >= HIGH_THRESHOLD (20k).

Uso: python -u scripts/train_high.py
"""
import os, sys, json, logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, mean_absolute_percentage_error
from catboost import CatBoostRegressor

from core.settings import settings
from valuation.feature_store import FeatureStore
from database.db import get_db_context
from database.models import Vehicle, VehicleType

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("train_high")

AUCTION_SOURCES = {"LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA",
                   "MARTELO", "AUTOLINE", "PENHORADO"}

HIGH_THRESHOLD = 20000.0        # routing: preliminar FULL >= isto -> usa HIGH
HIGH_TRAIN_THRESHOLD = 15000.0  # treina o CatBoost em price >= isto (aprende fronteira)
LOG_TARGET = True
RANDOM_STATE = 42
CAT_COLS = ["fuel_type", "transmission", "brand", "model", "district"]

FAIXAS_ALTAS = ["20-30k", "30-50k", ">50k"]


def _val_str(val):
    return "unknown" if val is None else (val.value if hasattr(val, "value") else str(val))


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
    n_auction = int(df["source"].isin(AUCTION_SOURCES).sum())
    df = df[~df["source"].isin(AUCTION_SOURCES)].reset_index(drop=True)
    logger.info(f"Carregados {len(df)} retalhos (excluidos {n_auction} leiloes)")
    return df


def _band_mask(yt, fx):
    if fx == "20-30k": return (yt >= 20000) & (yt < 30000)
    if fx == "30-50k": return (yt >= 30000) & (yt < 50000)
    return yt >= 50000


def metrics_por_faixa(y_true, y_pred, faixas=FAIXAS_ALTAS):
    res = {}
    yt = np.asarray(y_true); yp = np.asarray(y_pred)
    for fx in faixas:
        m = _band_mask(yt, fx)
        if m.sum() >= 3:
            res[fx] = {"n": int(m.sum()),
                       "r2": float(r2_score(yt[m], yp[m])),
                       "mae": float(mean_absolute_error(yt[m], yp[m])),
                       "mape_pct": float(mean_absolute_percentage_error(yt[m], yp[m]) * 100)}
    return res


def to_cat(A, cat_idx):
    A = A.copy().astype(object)
    for c in cat_idx:
        A[:, c] = A[:, c].astype(int).astype(str)
    return A


def main():
    mdir = Path(settings.models_dir)
    meta_prod = json.load(open(mdir / "best_model_carros.json"))
    feature_names = meta_prod["feature_names"]  # fonte de verdade (evita skew)
    cat_idx = [feature_names.index(c) for c in CAT_COLS if c in feature_names]
    logger.info(f"feature_names ({len(feature_names)}) | cat_idx={cat_idx}")

    df = load_retail_data()
    fs = FeatureStore()
    fs.load_index(mdir / "brand_index_carros.json")
    feats = [fs.compute_features(r) for r in df.to_dict("records")]
    X = np.array([[f.get(k, 0.0) for k in feature_names] for f in feats])
    y = df["price"].values

    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=0.2, random_state=RANDOM_STATE)
    Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]

    # ---- Treino CatBoost HIGH (cat nativas + log-target) ----
    hm = ytr >= HIGH_TRAIN_THRESHOLD
    Xh, yh = Xtr[hm], ytr[hm]
    yt_ = np.log1p(yh) if LOG_TARGET else yh
    logger.info(f"CatBoost HIGH treino n={len(yh)} (price>={int(HIGH_TRAIN_THRESHOLD)})")
    Xh2, Xv, yh2, yv = train_test_split(to_cat(Xh, cat_idx), yt_,
                                        test_size=0.15, random_state=RANDOM_STATE)
    high_model = CatBoostRegressor(
        iterations=1500, depth=8, learning_rate=0.03, l2_leaf_reg=3.0,
        loss_function="RMSE", eval_metric="RMSE", random_seed=RANDOM_STATE,
        verbose=False, early_stopping_rounds=80, cat_features=cat_idx)
    high_model.fit(Xh2, yh2, eval_set=(Xv, yv), use_best_model=True)

    # ---- Baseline ANTES (produção XGBoost two-stage) ----
    import xgboost as xgb
    from joblib import load as jload
    full = xgb.XGBRegressor(); full.load_model(str(mdir / meta_prod["model_path"]))
    fsc = jload(str(mdir / meta_prod["scaler_path"]))
    full_log = meta_prod.get("full_log_target", False)
    low = xgb.XGBRegressor(); low.load_model(str(mdir / meta_prod["low_model_path"]))
    lsc = jload(str(mdir / meta_prod["low_scaler_path"]))
    low_thr = meta_prod.get("low_threshold", 20000.0)

    fp_raw = full.predict(fsc.transform(Xte))
    fp = np.clip(np.expm1(fp_raw) if full_log else fp_raw, 0, None)
    low_pred = np.clip(low.predict(lsc.transform(Xte)), 0, None)
    hp = high_model.predict(to_cat(Xte, cat_idx))
    hp = np.clip(np.expm1(hp) if LOG_TARGET else hp, 0, None)

    pred_before = np.array([fp[i] if fp[i] >= low_thr else low_pred[i]
                            for i in range(len(yte))])
    pred_after = np.array([hp[i] if fp[i] >= HIGH_THRESHOLD else low_pred[i]
                           for i in range(len(yte))])

    before_high = metrics_por_faixa(yte, pred_before)
    after_high = metrics_por_faixa(yte, pred_after)
    hi = yte >= HIGH_THRESHOLD
    def glob(yp):
        return {"n": int(hi.sum()), "r2": float(r2_score(yte[hi], yp[hi])),
                "mae": float(mean_absolute_error(yte[hi], yp[hi])),
                "mape_pct": float(mean_absolute_percentage_error(yte[hi], yp[hi]) * 100)}
    before_glob, after_glob = glob(pred_before), glob(pred_after)

    # ---- Guardar HIGH ----
    high_path = mdir / "model_carros_high.json"
    high_model.save_model(str(high_path), format="json")
    logger.info(f"Guardado {high_path}")

    high_meta = {
        "model_type": "catboost", "target": "price",
        "high_threshold": HIGH_THRESHOLD, "high_train_threshold": HIGH_TRAIN_THRESHOLD,
        "high_log_target": LOG_TARGET, "high_cat_features": cat_idx,
        "feature_names": feature_names, "n_train_high": int(len(yh)),
        "trained_at": datetime.now().isoformat(),
        "metrics_true_ge_20k_after": after_glob,
        "metrics_true_ge_20k_before_xgb": before_glob,
        "por_faixa_after": after_high, "por_faixa_before_xgb": before_high,
        "excludes_auctions": sorted(AUCTION_SOURCES),
        "brand_index_path": "brand_index_carros.json",
    }
    json.dump(high_meta, open(mdir / "model_carros_high.meta.json", "w"), indent=2)

    # ---- RELATORIO ----
    print("\n" + "=" * 80)
    print("RELATORIO — CatBoost HIGH-END (routing 3 vias, produção-honesto)")
    print("=" * 80)
    print(f"Retalho s/leiloes: {len(df)} | hold-out: {len(yte)} | HIGH treino n={len(yh)}")
    print(f"Test true>=20k n={int(hi.sum())}")
    print(f"\nGLOBAL true>=20k:")
    print(f"  ANTES (XGB):  R2={before_glob['r2']:.4f} MAE=EUR{before_glob['mae']:.0f} MAPE={before_glob['mape_pct']:.1f}%")
    print(f"  DEPOIS(CB):   R2={after_glob['r2']:.4f} MAE=EUR{after_glob['mae']:.0f} MAPE={after_glob['mape_pct']:.1f}%")
    print("\n--- POR FAIXA ALTA (R2 / MAE EUR / MAPE %) ---")
    hdr = f"{'faixa':8} {'n':>4} | {'B_R2':>7} {'B_MAE':>8} {'B_MAPE':>7} | {'A_R2':>7} {'A_MAE':>8} {'A_MAPE':>7}"
    print(hdr); print("-" * len(hdr))
    for fx in FAIXAS_ALTAS:
        b, a = before_high.get(fx), after_high.get(fx)
        if not a and not b: continue
        n = (a or b)["n"]
        f = lambda d, k, dc=0: ("  -  " if not d else f"{d[k]:.{dc}f}")
        print(f"{fx:8} {n:>4} | {f(b,'r2',3):>7} {f(b,'mae'):>8} {f(b,'mape_pct',1):>7} | "
              f"{f(a,'r2',3):>7} {f(a,'mae'):>8} {f(a,'mape_pct',1):>7}")
    print("\nGuardado: models/model_carros_high.json (CatBoost, cat nativas, log-target)")


if __name__ == "__main__":
    main()
