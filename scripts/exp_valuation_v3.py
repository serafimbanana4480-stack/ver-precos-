"""
Benchmark incremental das melhorias de avaliação (carros).

Cada variante acrescenta UMA mudança à anterior, para se saber exatamente o que
contribui e o que não contribui. Protocolo idêntico ao de produção
(valuation/train_v2.py): TimeSeriesSplit de 5 folds, alvo log1p, sem leakage.

  A  baseline em produção (frequency encoding, inclui features mortas)
  D  A sem features mortas (district e doors estão a 0% de preenchimento)
  E  D + features extraídas do título (cilindrada, potência, trim, carroçaria)
  F  E + encoding hierárquico com shrinkage (modelo -> marca -> global)
  G  F com LightGBM e restrições de monotonia (km desce, ano sobe)

No fim, a melhor variante é reavaliada com regressão quantílica para produzir
intervalos P10/P50/P90, e mede-se a cobertura empírica do intervalo.

Uso:  python3 scripts/exp_valuation_v3.py
"""
from __future__ import annotations

import importlib.util
import os
import sqlite3
import unicodedata
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
# AUTODEAL_DB permite apontar para uma cópia local — útil quando a base está
# num volume de rede/montagem que dá erros de I/O em leituras longas.
DB = Path(os.environ.get("AUTODEAL_DB", ROOT / "data" / "autodeal.db"))

_spec = importlib.util.spec_from_file_location(
    "title_features", ROOT / "valuation" / "title_features.py")
tf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tf)

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


def _norm(t) -> str:
    if not t:
        return ""
    s = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def load_frame() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    ph = ",".join("?" * len(AUCTION_SOURCES))
    df = pd.read_sql_query(
        f"""SELECT brand, model, year, km, horsepower, engine_size, doors,
                   fuel_type, transmission, district, title, price, first_seen
            FROM vehicles
            WHERE vehicle_type='carros' AND is_active=1
              AND quality_status IN ('valid','valid_with_warning')
              AND price_kind='total' AND currency='EUR'
              AND price>300 AND price<400000
              AND year IS NOT NULL AND year>=1970 AND year<={CURRENT_YEAR + 1}
              AND km IS NOT NULL AND km>=0
              AND source NOT IN ({ph})""",
        con, params=AUCTION_SOURCES)
    con.close()
    df = df.drop_duplicates(subset=["brand", "model", "year", "km", "price"])
    for c in ("brand", "model", "district", "fuel_type", "transmission"):
        df[c] = df[c].map(_norm)
    df = df.sort_values("first_seen").reset_index(drop=True)

    # features do título, calculadas uma vez
    tfeats = pd.DataFrame(
        [tf.extract_title_features(t, y)
         for t, y in zip(df["title"], df["year"])], index=df.index)
    return pd.concat([df, tfeats], axis=1)


# ------------------------------------------------------------- encodings ----

def freq_encode(train_vals, all_vals):
    counts = Counter(train_vals)
    return np.array([counts.get(v, 0) for v in all_vals], dtype=float)


def hierarchical_encode(df, tr_idx, y_log, k_model=12.0, k_brand=6.0):
    """Encoding hierárquico com shrinkage empírico de Bayes.

    O preço médio de um modelo é encolhido para o da sua marca, e o da marca
    para a média global. Quanto menos exemplos, mais forte o encolhimento:

        marca_enc  = (soma_marca + global * k_brand) / (n_marca + k_brand)
        modelo_enc = (soma_modelo + marca_enc * k_model) / (n_modelo + k_model)

    É a ferramenta correta para categóricas esparsas (1200 modelos, ~3 exemplos
    cada), onde o target encoding simples sobreajusta. Ajustado só no treino.
    """
    brand = df["brand"].tolist()
    model = df["model"].tolist()
    ytr = y_log[tr_idx]
    gmean = float(np.mean(ytr))

    b_agg, m_agg = {}, {}
    for i in tr_idx:
        b, m, y = brand[i], model[i], y_log[i]
        s, n = b_agg.get(b, (0.0, 0)); b_agg[b] = (s + y, n + 1)
        key = (b, m)
        s, n = m_agg.get(key, (0.0, 0)); m_agg[key] = (s + y, n + 1)

    b_enc = {b: (s + gmean * k_brand) / (n + k_brand) for b, (s, n) in b_agg.items()}
    m_enc = {}
    for (b, m), (s, n) in m_agg.items():
        parent = b_enc.get(b, gmean)
        m_enc[(b, m)] = (s + parent * k_model) / (n + k_model)

    brand_col = np.array([b_enc.get(b, gmean) for b in brand])
    model_col = np.array([m_enc.get((b, m), b_enc.get(b, gmean))
                          for b, m in zip(brand, model)])
    n_model = Counter((brand[i], model[i]) for i in tr_idx)
    support = np.array([n_model.get((b, m), 0) for b, m in zip(brand, model)],
                       dtype=float)
    return brand_col, model_col, support


