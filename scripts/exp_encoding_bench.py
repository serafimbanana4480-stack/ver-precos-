"""
Benchmark de encoding para o modelo de preço (carros).

Responde a: "como poderia o modelo aprender melhor por marca, km e modelo?"

Compara, com o MESMO protocolo temporal (TimeSeriesSplit, alvo log1p) usado em
valuation/train_v2.py:

  A) baseline    — frequency encoding de brand/model (o que está em produção)
  B) target enc  — target encoding out-of-fold de brand, model e brand|model
  C) B + km      — B mais features de quilometragem/idade não-lineares

Target encoding é calculado SÓ com o fold de treino e aplicado ao fold de teste,
com smoothing bayesiano — sem leakage.

Uso:  python3 scripts/exp_encoding_bench.py
"""
from __future__ import annotations

import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import TimeSeriesSplit

DB = Path(__file__).resolve().parent.parent / "data" / "autodeal.db"
AUCTION_SOURCES = ("AUTOLINE", "LEILOSOC", "MARTELO", "PENHORADO",
                   "VPAUTO", "MANHEIM", "AUTOROLA", "BCA")
CURRENT_YEAR = 2026
SEED = 42

FUEL_ENCODE = {"gasolina": 0, "diesel": 1, "eletrico": 2, "hibrido": 3, "gpl": 4}
TRANS_ENCODE = {"manual": 0, "automatica": 1, "automatico": 1}
FUEL_PREMIUM = {"eletrico": 1.25, "hibrido": 1.12, "gasolina": 1.00,
                "gpl": 0.92, "diesel": 0.88}
EXPECTED_KM = {"diesel": 18000, "gasolina": 12000, "hibrido": 14000,
               "eletrico": 13000}


def _norm(text) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return t.strip().lower()


def load_frame() -> pd.DataFrame:
    """Mesmos filtros de valuation.train_v2.load_training_frame."""
    con = sqlite3.connect(DB)
    placeholders = ",".join("?" * len(AUCTION_SOURCES))
    df = pd.read_sql_query(
        f"""
        SELECT brand, model, year, km, horsepower, engine_size, doors,
               fuel_type, transmission, district, price, first_seen
        FROM vehicles
        WHERE vehicle_type = 'carros'
          AND is_active = 1
          AND quality_status IN ('valid', 'valid_with_warning')
          AND price_kind = 'total'
          AND currency = 'EUR'
          AND price > 300 AND price < 400000
          AND year IS NOT NULL AND year >= 1970 AND year <= {CURRENT_YEAR + 1}
          AND km IS NOT NULL AND km >= 0
          AND source NOT IN ({placeholders})
        """,
        con, params=AUCTION_SOURCES,
    )
    con.close()

    df = df.drop_duplicates(subset=["brand", "model", "year", "km", "price"])
    df["brand"] = df["brand"].map(_norm)
    df["model"] = df["model"].map(_norm)
    df["district"] = df["district"].map(_norm)
    df["fuel_type"] = df["fuel_type"].map(_norm)
    df["transmission"] = df["transmission"].map(_norm)
    df = df.sort_values("first_seen").reset_index(drop=True)
    return df


# --------------------------------------------------------------- encodings --

def freq_encode(train_vals, all_vals):
    """Encoding por frequência (o que está em produção)."""
    counts = Counter(train_vals)
    return np.array([counts.get(v, 0) for v in all_vals], dtype=float)


def target_encode(train_keys, train_y, apply_keys, smoothing=20.0):
    """Target encoding com smoothing bayesiano, ajustado só no treino.

    enc(k) = (soma_y(k) + prior * smoothing) / (n(k) + smoothing)

    Categorias não vistas caem no prior global — sem NaN, sem leakage.
    """
    prior = float(np.mean(train_y))
    agg: dict = {}
    for k, y in zip(train_keys, train_y):
        s, n = agg.get(k, (0.0, 0))
        agg[k] = (s + float(y), n + 1)
    enc = {k: (s + prior * smoothing) / (n + smoothing) for k, (s, n) in agg.items()}
    return np.array([enc.get(k, prior) for k in apply_keys], dtype=float)


def base_numeric(df: pd.DataFrame) -> dict:
    """Features numéricas partilhadas por todas as variantes."""
    age = np.maximum(CURRENT_YEAR - df["year"].to_numpy(dtype=float), 0)
    km = df["km"].to_numpy(dtype=float)
    return {
        "year": df["year"].to_numpy(dtype=float),
        "km": km,
        "horsepower": df["horsepower"].fillna(0).to_numpy(dtype=float),
        "engine_size": df["engine_size"].fillna(0).to_numpy(dtype=float),
        "doors": df["doors"].fillna(4).to_numpy(dtype=float),
        "age": age,
        "km_per_year": km / np.maximum(age, 1),
        "fuel_type": df["fuel_type"].map(FUEL_ENCODE).fillna(0).to_numpy(dtype=float),
        "transmission": df["transmission"].map(TRANS_ENCODE).fillna(0).to_numpy(dtype=float),
        "fuel_premium": df["fuel_type"].map(FUEL_PREMIUM).fillna(1.0).to_numpy(dtype=float),
        "log_km": np.log1p(km),
    }


