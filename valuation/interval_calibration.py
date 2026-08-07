"""
Calibração conformal dos intervalos do HybridValuator.

Problema
--------
O ``HybridValuator`` já devolve ``value_low`` / ``value_high``, mas esses limites
são construídos por heurística — divergência entre métodos, multiplicadores fixos
(0.9, 1.1, 0.7, 0.85) afinados à mão. Ninguém verificou alguma vez que um
intervalo dito de "alta confiança" contém de facto o preço real com a frequência
que promete.

O benchmark de 06/08/2026 mostrou o que acontece quando não se verifica: os
intervalos quantílicos nominais de 80% continham apenas 50,5% dos preços reais.
Não há razão para supor que os heurísticos estejam melhor.

Solução
-------
Esta camada não substitui a lógica do valuator — mede-a e corrige-a.

1. Recolhe pares (intervalo previsto, preço observado) num conjunto de calibração.
2. Mede o desvio conformal necessário para atingir a cobertura pretendida.
3. Persiste um único fator multiplicativo por banda de preço.
4. Aplica esse fator na inferência e classifica a fiabilidade.

O fator é multiplicativo (calculado em espaço log) porque um erro de 500 € é
grave num carro de 3.000 € e irrelevante num de 80.000 €.

Uso
---
    # offline, uma vez por retreino
    cal = IntervalCalibrator()
    cal.fit(lows, highs, centers, actuals)
    cal.save()

    # em inferência
    cal = IntervalCalibrator.load()
    resultado = cal.apply(valuation_dict)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

__all__ = ["IntervalCalibrator", "DEFAULT_CALIBRATION_PATH"]

DEFAULT_CALIBRATION_PATH = (
    Path(__file__).resolve().parent.parent / "models" / "interval_calibration.json")

# Bandas de preço: o erro relativo comporta-se de forma muito diferente em cada
# uma (0-5k tem MAPE 64%, 15-30k tem 12%), por isso a correção é por banda.
PRICE_BANDS: List[tuple] = [
    (0, 5_000, "0k-5k"),
    (5_000, 15_000, "5k-15k"),
    (15_000, 30_000, "15k-30k"),
    (30_000, 60_000, "30k-60k"),
    (60_000, float("inf"), "60k+"),
]

# Largura relativa acima da qual a avaliação não é accionável.
WIDTH_HIGH = 0.30
WIDTH_MEDIUM = 0.60
WIDTH_UNPUBLISHABLE = 1.00


def band_of(price: float) -> str:
    for lo, hi, label in PRICE_BANDS:
        if lo <= price < hi:
            return label
    return PRICE_BANDS[-1][2]


@dataclass
class CalibrationReport:
    """O que a calibração encontrou — para registo e auditoria."""

    coverage_before: float
    coverage_after: float
    target: float
    median_width_before: float
    median_width_after: float
    n: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "cobertura_antes_pct": round(self.coverage_before, 2),
            "cobertura_depois_pct": round(self.coverage_after, 2),
            "alvo_pct": round(self.target * 100, 2),
            "largura_mediana_antes_pct": round(self.median_width_before, 2),
            "largura_mediana_depois_pct": round(self.median_width_after, 2),
            "n": self.n,
        }


class IntervalCalibrator:
    """Corrige os intervalos do valuator para atingirem a cobertura prometida."""

    def __init__(self, target_coverage: float = 0.80,
                 path: Optional[Path] = None):
        if not 0 < target_coverage < 1:
            raise ValueError("target_coverage tem de estar entre 0 e 1")
        self.target_coverage = target_coverage
        self.path = Path(path) if path else DEFAULT_CALIBRATION_PATH
        # fator multiplicativo de alargamento, por banda
        self.factors: Dict[str, float] = {}
        self.global_factor: float = 1.0
        self.report_: Optional[CalibrationReport] = None
        self.fitted_at_: Optional[str] = None

    # ---------------------------------------------------------------- fit --

    def fit(self, lows: Sequence[float], highs: Sequence[float],
            centers: Sequence[float], actuals: Sequence[float]) -> "IntervalCalibrator":
        """Calcula o alargamento necessário a partir de dados de calibração.

        ``actuals`` é o preço observado (pedido ou de venda). O fator resultante
        é o quantil da razão necessária para conter o alvo de cobertura.
        """
        lo = np.asarray(lows, dtype=float)
        hi = np.asarray(highs, dtype=float)
        mid = np.asarray(centers, dtype=float)
        y = np.asarray(actuals, dtype=float)
        if not (len(lo) == len(hi) == len(mid) == len(y)):
            raise ValueError("todas as sequências têm de ter o mesmo comprimento")
        if len(y) < 50:
            raise ValueError(f"calibração precisa de >=50 amostras, recebeu {len(y)}")

        valid = (mid > 0) & (y > 0) & (hi >= lo)
        lo, hi, mid, y = lo[valid], hi[valid], mid[valid], y[valid]

        inside_before = (y >= lo) & (y <= hi)
        width_before = (hi - lo) / np.maximum(mid, 1)

        # Quanto teria de esticar cada meio-intervalo para conter o real.
        # Em espaço log para ser multiplicativo e simétrico.
        eps = 1e-9
        need_up = np.log(np.maximum(y, eps)) - np.log(np.maximum(hi, eps))
        need_down = np.log(np.maximum(lo, eps)) - np.log(np.maximum(y, eps))
        score = np.maximum(need_up, need_down)  # <=0 se já está dentro

        n = len(score)
        level = min(self.target_coverage * (1 + 1 / n), 1.0)
        self.global_factor = float(np.exp(max(np.quantile(score, level), 0.0)))

        # Por banda, quando há amostras suficientes.
        bands = np.array([band_of(v) for v in y])
        for _, _, label in PRICE_BANDS:
            m = bands == label
            if m.sum() >= 30:
                lvl = min(self.target_coverage * (1 + 1 / m.sum()), 1.0)
                self.factors[label] = float(
                    np.exp(max(np.quantile(score[m], lvl), 0.0)))

        new_lo = lo / np.array([self.factor_for(v) for v in mid])
        new_hi = hi * np.array([self.factor_for(v) for v in mid])
        inside_after = (y >= new_lo) & (y <= new_hi)
        width_after = (new_hi - new_lo) / np.maximum(mid, 1)

        self.report_ = CalibrationReport(
            coverage_before=float(np.mean(inside_before) * 100),
            coverage_after=float(np.mean(inside_after) * 100),
            target=self.target_coverage,
            median_width_before=float(np.median(width_before) * 100),
            median_width_after=float(np.median(width_after) * 100),
            n=int(n))
        self.fitted_at_ = datetime.now(timezone.utc).isoformat()
        logger.info("Calibração: cobertura %.1f%% -> %.1f%% (alvo %.0f%%)",
                    self.report_.coverage_before, self.report_.coverage_after,
                    self.target_coverage * 100)
        return self

    def factor_for(self, center: float) -> float:
        return self.factors.get(band_of(float(center)), self.global_factor)

    # -------------------------------------------------------------- apply --

    def apply(self, valuation: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica a correção a um resultado do HybridValuator.

        Acrescenta ``value_low_calibrated``, ``value_high_calibrated``,
        ``interval_reliability`` e ``publishable``. Não altera
        ``estimated_value`` — a estimativa central é da responsabilidade do
        valuator, esta camada só trata da incerteza.
        """
        out = dict(valuation)
        value = float(valuation.get("estimated_value") or 0)
        lo = float(valuation.get("value_low") or 0)
        hi = float(valuation.get("value_high") or 0)
        if value <= 0 or hi < lo:
            out["publishable"] = False
            out["interval_reliability"] = "insuficiente"
            return out

        f = self.factor_for(value)
        new_lo = max(lo / f, 300.0)
        new_hi = max(hi * f, new_lo * 1.05)
        width = (new_hi - new_lo) / max(value, 1.0)

        if width <= WIDTH_HIGH:
            rel = "alta"
        elif width <= WIDTH_MEDIUM:
            rel = "media"
        else:
            rel = "baixa"

        out["value_low_calibrated"] = round(new_lo, 2)
        out["value_high_calibrated"] = round(new_hi, 2)
        out["interval_relative_width"] = round(width, 4)
        out["interval_reliability"] = rel
        out["interval_target_coverage"] = self.target_coverage
        out["publishable"] = bool(width < WIDTH_UNPUBLISHABLE)
        return out

    # ------------------------------------------------------------ persist --

    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path else self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "target_coverage": self.target_coverage,
            "global_factor": self.global_factor,
            "factors": self.factors,
            "fitted_at": self.fitted_at_,
            "report": self.report_.as_dict() if self.report_ else None,
        }
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                          encoding="utf-8")
        logger.info("Calibração guardada em %s", target)
        return target

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Optional["IntervalCalibrator"]:
        """Carrega a calibração. Devolve None se não existir — o chamador deve
        então usar os intervalos heurísticos e saber que não estão calibrados."""
        target = Path(path) if path else DEFAULT_CALIBRATION_PATH
        if not target.exists():
            logger.warning("Sem ficheiro de calibração em %s — intervalos "
                           "ficam por calibrar", target)
            return None
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Calibração ilegível (%s): %s", target, exc)
            return None
        obj = cls(target_coverage=data.get("target_coverage", 0.80), path=target)
        obj.global_factor = float(data.get("global_factor", 1.0))
        obj.factors = {k: float(v) for k, v in (data.get("factors") or {}).items()}
        obj.fitted_at_ = data.get("fitted_at")
        return obj