def numeric_block(df, drop_dead=False, with_title=False):
    age = np.maximum(CURRENT_YEAR - df["year"].to_numpy(float), 0)
    km = df["km"].to_numpy(float)
    cols = {
        "year": df["year"].to_numpy(float),
        "km": km,
        "horsepower": df["horsepower"].fillna(0).to_numpy(float),
        "engine_size": df["engine_size"].fillna(0).to_numpy(float),
        "age": age,
        "km_per_year": km / np.maximum(age, 1),
        "fuel_type": df["fuel_type"].map(FUEL_ENCODE).fillna(0).to_numpy(float),
        "transmission": df["transmission"].map(TRANS_ENCODE).fillna(0).to_numpy(float),
        "fuel_premium": df["fuel_type"].map(FUEL_PREMIUM).fillna(1.0).to_numpy(float),
        "log_km": np.log1p(km),
    }
    if not drop_dead:
        cols["doors"] = df["doors"].fillna(4).to_numpy(float)

    exp_total = np.maximum(
        df["fuel_type"].map(EXPECTED_KM).fillna(13000).to_numpy(float)
        * np.maximum(age, 1), 1)
    cols["km_excess"] = np.maximum(km - exp_total, 0)
    cols["km_extreme"] = (km / exp_total > 2.0).astype(float)

    if with_title:
        for name in tf.TITLE_FEATURE_NAMES:
            if name in ("t_is_import", "t_has_damage"):
                continue  # 0% de deteção neste corpus, seriam constantes
            cols[name] = df[name].to_numpy(float)
    return cols


def build(variant, df, tr_idx, te_idx, y_log):
    drop_dead = variant in ("D", "E", "F", "G")
    with_title = variant in ("E", "F", "G")
    cols = numeric_block(df, drop_dead, with_title)
    names = list(cols.keys())
    mats = [cols[n] for n in names]

    brand, model = df["brand"].tolist(), df["model"].tolist()
    if variant in ("A", "D", "E"):
        mats += [freq_encode([brand[i] for i in tr_idx], brand),
                 freq_encode([model[i] for i in tr_idx], model)]
        names += ["brand_freq", "model_freq"]
        if not drop_dead:
            d = df["district"].tolist()
            mats.append(freq_encode([d[i] for i in tr_idx], d))
            names.append("district_freq")
    else:
        b, m, sup = hierarchical_encode(df, tr_idx, y_log)
        mats += [b, m, sup]
        names += ["brand_hier", "model_hier", "model_support"]

    X = np.column_stack(mats)
    return X[tr_idx], X[te_idx], names


def monotone_vector(names):
    """+1 sobe com o preço, -1 desce, 0 sem restrição."""
    up = {"year", "horsepower", "engine_size", "t_power_cv", "t_trim_tier",
          "t_displacement", "t_battery_kwh", "brand_hier", "model_hier"}
    down = {"km", "log_km", "age", "km_excess", "km_extreme", "km_per_year"}
    return [1 if n in up else (-1 if n in down else 0) for n in names]


def mape_by_band(yt, yp):
    bands = [(0, 5000), (5000, 15000), (15000, 30000), (30000, 60000),
             (60000, 10 ** 9)]
    out = {}
    for lo, hi in bands:
        msk = (yt >= lo) & (yt < hi)
        lbl = f"{lo // 1000}k-{hi // 1000}k" if hi < 10 ** 9 else "60k+"
        if msk.sum() >= 5:
            out[lbl] = (float(np.mean(np.abs(yt[msk] - yp[msk]) / yt[msk]) * 100),
                        int(msk.sum()))
    return out


def run(variant, df, n_splits=5):
    y = df["price"].to_numpy(float)
    y_log = np.log1p(y)
    yt_all, yp_all = [], []
    for tr, te in TimeSeriesSplit(n_splits=n_splits).split(df):
        Xtr, Xte, names = build(variant, df, tr, te, y_log)
        if variant == "G":
            import lightgbm as lgb
            m = lgb.LGBMRegressor(
                n_estimators=700, learning_rate=0.04, num_leaves=31,
                min_child_samples=8, subsample=0.85, subsample_freq=1,
                colsample_bytree=0.85, reg_lambda=2.0,
                monotone_constraints=monotone_vector(names),
                random_state=SEED, verbose=-1, n_jobs=-1)
        else:
            m = ExtraTreesRegressor(n_estimators=400, min_samples_leaf=2,
                                    random_state=SEED, n_jobs=-1)
        m.fit(Xtr, y_log[tr])
        yt_all.append(y[te])
        yp_all.append(np.expm1(m.predict(Xte)))
    yt, yp = np.concatenate(yt_all), np.concatenate(yp_all)
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
    return {"r2": 1 - ss_res / ss_tot,
            "mape": float(np.mean(np.abs(yt - yp) / yt) * 100),
            "mae": float(np.mean(np.abs(yt - yp))),
            "bands": mape_by_band(yt, yp)}