def km_features(df: pd.DataFrame) -> dict:
    """Features de quilometragem não-lineares (variante C)."""
    age = np.maximum(CURRENT_YEAR - df["year"].to_numpy(dtype=float), 0)
    km = df["km"].to_numpy(dtype=float)
    expected = df["fuel_type"].map(EXPECTED_KM).fillna(13000).to_numpy(dtype=float)
    expected_total = np.maximum(expected * np.maximum(age, 1), 1)
    km_ratio = km / expected_total
    return {
        "km_ratio": km_ratio,
        "km_excess": np.maximum(km - expected_total, 0),
        "km_extreme": (km_ratio > 2.0).astype(float),
        "km_low": (km_ratio < 0.5).astype(float),
        "sqrt_km": np.sqrt(km),
        "age_x_logkm": age * np.log1p(km),
        "is_new": (age <= 1).astype(float),
        "is_old": (age >= 15).astype(float),
    }


def build(variant: str, df: pd.DataFrame, tr_idx, te_idx, y_log):
    """Constrói matrizes X_train/X_test para a variante pedida."""
    num = base_numeric(df)
    if variant == "C":
        num.update(km_features(df))

    cols = [v for v in num.values()]

    brand = df["brand"].tolist()
    model = df["model"].tolist()
    bm = [f"{b}|{m}" for b, m in zip(brand, model)]
    district = df["district"].tolist()

    if variant == "A":
        tb = [brand[i] for i in tr_idx]
        tm = [model[i] for i in tr_idx]
        td = [district[i] for i in tr_idx]
        cols += [freq_encode(tb, brand), freq_encode(tm, model),
                 freq_encode(td, district)]
    else:
        ytr = y_log[tr_idx]
        for keys in (brand, model, bm, district):
            tk = [keys[i] for i in tr_idx]
            cols.append(target_encode(tk, ytr, keys))
        # contagem de suporte: o modelo aprende a desconfiar de encodings raros
        cols.append(freq_encode([bm[i] for i in tr_idx], bm))

    X = np.column_stack(cols)
    return X[tr_idx], X[te_idx]


def mape_by_band(y_true, y_pred):
    bands = [(0, 5000), (5000, 15000), (15000, 30000), (30000, 60000),
             (60000, 10**9)]
    out = {}
    for lo, hi in bands:
        m = (y_true >= lo) & (y_true < hi)
        label = f"{lo // 1000}k-{hi // 1000}k" if hi < 10**9 else "60k+"
        if m.sum() >= 5:
            out[label] = (float(np.mean(np.abs(y_true[m] - y_pred[m]) / y_true[m]) * 100),
                          int(m.sum()))
    return out


def run(variant: str, df: pd.DataFrame, n_splits=5):
    y = df["price"].to_numpy(dtype=float)
    y_log = np.log1p(y)
    tscv = TimeSeriesSplit(n_splits=n_splits)

    yt_all, yp_all = [], []
    for tr, te in tscv.split(df):
        Xtr, Xte = build(variant, df, tr, te, y_log)
        m = ExtraTreesRegressor(n_estimators=400, max_depth=None,
                                min_samples_leaf=2, random_state=SEED, n_jobs=-1)
        m.fit(Xtr, y_log[tr])
        pred = np.expm1(m.predict(Xte))
        yt_all.append(y[te])
        yp_all.append(pred)

    yt = np.concatenate(yt_all)
    yp = np.concatenate(yp_all)
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
    return {
        "r2": 1 - ss_res / ss_tot,
        "mape": float(np.mean(np.abs(yt - yp) / yt) * 100),
        "mae": float(np.mean(np.abs(yt - yp))),
        "median_ae": float(np.median(np.abs(yt - yp))),
        "bands": mape_by_band(yt, yp),
        "n": len(yt),
    }


def main():
    df = load_frame()
    print(f"Corpus de treino: {len(df)} linhas  "
          f"({df['brand'].nunique()} marcas, {df['model'].nunique()} modelos)\n")

    labels = {
        "A": "baseline (frequency encoding)  [produção]",
        "B": "target encoding brand/model/brand|model",
        "C": "B + features de km/idade não-lineares",
    }
    results = {}
    for v in ("A", "B", "C"):
        results[v] = run(v, df)
        r = results[v]
        print(f"--- {v}: {labels[v]}")
        print(f"    R2={r['r2']:.4f}  MAPE={r['mape']:.2f}%  "
              f"MAE={r['mae']:.0f}EUR  medAE={r['median_ae']:.0f}EUR")
        for band, (mp, n) in r["bands"].items():
            print(f"      {band:>8}: MAPE {mp:5.1f}%  (n={n})")
        print()

    a, c = results["A"], results["C"]
    print("=" * 62)
    print(f"Ganho C vs A:  R2 {a['r2']:.4f} -> {c['r2']:.4f}   "
          f"MAPE {a['mape']:.2f}% -> {c['mape']:.2f}%")
    for band in c["bands"]:
        if band in a["bands"]:
            print(f"  {band:>8}: {a['bands'][band][0]:5.1f}% -> {c['bands'][band][0]:5.1f}%")


if __name__ == "__main__":
    main()
