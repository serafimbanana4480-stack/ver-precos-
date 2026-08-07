"""
Regressão quantílica conformalizada (CQR) para avaliação de veículos.

Porquê
------
Uma avaliação profissional nunca é um número único. Eurotax, Schwacke e DAT
publicam intervalos, porque um comprador precisa de saber a *incerteza*, não só
a estimativa. O sistema atual devolve um ponto — e o benchmark de 06/08/2026
mostrou que a regressão quantílica simples é otimista de mais: o intervalo
nominal P10–P90 (80%) só continha 50,5% dos preços reais.

A conformalização corrige isto com uma garantia distribution-free: para qualquer
modelo e qualquer distribuição, a cobertura no conjunto de teste é ≥ 1-α, desde
que os dados sejam permutáveis (Romano, Patterson & Candès, 2019).

Como funciona
-------------
1. Divide o treino em *proper train* e *calibração*.
2. Ajusta modelos quantílicos q_lo e q_hi no proper train.
3. Na calibração, mede o quanto cada intervalo falhou:

       E_i = max(q_lo(x_i) - y_i,  y_i - q_hi(x_i))

   E_i é negativo quando o ponto cai dentro do intervalo, positivo quando cai
   fora — é a "folga" que faltou.
4. Toma Q = quantil (1-α)(1+1/n) de E e alarga o intervalo:

       [q_lo(x) - Q,  q_hi(x) + Q]

O ajuste é feito em espaço logarítmico, para que a margem seja multiplicativa —
um erro de 500 € é grave num carro de 3.000 € e irrelevante num de 80.000 €.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

__all__ = ["ConformalQuantileValuator", "ValuationInterval"]


@dataclass
class ValuationInterval:
    """Resultado de uma avaliação com incerteza quantificada."""

    estimate: float          # mediana P50 — o valor a mostrar
    lower: float             # limite inferior calibrado
    upper: float             # limite superior calibrado
    confidence: float        # nível nominal do intervalo (ex. 0.80)
    relative_width: float    # (upper-lower)/estimate — largura relativa
    reliability: str         # "alta" | "media" | "baixa"
    publishable: bool        # se é responsável mostrar isto ao utilizador

    def as_dict(self) -> Dict[str, Any]:
        return {
            "estimate": round(self.estimate, 2),
            "lower": round(self.lower, 2),
            "upper": round(self.upper, 2),
            "confidence": self.confidence,
            "relative_width": round(self.relative_width, 4),
            "reliability": self.reliability,
            "publishable": self.publishable,
        }

    def format_pt(self) -> str:
        if not self.publishable:
            return ("Sem dados suficientes para uma avaliação fiável "
                    "deste veículo.")
        return (f"{self.estimate:,.0f} EUR "
                f"(intervalo {self.lower:,.0f}–{self.upper:,.0f} EUR, "
                f"{self.confidence:.0%} confiança)".replace(",", " "))


# Acima destes limiares de largura relativa, o intervalo é largo demais para
# ser accionável. Derivados do benchmark: a banda 0-5k tem largura mediana de
# ~127%, e é exatamente onde o erro é maior (MAPE 63%).
WIDTH_HIGH_RELIABILITY = 0.30
WIDTH_MEDIUM_RELIABILITY = 0.60
WIDTH_UNPUBLISHABLE = 1.00


class ConformalQuantileValuator:
    """Envolve três modelos quantílicos e calibra-os por conformalização.

    Espera estimadores compatíveis com scikit-learn que aceitem
    ``objective='quantile'`` (LightGBM) ou equivalente. O treino é feito em
    log1p(preço); a inferência devolve euros.
    """

    def __init__(self, alpha: float = 0.20, calib_fraction: float = 0.25,
                 model_factory=None, random_state: int = 42):
        if not 0 < alpha < 1:
            raise ValueError("alpha tem de estar entre 0 e 1")
        self.alpha = alpha
        self.calib_fraction = calib_fraction
        self.random_state = random_state
        self.model_factory = model_factory or self._default_factory
        self.q_lo: Any = None
        self.q_hi: Any = None
        self.q_mid: Any = None
        self.correction_: float = 0.0
        self.n_calib_: int = 0

    @staticmethod
    def _default_factory(quantile: float, random_state: int):
        import lightgbm as lgb
        return lgb.LGBMRegressor(
            objective="quantile", alpha=quantile, n_estimators=700,
            learning_rate=0.04, num_leaves=31, min_child_samples=8,
            subsample=0.85, subsample_freq=1, colsample_bytree=0.85,
            reg_lambda=2.0, random_state=random_state, verbose=-1, n_jobs=-1)

    # ------------------------------------------------------------- treino --

    def fit(self, X: np.ndarray, y: np.ndarray,
            calib_idx: Optional[Sequence[int]] = None) -> "ConformalQuantileValuator":
        """Ajusta os quantis e calcula a correção conformal.

        ``y`` em euros. Se ``calib_idx`` for dado, usa esses índices para
        calibração (útil para respeitar ordem temporal); caso contrário reserva
        a última fatia, que é a escolha certa para dados com deriva temporal.
        """
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if len(X) != len(y):
            raise ValueError("X e y com comprimentos diferentes")
        if len(X) < 50:
            raise ValueError(f"treino insuficiente para calibrar: {len(X)} linhas")

        if calib_idx is None:
            n_calib = max(int(len(X) * self.calib_fraction), 30)
            calib_idx = np.arange(len(X) - n_calib, len(X))
        calib_idx = np.asarray(calib_idx)
        proper_idx = np.setdiff1d(np.arange(len(X)), calib_idx)

        y_log = np.log1p(y)
        lo_q, hi_q = self.alpha / 2, 1 - self.alpha / 2

        self.q_lo = self.model_factory(lo_q, self.random_state)
        self.q_hi = self.model_factory(hi_q, self.random_state)
        self.q_mid = self.model_factory(0.5, self.random_state)
        for m in (self.q_lo, self.q_hi, self.q_mid):
            m.fit(X[proper_idx], y_log[proper_idx])

        # conformalização em espaço log -> margem multiplicativa
        lo_c = self.q_lo.predict(X[calib_idx])
        hi_c = self.q_hi.predict(X[calib_idx])
        y_c = y_log[calib_idx]
        scores = np.maximum(lo_c - y_c, y_c - hi_c)

        n = len(scores)
        level = min((1 - self.alpha) * (1 + 1 / n), 1.0)
        self.correction_ = float(np.quantile(scores, level))
        self.n_calib_ = n
        logger.info("CQR calibrado: n=%d correcao_log=%.4f (=%.1f%% multiplicativo)",
                    n, self.correction_, (np.exp(self.correction_) - 1) * 100)
        return self

    # ---------------------------------------------------------- inferencia --

    def predict_interval(self, X: np.ndarray) -> List[ValuationInterval]:
        if self.q_mid is None:
            raise RuntimeError("modelo não treinado — chama fit() primeiro")
        X = np.asarray(X, dtype=float)
        mid = np.expm1(self.q_mid.predict(X))
        lo = np.expm1(self.q_lo.predict(X) - self.correction_)
        hi = np.expm1(self.q_hi.predict(X) + self.correction_)

        lo = np.maximum(lo, 0.0)
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
        mid = np.clip(mid, lo, hi)

        out: List[ValuationInterval] = []
        for m, l, h in zip(mid, lo, hi):
            width = (h - l) / max(m, 1.0)
            if width <= WIDTH_HIGH_RELIABILITY:
                rel = "alta"
            elif width <= WIDTH_MEDIUM_RELIABILITY:
                rel = "media"
            else:
                rel = "baixa"
            out.append(ValuationInterval(
                estimate=float(m), lower=float(l), upper=float(h),
                confidence=1 - self.alpha, relative_width=float(width),
                reliability=rel, publishable=bool(width < WIDTH_UNPUBLISHABLE)))
        return out

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Estimativa pontual (mediana), para compatibilidade."""
        return np.expm1(self.q_mid.predict(np.asarray(X, dtype=float)))

    # ------------------------------------------------------------ avaliacao --

    @staticmethod
    def evaluate_coverage(intervals: List[ValuationInterval],
                          y_true: np.ndarray) -> Dict[str, float]:
        y_true = np.asarray(y_true, dtype=float)
        lo = np.array([i.lower for i in intervals])
        hi = np.array([i.upper for i in intervals])
        mid = np.array([i.estimate for i in intervals])
        inside = (y_true >= lo) & (y_true <= hi)
        return {
            "cobertura_pct": float(np.mean(inside) * 100),
            "largura_relativa_mediana_pct": float(
                np.median((hi - lo) / np.maximum(mid, 1)) * 100),
            "mape_pct": float(np.mean(np.abs(y_true - mid) / y_true) * 100),
            "n": int(len(y_true)),
        }