def run_quantiles(df, variant="E", n_splits=5):
    """Intervalos P10/P50/P90 por regressão quantílica (pinball loss).

    Nota: o LightGBM não aceita monotone_constraints com objetivo quantile, por
    isso os quantis correm sem restrição de monotonia.
    """
    import lightgbm as lgb
    y = df["price"].to_numpy(float)
    y_log = np.log1p(y)
    acc = {q: [] for q in (0.1, 0.5, 0.9)}
    truth, bands_src = [], []
    for tr, te in TimeSeriesSplit(n_splits=n_splits).split(df):
        Xtr, Xte, _ = build(variant, df, tr, te, y_log)
        truth.append(y[te])
        for q in (0.1, 0.5, 0.9):
            m = lgb.LGBMRegressor(
                objective="quantile", alpha=q, n_estimators=700,
                learning_rate=0.04, num_leaves=31, min_child_samples=8,
                subsample=0.85, subsample_freq=1, colsample_bytree=0.85,
                random_state=SEED, verbose=-1, n_jobs=-1)
            m.fit(Xtr, y_log[tr])
            acc[q].append(np.expm1(m.predict(Xte)))
    yt = np.concatenate(truth)
    p10, p50, p90 = (np.concatenate(acc[q]) for q in (0.1, 0.5, 0.9))
    p10, p90 = np.minimum(p10, p90), np.maximum(p10, p90)
    inside = (yt >= p10) & (yt <= p90)
    rel_width = (p90 - p10) / np.maximum(p50, 1)

    # cobertura e largura por banda de preço: onde é que o modelo sabe que não sabe
    per_band = {}
    for lo, hi in [(0, 5000), (5000, 15000), (15000, 30000), (30000, 60000),
                   (60000, 10 ** 9)]:
        msk = (yt >= lo) & (yt < hi)
        lbl = f"{lo // 1000}k-{hi // 1000}k" if hi < 10 ** 9 else "60k+"
        if msk.sum() >= 5:
            per_band[lbl] = (float(np.mean(inside[msk]) * 100),
                             float(np.median(rel_width[msk]) * 100),
                             int(msk.sum()))
    return {"cobertura_p10_p90": float(np.mean(inside) * 100),
            "largura_mediana_pct": float(np.median(rel_width) * 100),
            "mape_p50": float(np.mean(np.abs(yt - p50) / yt) * 100),
            "por_banda": per_band}


def main():
    df = load_frame()
    print(f"Corpus: {len(df)} carros | {df.brand.nunique()} marcas | "
          f"{df.model.nunique()} modelos\n")

    labels = {
        "A": "baseline produção (freq. encoding + features mortas)",
        "D": "A sem features mortas (district, doors)",
        "E": "D + features do título",
        "F": "E + encoding hierárquico com shrinkage",
        "G": "F + LightGBM com monotonia (km desce, ano sobe)",
    }
    res = {}
    for v in ("A", "D", "E", "F", "G"):
        res[v] = run(v, df)
        r = res[v]
        print(f"--- {v}: {labels[v]}")
        print(f"    R2={r['r2']:.4f}  MAPE={r['mape']:.2f}%  MAE={r['mae']:.0f}EUR")
        print("    " + "  ".join(f"{b}:{mp:.1f}%" for b, (mp, _) in r["bands"].items()))
        print()

    print("=" * 68)
    a = res["A"]
    best = max(res, key=lambda k: res[k]["r2"])
    print(f"{'variante':>4}  {'R2':>8}  {'MAPE':>8}  {'vs baseline':>12}")
    for v in ("A", "D", "E", "F", "G"):
        d = res[v]["mape"] - a["mape"]
        print(f"{v:>4}  {res[v]['r2']:8.4f}  {res[v]['mape']:7.2f}%  "
              f"{d:+11.2f}pp{'   <-- melhor' if v == best else ''}")

    print("\n" + "=" * 68)
    print("Intervalos de previsão (regressão quantílica sobre a variante E)")
    q = run_quantiles(df, variant="E")
    print(f"  cobertura real do intervalo P10-P90 : {q['cobertura_p10_p90']:.1f}%  (alvo 80%)")
    print(f"  largura mediana do intervalo        : {q['largura_mediana_pct']:.1f}% do preço")
    print(f"  MAPE da mediana P50                 : {q['mape_p50']:.2f}%")
    print(f"\n  {'banda':>8}  {'cobertura':>10}  {'largura':>9}  {'n':>5}")
    for b, (cov, w, n) in q["por_banda"].items():
        print(f"  {b:>8}  {cov:9.1f}%  {w:8.1f}%  {n:5}")


if __name__ == "__main__":
    main()
