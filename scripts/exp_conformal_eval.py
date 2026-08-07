"""
Validação da regressão quantílica conformalizada (CQR).

Verifica as duas propriedades que interessam numa avaliação profissional:

  1. cobertura — o intervalo de 80% contém mesmo 80% dos preços reais?
  2. utilidade — o intervalo é estreito o suficiente para ser accionável?

Protocolo temporal idêntico ao de produção: TimeSeriesSplit de 5 folds, e dentro
de cada fold de treino a última fatia é reservada para calibração (nunca o
futuro).

Uso:  python3 scripts/exp_conformal_eval.py
"""
from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # necessário para @dataclass resolver o módulo
    spec.loader.exec_module(mod)
    return mod


bench = _load("bench", "scripts/exp_valuation_v3.py")
conf = _load("conf", "valuation/conformal.py")


def main():
    df = bench.load_frame()
    y = df["price"].to_numpy(float)
    y_log = np.log1p(y)
    print(f"Corpus: {len(df)} carros\n")

    rows_true, rows_iv = [], []
    for tr, te in TimeSeriesSplit(n_splits=5).split(df):
        Xtr, Xte, _ = bench.build("E", df, tr, te, y_log)
        n_calib = max(int(len(tr) * 0.25), 30)
        calib_local = np.arange(len(tr) - n_calib, len(tr))

        cv = conf.ConformalQuantileValuator(alpha=0.20)
        cv.fit(Xtr, y[tr], calib_idx=calib_local)
        rows_iv.extend(cv.predict_interval(Xte))
        rows_true.append(y[te])

    yt = np.concatenate(rows_true)
    stats = conf.ConformalQuantileValuator.evaluate_coverage(rows_iv, yt)

    print("=" * 62)
    print("CQR — intervalo nominal de 80%")
    print(f"  cobertura real          : {stats['cobertura_pct']:.1f}%   (alvo 80%)")
    print(f"  largura relativa mediana: {stats['largura_relativa_mediana_pct']:.1f}%")
    print(f"  MAPE da estimativa P50  : {stats['mape_pct']:.2f}%")
    print(f"  n                       : {stats['n']}")

    lo = np.array([i.lower for i in rows_iv])
    hi = np.array([i.upper for i in rows_iv])
    mid = np.array([i.estimate for i in rows_iv])
    inside = (yt >= lo) & (yt <= hi)
    width = (hi - lo) / np.maximum(mid, 1)

    print("\n  por banda de preço:")
    print(f"  {'banda':>8} {'cobertura':>10} {'largura':>9} {'MAPE':>8} {'n':>6}")
    for lo_b, hi_b in [(0, 5000), (5000, 15000), (15000, 30000),
                       (30000, 60000), (60000, 10 ** 9)]:
        m = (yt >= lo_b) & (yt < hi_b)
        lbl = f"{lo_b // 1000}k-{hi_b // 1000}k" if hi_b < 10 ** 9 else "60k+"
        if m.sum() >= 5:
            mp = np.mean(np.abs(yt[m] - mid[m]) / yt[m]) * 100
            print(f"  {lbl:>8} {np.mean(inside[m]) * 100:9.1f}% "
                  f"{np.median(width[m]) * 100:8.1f}% {mp:7.1f}% {m.sum():6}")

    print("\n  triagem por fiabilidade:")
    for tier in ("alta", "media", "baixa"):
        m = np.array([i.reliability == tier for i in rows_iv])
        if m.sum():
            mp = np.mean(np.abs(yt[m] - mid[m]) / yt[m]) * 100
            print(f"    {tier:>6}: n={m.sum():5}  MAPE={mp:5.1f}%  "
                  f"cobertura={np.mean(inside[m]) * 100:5.1f}%")

    pub = np.array([i.publishable for i in rows_iv])
    mp_pub = np.mean(np.abs(yt[pub] - mid[pub]) / yt[pub]) * 100
    print(f"\n  publicáveis: {pub.sum()}/{len(pub)} ({pub.mean() * 100:.1f}%)  "
          f"MAPE nesse subconjunto = {mp_pub:.2f}%")
    print(f"  suprimidas : {(~pub).sum()} avaliações que seriam erradas e confiantes")


if __name__ == "__main__":
    main()
