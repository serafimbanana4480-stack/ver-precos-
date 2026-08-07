"""
Hybrid Vehicle Valuator (v2)
============================

Motor de avaliação híbrido que combina, com pesos dependentes da confiança:

1. **Comparáveis estatísticos** — hierarquia progressiva de segmentos
   (marca+modelo+ano → ±1 ano → marca+modelo → marca+segmento → marca →
   segmento global), sempre com exclusão do próprio anúncio e estatística
   robusta (mediana ponderada, IQR).
2. **Modelo ML** (XGBoost/LightGBM/CatBoost via PricePredictor) — apenas
   quando o artefacto carrega corretamente e passa na validação de sanidade.
3. **Referência externa de mercado** (:mod:`valuation.market_reference`) —
   âncoras PVP + curvas de depreciação, independente da base de dados.

Princípios v2 (em resposta à auditoria de 2026-08-01):

* Nunca inventar valores fixos universais (os antigos ``500``/``10000``).
  Quando não há referência fiável, o resultado é ``estimated_value=None`` com
  ``confidence_label="insufficient_data"`` e ``deal_score`` neutro.
* Nunca transformar dados desconhecidos em zero (o antigo ``year or 0``).
  Campos em falta reduzem a confiança e ficam registados em
  ``features_missing``/``warnings``.
* A exclusão do próprio anúncio nunca termina a procura: se um bucket fica
  vazio, o nível seguinte da hierarquia é testado.
* Scores extremos exigem confiança alta; confiança baixa limita o score a uma
  faixa neutra.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from database.db import get_db_context
from database.models import Vehicle
from config import settings

logger = logging.getLogger(__name__)

VALUATION_VERSION = "v2.3"

# Fontes de leilão: o preço é uma transação real (âncora), não um ask de retalho.
AUCTION_SOURCES = (
    "LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA",
    "AUTOLINE", "MARTELO", "PENHORADO",
)

# Número mínimo de comparáveis por nível de confiança (configurável).
MIN_COMPS_HIGH = 15
MIN_COMPS_MEDIUM = 5
MIN_COMPS_LOW = 2

# Pesos máximos de cada método na combinação final.
_W_STATS = 0.60
_W_ML = 0.25
_W_REF = 0.40


# ---------------------------------------------------------------------------
# Parsing explícito de valores opcionais (nunca "or 0")
# ---------------------------------------------------------------------------

def parse_optional_int(value: Any) -> Optional[int]:
    """Converte para int ou devolve None. Distingue ausente de zero real."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_key(value: Any) -> str:
    return str(value).strip().lower() if value else "unknown"


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """Mediana ponderada (50º percentil ponderado)."""
    if len(values) == 0:
        return float("nan")
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w)
    cutoff = 0.5 * cum[-1]
    return float(v[min(np.searchsorted(cum, cutoff), len(v) - 1)])


def _robust_center(values: List[float], weights: Optional[List[float]] = None) -> Optional[float]:
    """Centro robusto: mediana (ponderada se houver pesos)."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return None
    if weights is not None and len(weights) == len(arr) and sum(weights) > 0:
        return _weighted_median(arr, np.asarray(weights, dtype=float))
    return float(np.median(arr))


def _iqr_interval(values: List[float], center: float) -> Tuple[float, float]:
    """Intervalo [Q25, Q75] alargado 25%, centrado na mediana dos comparáveis."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) >= 4:
        q25, q75 = np.percentile(arr, [25, 75])
        spread = max((q75 - q25) * 0.75, center * 0.08)
    else:
        spread = center * 0.15
    return center - spread, center + spread


# ---------------------------------------------------------------------------
# Valuator
# ---------------------------------------------------------------------------

class HybridValuator:
    """Hybrid valuation engine (v2). Ver docstring do módulo."""

    def __init__(self):
        self.ml_model = None          # backward-compat: predictor de carros
        self.ml_available = False
        self.ml_r2 = 0.0
        self.ml_error: Optional[str] = None
        self.ml_models: Dict[str, Any] = {}   # vehicle_type -> PricePredictor
        self.ml_r2_by_type: Dict[str, float] = {}
        self.segment_rows: List[Dict[str, Any]] = []
        self._load_ml_model()
        self._compute_segment_stats()

    # ------------------------------------------------------------------ ML --

    def _load_ml_model(self):
        """Carrega UM predictor por tipo de veículo, de forma defensiva.

        Cada tipo usa apenas o seu próprio artefacto — nunca se aplica o
        modelo de carros a motos (vies histórico: com o artefacto de motos
        em falta, o fallback para carros avaliava motas com lógica de carro).
        Um artefacto em falta/incompatível desativa a componente ML APENAS
        desse tipo, com erro explícito.
        """
        try:
            from valuation.predict import PricePredictor

            errors = []
            for vtype in ("carros", "motos"):
                predictor = PricePredictor(vtype)
                if predictor.model is not None and getattr(predictor, "model_loaded_ok", False):
                    r2 = predictor.metrics.get("r2", 0) or 0.0
                    if r2 >= 0.30:
                        self.ml_models[vtype] = predictor
                        self.ml_r2_by_type[vtype] = r2
                        logger.info("ML model loaded for %s (R²=%.3f)", vtype, r2)
                    else:
                        errors.append(f"{vtype}: R²={r2:.2f} < 0.30")
                elif predictor.load_error:
                    errors.append(f"{vtype}: {predictor.load_error}")

            # Backward-compat: atributos agregados apontam para carros (métricas).
            if "carros" in self.ml_models:
                self.ml_model = self.ml_models["carros"]
                self.ml_r2 = self.ml_r2_by_type["carros"]
            elif self.ml_models:
                first = next(iter(self.ml_models))
                self.ml_model = self.ml_models[first]
                self.ml_r2 = self.ml_r2_by_type[first]
            self.ml_available = bool(self.ml_models)
            self.ml_error = "; ".join(errors) if errors else None
            if not self.ml_available:
                logger.warning("Nenhum modelo ML utilizável: %s", self.ml_error or "sem artefactos")
        except Exception as e:  # pragma: no cover - defesa extrema
            self.ml_error = f"{type(e).__name__}: {e}"
            logger.error("Falha ao carregar modelo ML: %s", self.ml_error, exc_info=True)

    def _ml_predict_for(self, vtype: str, vehicle_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Previsão ML para o tipo correto + intervalo band-aware.

        O intervalo usa o MAPE do segmento de routing (LOW/FULL/HIGH) em vez
        do MAPE global — nos extremos o erro real é muito maior e o intervalo
        tem de o refletir (evita deal scores sobreconfiantes em <5k e >60k).
        """
        predictor = self.ml_models.get("motos" if str(vtype).lower().startswith("moto") else "carros")
        if predictor is None:
            return None
        pred = predictor.predict(vehicle_data)
        if not pred or pred <= 0:
            return None

        mape = (predictor.metrics.get("mape_pct", 30.0) or 30.0) / 100.0
        band = "FULL"
        high_model = getattr(predictor, "high_model", None)
        high_threshold = getattr(predictor, "high_threshold", None)
        low_model = getattr(predictor, "low_model", None)
        low_threshold = getattr(predictor, "low_threshold", None)
        if high_model is not None and high_threshold and pred >= high_threshold:
            band = "HIGH"
            hm = getattr(predictor, "high_metrics", {}).get("mape_pct")
            if hm:
                mape = hm / 100.0
        elif low_model is not None and low_threshold and pred < low_threshold:
            band = "LOW"
            lm = getattr(predictor, "low_metrics", {}).get("mape_pct")
            if lm:
                mape = lm / 100.0

        ml_conf = max(0.2, min(0.8, 1.0 - mape))
        return {
            "value": float(pred),
            "low": float(pred * (1 - mape)),
            "high": float(pred * (1 + mape)),
            "comparables": 0,
            "confidence": round(ml_conf, 3),
            "method": "ml_model",
            "reference_level": 0,
            "note": f"Modelo {predictor.model_name} band={band} (R²={self.ml_r2_by_type.get('motos' if str(vtype).lower().startswith('moto') else 'carros', 0):.2f}, MAPE={mape * 100:.0f}%)",
        }

    # -------------------------------------------------------- segment stats --

    def _compute_segment_stats(self):
        """Carrega anúncios ativos e prepara índices multi-nível.

        Ao contrário da v1, anúncios SEM ano também entram (contribuem para
        os níveis marca+modelo / marca), e guardamos ano/km/fonte para
        ponderação por distância.
        """
        with get_db_context() as db:
            from sqlalchemy import or_
            vehicles = db.query(Vehicle).filter(
                Vehicle.is_active == True,  # noqa: E712
                Vehicle.price.isnot(None),
                Vehicle.price > 0,
                Vehicle.quality_status.in_(("valid", "valid_with_warning")),
            ).all()

            rows: List[Dict[str, Any]] = []
            for v in vehicles:
                src = v.source.value if v.source else ""
                if src in AUCTION_SOURCES:
                    # Leilões não são comparáveis de retalho.
                    continue
                rows.append({
                    "id": int(v.id),
                    "brand": _norm_key(v.brand),
                    "model": _norm_key(v.model),
                    "version": _norm_key(v.version),
                    "year": int(v.year) if v.year else None,
                    "price": float(v.price),
                    "km": int(v.km) if v.km else None,
                    "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
                    "transmission": v.transmission.value if v.transmission else "unknown",
                    "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros",
                })

        self.segment_rows = rows
        self._build_indexes(rows)

    def _build_indexes(self, rows: List[Dict[str, Any]]) -> None:
        """Constrói todos os índices a partir das linhas (separado da carga
        para permitir injeção direta de dados em testes)."""
        if not rows:
            logger.warning("Sem dados para estatísticas de segmento")
            self._idx_bmy, self._idx_bm, self._idx_bmf = {}, {}, {}
            self._idx_b, self._idx_all, self._idx_seg, self._idx_bseg = {}, {}, {}, {}
            self.depreciation, self.segment_depreciation = {}, {}
            return

        # Índices auxiliares: (nível) -> chave -> lista de índices de linha
        def _index(key_fn):
            idx: Dict[Any, List[int]] = {}
            for i, r in enumerate(rows):
                k = key_fn(r)
                if k is not None:
                    idx.setdefault(k, []).append(i)
            return idx

        self._idx_bmy = _index(lambda r: (r["vehicle_type"], r["brand"], r["model"], r["year"]) if r["year"] else None)
        self._idx_bm = _index(lambda r: (r["vehicle_type"], r["brand"], r["model"]))
        self._idx_bmf = _index(lambda r: (r["vehicle_type"], r["brand"], r["model"], r["fuel_type"]))
        self._idx_b = _index(lambda r: (r["vehicle_type"], r["brand"]))
        self._idx_all = _index(lambda r: r["vehicle_type"])

        # Segmento de mercado (via referência externa) por linha
        try:
            from valuation.market_reference import resolve_segment
            for r in rows:
                r["segment"] = resolve_segment(
                    r["brand"], r["model"], r["vehicle_type"], r["fuel_type"]
                )
        except Exception as exc:  # pragma: no cover
            logger.debug("resolve_segment indisponível: %s", exc)
            for r in rows:
                r["segment"] = "media"
        self._idx_seg = _index(lambda r: (r["vehicle_type"], r["segment"]))
        self._idx_bseg = _index(lambda r: (r["vehicle_type"], r["brand"], r["segment"]))

        # Curvas de depreciação por marca (€/ano) e globais por segmento
        self.depreciation = self._fit_depreciation(rows, key=lambda r: (r["vehicle_type"], r["brand"]))
        self.segment_depreciation = self._fit_depreciation(rows, key=lambda r: (r["vehicle_type"], r["segment"]))

        logger.info(
            "Segment stats: %d anúncios | %d BMY | %d BM | %d marcas",
            len(rows), len(self._idx_bmy), len(self._idx_bm), len(self._idx_b),
        )

    @staticmethod
    def _fit_depreciation(rows, key) -> Dict[Any, float]:
        """Declínio anual típico (€/ano) por grupo, via medianas por ano."""
        by_group: Dict[Any, Dict[int, List[float]]] = {}
        for r in rows:
            if r["year"]:
                by_group.setdefault(key(r), {}).setdefault(r["year"], []).append(r["price"])
        out: Dict[Any, float] = {}
        for g, year_prices in by_group.items():
            if len(year_prices) < 2:
                continue
            med = {y: float(np.median(p)) for y, p in year_prices.items() if len(p) >= 1}
            if len(med) < 2:
                continue
            years = sorted(med)
            span = years[-1] - years[0]
            if span > 0:
                drop = med[years[0]] - med[years[-1]]
                if drop > 0:
                    out[g] = drop / span
        return out

    @classmethod
    def from_rows(cls, rows: List[Dict[str, Any]], ml_model=None, ml_r2: float = 0.0) -> "HybridValuator":
        """Constrói um avaliador sem BD (testes/demonstração).

        ``rows`` segue o formato interno de ``segment_rows``.
        """
        inst = cls.__new__(cls)
        inst.ml_model = ml_model
        inst.ml_available = ml_model is not None and ml_r2 >= 0.30
        inst.ml_r2 = ml_r2
        inst.ml_error = None
        # from_rows aceita um único predictor legado: assume-se "carros"
        inst.ml_models = {"carros": ml_model} if ml_model is not None else {}
        inst.ml_r2_by_type = {"carros": ml_r2} if ml_model is not None else {}
        normalized = []
        for r in rows:
            row = dict(r)
            row.setdefault("version", "unknown")
            row.setdefault("vehicle_type", "carros")
            row.setdefault("fuel_type", "unknown")
            row.setdefault("transmission", "unknown")
            row.setdefault("km", None)
            row.setdefault("year", None)
            normalized.append(row)
        inst.segment_rows = normalized
        inst._build_indexes(normalized)
        return inst

    # ------------------------------------------------------------ internals --

    def _exclude_self(self, indices: List[int], self_id: Optional[int],
                      self_price: Optional[float]) -> List[int]:
        out = []
        for i in indices:
            r = self.segment_rows[i]
            if self_id is not None and r["id"] == self_id:
                continue
            out.append(i)
        # Se só sobrar o próprio preço (sem id), remove uma ocorrência exata.
        if self_id is None and self_price is not None and len(out) > 1:
            for j, i in enumerate(out):
                if abs(self.segment_rows[i]["price"] - self_price) < 0.01:
                    out.pop(j)
                    break
        return out

    @staticmethod
    def _fit_km_elasticity(pairs) -> Optional[float]:
        """Elasticidade preço-km (log-log): ``log(price) ~ b * log(km)``.

        Num mercado maduro, para o mesmo modelo/ano, dobrar os km reduz o
        preço ~15-25 % (b ∈ [−0.35, −0.15]). Ajuste por mínimos quadrados
        sobre os comparáveis com km conhecido; devolve ``None`` quando não há
        relação km→preço identificável (dados ralos ou ruído).
        """
        vals = [
            (km, price) for km, price in pairs
            if km and price and km > 0 and price > 0
        ]
        if len(vals) < 4:
            return None
        x = np.log(np.fromiter((km for km, _ in vals), dtype=float))
        y = np.log(np.fromiter((price for _, price in vals), dtype=float))
        xm, ym = x.mean(), y.mean()
        den = float(((x - xm) ** 2).sum())
        if den <= 0:
            return None
        slope = float(((x - xm) * (y - ym)).sum() / den)
        if slope > -0.02:
            return None
        return slope

    def _level_estimate(
        self,
        indices: List[int],
        target: Dict[str, Any],
        level: int,
        method: str,
        level_penalty: float,
    ) -> Optional[Dict[str, Any]]:
        """Estima a partir de um conjunto de comparáveis (mediana ponderada).

        Ponderação por distância de ano e quilometragem quando esses dados
        existem dos dois lados; nunca assume 0 para dados em falta. Com
        comparáveis suficientes com km, o valor é ainda corrigido para o km
        do alvo (elasticidade log-log) — sem isto, um carro com 250 000 km é
        avaliado ao preço de um com 120 000 km.
        """
        if len(indices) < MIN_COMPS_LOW:
            return None

        t_year = target.get("year")
        t_km = target.get("km")
        prices, weights = [], []
        km_pairs: List[Tuple[float, float]] = []
        for i in indices:
            r = self.segment_rows[i]
            w = 1.0
            if t_year and r["year"]:
                w *= 1.0 / (1.0 + abs(t_year - r["year"]))
            if t_km and r["km"]:
                w *= 1.0 / (1.0 + abs(t_km - r["km"]) / 60000.0)
            prices.append(r["price"])
            weights.append(w)
            if t_km and r["km"]:
                km_pairs.append((float(r["km"]), float(r["price"])))

        center = _robust_center(prices, weights)
        if center is None or center <= 0:
            return None

        n = len(prices)
        # Ajuste temporal apenas quando o ano é conhecido (nunca assumir ano 0).
        year_note = None
        if t_year and level >= 3:
            comp_years = [self.segment_rows[i]["year"] for i in indices if self.segment_rows[i]["year"]]
            if comp_years:
                med_year = float(np.median(comp_years))
                dep_key = (target["vehicle_type"], target["brand"])
                dep = self.depreciation.get(dep_key)
                if dep is None:
                    dep = self.segment_depreciation.get((target["vehicle_type"], target.get("segment")), 900.0)
                year_diff = t_year - med_year
                if abs(year_diff) >= 1:
                    center = center + year_diff * dep
                    year_note = f"Ajuste temporal: {year_diff:+.0f} anos × €{dep:.0f}/ano"

        # Ajuste por quilometragem: extrapola da mediana dos comparáveis para
        # o km do alvo. Fator limitado a [0.6, 1.4] para nunca fabricar
        # valores fora da vizinhança dos dados observados.
        km_note = None
        if t_km and t_km > 0 and len(km_pairs) >= 4:
            slope = self._fit_km_elasticity(km_pairs)
            med_km = float(np.median([k for k, _ in km_pairs]))
            if slope is not None and med_km > 0 and abs(med_km - t_km) > 1000:
                factor = float(min(max((t_km / med_km) ** slope, 0.6), 1.4))
                if abs(factor - 1.0) > 0.02:
                    center = center * factor
                    km_note = (
                        f"Ajuste km: {t_km:,.0f} km vs mediana {med_km:,.0f} km "
                        f"({factor:+.0%})".replace(",", ".")
                    )

        # Limites data-driven (nunca constantes universais): a estimativa não
        # pode sair da vizinhança dos comparáveis usados — evita valores
        # negativos por ajuste temporal e extrapolações absurdas.
        arr = np.asarray(prices, dtype=float)
        p10, p90 = np.percentile(arr, [10, 90])
        center = float(min(max(center, p10 * 0.5), p90 * 2.0))
        low, high = _iqr_interval(prices, center)

        if n >= MIN_COMPS_HIGH:
            conf = 0.85
        elif n >= MIN_COMPS_MEDIUM:
            conf = 0.65
        else:
            conf = 0.45
        conf = max(0.15, conf * level_penalty)

        return {
            "value": float(center),
            "low": float(min(low, center)),
            "high": float(max(high, center)),
            "comparables": n,
            "confidence": round(conf, 3),
            "method": method,
            "reference_level": level,
            "note": " · ".join(n for n in (year_note, km_note) if n) or None,
        }

    def _statistical_estimate(self, vehicle_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Hierarquia progressiva de comparáveis (nunca devolve antes de
        testar todos os níveis válidos)."""
        brand = _norm_key(vehicle_data.get("brand"))
        model = _norm_key(vehicle_data.get("model"))
        vtype = str(vehicle_data.get("vehicle_type") or "carros").lower()
        if vtype not in ("carros", "motos"):
            vtype = "carros"
        fuel = _norm_key(vehicle_data.get("fuel_type"))
        year = parse_optional_int(vehicle_data.get("year"))
        km = parse_optional_int(vehicle_data.get("km"))
        self_id = parse_optional_int(vehicle_data.get("id"))
        self_price = parse_optional_float(vehicle_data.get("price"))

        target = {"vehicle_type": vtype, "brand": brand, "year": year, "km": km}
        try:
            from valuation.market_reference import resolve_segment
            target["segment"] = resolve_segment(brand, model, vtype, fuel)
        except Exception:
            target["segment"] = "media"

        if brand in ("unknown", ""):
            return None

        levels: List[Tuple[int, str, float, List[int]]] = []

        # L1: marca+modelo+ano (mín. 2)
        if year:
            idx = self._exclude_self(self._idx_bmy.get((vtype, brand, model, year), []), self_id, self_price)
            levels.append((1, "brand_model_year", 1.0, idx))
            # L2: marca+modelo+ano±1
            idx2 = []
            for dy in (-1, 1):
                idx2 += self._idx_bmy.get((vtype, brand, model, year + dy), [])
            idx2 = self._exclude_self(idx2, self_id, self_price)
            levels.append((2, "brand_model_year_pm1", 0.92, idx2))

        # L3: marca+modelo+combustível (mín. 2, ajuste temporal)
        if fuel != "unknown":
            idx = self._exclude_self(self._idx_bmf.get((vtype, brand, model, fuel), []), self_id, self_price)
            levels.append((3, "brand_model_fuel", 0.88, idx))

        # L4: marca+modelo (mín. 2, ajuste temporal)
        idx = self._exclude_self(self._idx_bm.get((vtype, brand, model), []), self_id, self_price)
        levels.append((4, "brand_model", 0.85 if year else 0.8, idx))

        # L5: marca+segmento (mín. 3, ajuste temporal)
        idx = self._exclude_self(self._idx_bseg.get((vtype, brand, target["segment"]), []), self_id, self_price)
        levels.append((5, "brand_segment", 0.62, idx))

        # L6: marca (mín. 3, ajuste temporal)
        idx = self._exclude_self(self._idx_b.get((vtype, brand), []), self_id, self_price)
        levels.append((6, "brand_only", 0.55, idx))

        # L7: segmento global (mín. 5, ajuste temporal)
        idx = self._exclude_self(self._idx_seg.get((vtype, target["segment"]), []), self_id, self_price)
        levels.append((7, "segment_global", 0.42, idx))

        for level, method, penalty, indices in levels:
            min_needed = MIN_COMPS_LOW if level <= 4 else 3
            if len(indices) < min_needed:
                continue
            est = self._level_estimate(indices, target, level, method, penalty)
            if est is not None:
                return est
        return None

    # ------------------------------------------------------------- auction --

    def _auction_estimate(self, vehicle_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Leilões: o preço de adjudicação é a âncora real; o valor de
        revenda é um múltiplo conservador + custos de reparação."""
        price = parse_optional_float(vehicle_data.get("price"))
        if not price or price <= 0:
            return None
        year = parse_optional_int(vehicle_data.get("year"))
        km = parse_optional_int(vehicle_data.get("km"))
        if not year:
            mult = 1.6  # sem ano: não assumir carro velho
        else:
            age = max(0, pd.Timestamp.now().year - year)
            kmv = km if km else 120000
            if age > 15 or kmv > 250000:
                mult = 3.5
            elif age > 10 or kmv > 150000:
                mult = 2.5
            elif age > 5:
                mult = 2.0
            else:
                mult = 1.6
        repair = self._estimate_repair_costs(parse_optional_float(vehicle_data.get("condition_score")) or 3.0)
        est = price * mult + repair

        # Teto data-driven em vez do antigo cap fixo de €60 000 (que cortava
        # Porsche/Mercedes de leilão para valores irrealistas): se a referência
        # de mercado conhece o modelo, o teto é a banda alta da referência
        # (+15%); senão, um múltiplo absoluto do preço de adjudicação.
        bound = price * 4.5
        bound_note = None
        try:
            from valuation.market_reference import estimate_reference_value

            ref = estimate_reference_value(
                brand=vehicle_data.get("brand"),
                model=vehicle_data.get("model"),
                year=year,
                km=km,
                fuel_type=vehicle_data.get("fuel_type"),
                vehicle_type=str(vehicle_data.get("vehicle_type") or "carros"),
                engine_cc=parse_optional_int(vehicle_data.get("engine_size")),
            )
            if ref.get("value") and ref.get("confidence", 0) >= 0.4:
                bound = max(price * 1.2, float(ref["high"]) * 1.15)
                bound_note = f"teto ref. mercado €{bound:,.0f}".replace(",", ".")
        except Exception:  # pragma: no cover
            pass

        est = min(est, bound)
        est = max(est, price)
        high = min(est * 1.25, bound)
        note = f"Leilão: €{price:.0f} × {mult} + €{repair:.0f} reparação"
        if bound_note:
            note += f" ({bound_note})"
        return {
            "value": float(est),
            "low": float(max(price, est * 0.8)),
            "high": float(max(high, est)),
            "comparables": 0,
            "confidence": 0.5 if year else 0.35,
            "method": "auction_resale_multiple",
            "reference_level": 0,
            "note": note,
        }

    # ------------------------------------------------------------------ API --

    def estimate(self, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Avaliação estruturada completa (v2).

        Devolve sempre um dict com estimated_value (pode ser None),
        intervalo, confiança, método, avisos e explicação.
        """
        warnings: List[str] = []
        missing: List[str] = []
        price = parse_optional_float(vehicle_data.get("price"))

        year = parse_optional_int(vehicle_data.get("year"))
        km = parse_optional_int(vehicle_data.get("km"))
        if year is None:
            missing.append("year")
        elif year < 1950 or year > pd.Timestamp.now().year + 1:
            warnings.append(f"Ano {year} impossível — ignorado na avaliação.")
            year = None
            missing.append("year")
        if km is None:
            missing.append("km")
        if not vehicle_data.get("fuel_type") or _norm_key(vehicle_data.get("fuel_type")) == "unknown":
            missing.append("fuel_type")
        if not vehicle_data.get("transmission") or _norm_key(vehicle_data.get("transmission")) == "unknown":
            missing.append("transmission")

        source = str(vehicle_data.get("source", "")).upper()
        vtype = str(vehicle_data.get("vehicle_type") or "carros")

        candidates: List[Tuple[float, Dict[str, Any]]] = []  # (peso, estimativa)

        # 1) Leilões: caminho dedicado (não usa comparáveis de retalho).
        if source in AUCTION_SOURCES:
            est = self._auction_estimate(vehicle_data)
            if est:
                candidates.append((0.9, est))

        # 2) Comparáveis estatísticos
        stats_est = self._statistical_estimate(vehicle_data)
        if stats_est:
            candidates.append((_W_STATS * (0.4 + 0.6 * stats_est["confidence"]), stats_est))

        # 3) Modelo ML (apenas do tipo correto; nunca carros→motos)
        ml_est = None
        if self.ml_available:
            try:
                ml_est = self._ml_predict_for(vtype, vehicle_data)
                if ml_est is None and not str(vtype).lower().startswith("moto") \
                        and "carros" not in self.ml_models:
                    warnings.append("Modelo ML de carros indisponível.")
                if ml_est:
                    candidates.append((_W_ML * ml_est["confidence"], ml_est))
            except Exception as e:
                logger.warning(
                    "ML prediction falhou (%s: %s) | anúncio=%s",
                    type(e).__name__, e, vehicle_data.get("id"),
                )
                warnings.append("Previsão ML falhou; ignorada na combinação.")

        # 4) Referência externa de mercado
        ref_est = None
        try:
            from valuation.market_reference import estimate_reference_value

            ref = estimate_reference_value(
                brand=vehicle_data.get("brand"),
                model=vehicle_data.get("model"),
                year=year,
                km=km,
                fuel_type=vehicle_data.get("fuel_type"),
                vehicle_type=vtype,
                engine_cc=parse_optional_int(vehicle_data.get("engine_size")),
            )
            if ref.get("value") and ref.get("confidence", 0) > 0:
                ref_est = {
                    "value": float(ref["value"]),
                    "low": float(ref["low"]),
                    "high": float(ref["high"]),
                    "comparables": 0,
                    "confidence": float(ref["confidence"]),
                    "method": "market_reference",
                    "reference_level": 8,
                    "note": "; ".join(ref.get("notes", [])[:2]),
                }
                candidates.append((_W_REF * ref["confidence"], ref_est))
            elif ref.get("method") == "sem_referencia":
                warnings.append("Modelo sem âncora de PVP na referência de mercado.")
        except Exception as exc:
            logger.debug("Referência externa indisponível: %s", exc)

        # ---------------- combinação ----------------
        if not candidates:
            return self._insufficient_result(vehicle_data, missing, warnings)

        total_w = sum(w for w, _ in candidates)
        value = sum(w * c["value"] for w, c in candidates) / total_w
        low = sum(w * c["low"] for w, c in candidates) / total_w
        high = sum(w * c["high"] for w, c in candidates) / total_w
        base_conf = max(c["confidence"] for _, c in candidates)
        primary = max(candidates, key=lambda wc: wc[0])[1]

        # Divergência entre métodos → alargar intervalo e reduzir confiança.
        if len(candidates) >= 2:
            vals = [c["value"] for _, c in candidates]
            spread = (max(vals) - min(vals)) / max(1.0, np.mean(vals))
            if spread > 0.45:
                base_conf *= 0.6
                low = min(low, min(vals) * 0.9)
                high = max(high, max(vals) * 1.1)
                warnings.append(
                    f"Métodos divergem {spread:.0%}; confiança reduzida e intervalo alargado."
                )
            elif spread > 0.30:
                base_conf *= 0.8
                warnings.append(f"Métodos divergem {spread:.0%}.")

        # Dados em falta reduzem a confiança (sem inventar valores).
        if "year" in missing:
            base_conf *= 0.7
        if "km" in missing:
            base_conf *= 0.85

        # Guarda de scooters 125cc (vies histórico do modelo)
        title = str(vehicle_data.get("title", "")).lower()
        model_str = str(vehicle_data.get("model", "")).lower()
        is_scooter = any(kw in (title + " " + model_str) for kw in (
            'pcx', 'scooter', 'vespa', 'liberty', 'nmax', 'xmax', 'forza',
            'sh125', 'sh150', 'medley', 'burgman', 'vision', 'sh125i', 'nss'))
        if vtype == "motos" and is_scooter and price and price > 100 and value > price * 1.8:
            warnings.append("Estimativa limitada: scooter 125cc não pode valer várias vezes o ask.")
            value = price * 1.8
            high = min(high, price * 2.2)
            base_conf *= 0.7

        # Sanidade final contra a referência de mercado
        uncorrected_value = value
        try:
            from valuation.market_reference import validate_estimate

            check = validate_estimate(value, vehicle_data, asking_price=price)
            if check["severity"] == "critical" and check["corrected_value"]:
                warnings.extend(check["issues"])
                value = float(check["corrected_value"])
                high = max(high, value)
                low = min(low, value)
                base_conf *= 0.7
            elif check["issues"]:
                warnings.extend(check["issues"])
        except Exception as exc:  # pragma: no cover
            logger.debug("Sanity check indisponível: %s", exc)

        # O intervalo nunca pode ser negativo nem abaixo do piso absoluto.
        low = max(low, 300.0)
        high = max(high, low * 1.05, value)
        low = min(low, value)

        conf_label = (
            "high" if base_conf >= 0.65
            else "medium" if base_conf >= 0.45
            else "low" if base_conf >= 0.2
            else "insufficient_data"
        )

        explanation = self._build_explanation(primary, candidates, missing, warnings, conf_label)

        result = {
            "estimated_value": round(float(value), 2),
            "uncorrected_value": round(float(uncorrected_value), 2),
            "value_low": round(float(low), 2),
            "value_high": round(float(high), 2),
            "confidence": round(float(base_conf), 3),
            "confidence_label": conf_label,
            "method": primary["method"],
            "comparables_count": primary.get("comparables", 0),
            "reference_level": primary.get("reference_level", 0),
            "methods_used": [c["method"] for _, c in candidates],
            "warnings": warnings,
            "features_missing": missing,
            "valuation_version": VALUATION_VERSION,
            "valuation_explanation": explanation,
        }

        return self._calibrate_interval(result)

    @staticmethod
    def _calibrate_interval(result: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica a calibração conformal dos intervalos, se existir.

        Os limites ``value_low``/``value_high`` acima são heurísticos e nunca
        foram verificados contra a cobertura que prometem. Esta camada mede-os
        e corrige-os (ver valuation/interval_calibration.py).

        Se não houver ficheiro de calibração, o resultado passa intacto mas
        marcado com ``interval_calibrated=False``, para que o consumidor saiba
        que o intervalo não tem garantia de cobertura.
        """
        try:
            from valuation.interval_calibration import IntervalCalibrator

            calibrator = IntervalCalibrator.load()
            if calibrator is None:
                result["interval_calibrated"] = False
                return result
            calibrated = calibrator.apply(result)
            calibrated["interval_calibrated"] = True
            return calibrated
        except Exception as exc:  # pragma: no cover - nunca partir a avaliação
            logger.debug("Calibração de intervalo indisponível: %s", exc)
            result["interval_calibrated"] = False
            return result

    def _insufficient_result(self, vehicle_data, missing, warnings) -> Dict[str, Any]:
        return {
            "estimated_value": None,
            "value_low": None,
            "value_high": None,
            "confidence": 0.0,
            "confidence_label": "insufficient_data",
            "method": "no_reliable_reference",
            "comparables_count": 0,
            "reference_level": None,
            "methods_used": [],
            "warnings": warnings + ["Sem referência fiável: avaliação inconclusiva."],
            "features_missing": missing,
            "valuation_version": VALUATION_VERSION,
            "valuation_explanation": (
                "Não foi encontrada nenhuma referência fiável (comparáveis, "
                "modelo ML ou referência externa). Avaliação inconclusiva — "
                "o anúncio não é classificado como oportunidade nem como caro."
            ),
        }

    @staticmethod
    def _build_explanation(primary, candidates, missing, warnings, conf_label) -> str:
        parts = [f"Método principal: {primary['method']}"]
        if primary.get("comparables"):
            parts.append(f"{primary['comparables']} comparáveis (nível {primary['reference_level']})")
        if len(candidates) > 1:
            parts.append("combinado com " + ", ".join(c['method'] for _, c in candidates[1:]))
        if primary.get("note"):
            parts.append(primary["note"])
        if missing:
            parts.append("dados em falta: " + ", ".join(missing))
        parts.append(f"confiança {conf_label}")
        return ". ".join(parts) + "."

    def estimate_value(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """Backward-compat: devolve apenas o valor estimado (ou None)."""
        return self.estimate(vehicle_data)["estimated_value"]

    # ---------------------------------------------------------- deal score --

    def calculate_deal_score(self, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deal score 0-10 consciente da confiança + estado interpretável."""
        price = parse_optional_float(vehicle_data.get("price")) or 0.0
        est = self.estimate(vehicle_data)
        estimated_value = est["estimated_value"]

        # Sem estimativa fiável ou preço inválido → avaliação inconclusiva.
        if estimated_value is None or price <= 0:
            return {
                "deal_score": 5.0,
                "deal_status": "dados_insuficientes",
                "estimated_value": estimated_value,
                "price": price,
                "profit_potential": 0.0,
                "net_profit_potential": 0.0,
                "profit_percentage": 0.0,
                "confidence": est["confidence"],
                "confidence_label": est["confidence_label"],
                "valuation": est,
                "valuation_method": est["method"],
            }

        value_low = est["value_low"] or estimated_value * 0.85
        value_high = est["value_high"] or estimated_value * 1.15
        conf = est["confidence"]

        # Posição do preço face ao intervalo estimado:
        # dentro do intervalo → ~5; abaixo do mínimo → sobe; acima → desce.
        if price >= value_high:
            excess = (price - value_high) / value_high
            raw_score = 5.0 - min(5.0, excess * 12.0)
        elif price <= value_low:
            discount = (value_low - price) / value_low
            raw_score = 5.0 + min(5.0, discount * 12.0)
        else:
            # Dentro do intervalo: posição linear entre 4.5 e 5.5
            pos = (price - value_low) / max(1.0, value_high - value_low)
            raw_score = 5.5 - pos

        # Scores extremos exigem confiança: quanto menor a confiança,
        # mais o score é puxado para a faixa neutra.
        if conf >= 0.65:
            lo, hi = 0.0, 10.0
        elif conf >= 0.45:
            lo, hi = 2.5, 7.5
        elif conf >= 0.2:
            lo, hi = 3.5, 6.5
        else:
            lo, hi = 4.0, 6.0
        deal_score = round(max(lo, min(hi, raw_score)), 1)

        # Estado interpretável
        if deal_score >= 7.5:
            status = "excelente_oportunidade"
        elif deal_score >= 6.0:
            status = "bom_preco"
        elif deal_score > 4.0:
            status = "preco_justo"
        elif deal_score > 2.5:
            status = "ligeiramente_caro"
        else:
            status = "caro"

        # Deteção de preço provavelmente não-total (mensalidade/entrada).
        # Usa o valor ANTES do cap de sanidade "2.5x o ask" — caso contrário
        # uma mensalidade de €400 seria classificada como grande oportunidade.
        unc = est.get("uncorrected_value") or estimated_value
        ratio = price / estimated_value if estimated_value else None
        ratio_unc = price / unc if unc else ratio
        risk_flags: List[str] = []
        if ratio_unc is not None and ratio_unc < 0.15 and unc > 4000:
            status = "provavel_erro_anuncio"
            risk_flags.append(
                "Preço <15% do valor estimado: provável mensalidade, entrada "
                "ou erro de extração — não é um preço total."
            )
            deal_score = 5.0
        elif ratio_unc is not None and ratio_unc < 0.35:
            status = "anuncio_suspeito"
            risk_flags.append(
                "Preço muito abaixo do mercado: verificar fraude, salvado, "
                "peças ou preço de financiamento."
            )
            deal_score = min(deal_score, 6.5)

        # Plausibility externa (referência independente)
        plausibility = None
        try:
            from valuation.market_reference import price_plausibility

            plausibility = price_plausibility(price, vehicle_data)
            if plausibility.get("verdict") == "suspeito" and status not in ("provavel_erro_anuncio",):
                status = "anuncio_suspeito"
                risk_flags.extend(plausibility.get("flags", []))
        except Exception:  # pragma: no cover
            pass

        # ---------------- custos e lucro (lógica PT existente) ----------------
        gross_profit = max(0.0, estimated_value - price)
        profit_percentage = (gross_profit / price * 100.0) if price > 0 else 0.0

        from valuation.deal_scorer_unified import calculate_profit_potential

        is_national = vehicle_data.get("is_national", None)
        engine_cc = parse_optional_int(vehicle_data.get("engine_size")) or 1500
        co2 = parse_optional_float(vehicle_data.get("co2_gkm"))
        year = parse_optional_int(vehicle_data.get("year"))
        age_years = max(0, pd.Timestamp.now().year - year) if year else 8
        condition_score = parse_optional_float(vehicle_data.get("condition_score")) or 6.0
        vtype = str(vehicle_data.get("vehicle_type") or "carros")

        try:
            from valuation.price_drivers import liquidity_driver

            days_to_sell = int(liquidity_driver(vehicle_data.get("brand")).get("days_to_sell", 55))
        except Exception:  # pragma: no cover
            days_to_sell = 55

        profit = calculate_profit_potential(
            estimated_value=estimated_value,
            asking_price=price,
            engine_cc=engine_cc,
            co2_gkm=co2,
            fuel_type=str(vehicle_data.get("fuel_type") or "gasolina"),
            age_years=age_years,
            is_national=bool(is_national) if is_national is not None else True,
            vehicle_type=vtype,
            condition_score=condition_score,
            days_to_sell=days_to_sell,
        )

        taxes = profit["taxes"]["total"]
        repair_costs = profit["repair_costs"]
        net_profit = max(0.0, profit["net_profit_after_sale"])
        net_profit_pct = (net_profit / price * 100.0) if price > 0 else 0.0

        discount = (estimated_value - price) / estimated_value

        result = {
            "deal_score": deal_score,
            "deal_status": status,
            "estimated_value": round(estimated_value, 2),
            "value_low": round(value_low, 2),
            "value_high": round(value_high, 2),
            "asking_benchmark": round(estimated_value * 1.12, 2),
            "price": price,
            "price_discount": round(discount, 3),
            "profit_potential": round(gross_profit, 2),
            "profit_percentage": round(profit_percentage, 2),
            "net_profit_potential": round(net_profit, 2),
            "net_profit_percentage": round(net_profit_pct, 2),
            "roi_percentage": profit["roi_percentage"],
            "roi_annualized_percentage": profit["roi_annualized_percentage"],
            "transfer_taxes": round(taxes, 2),
            "acquisition_costs": profit["acquisition_costs"],
            "selling_costs": profit["selling_costs"]["total"],
            "estimated_repair_costs": round(repair_costs, 2),
            "iuc_annual": profit["iuc_annual"],
            "days_to_sell": days_to_sell,
            "cost_notes": profit["notes"],
            "confidence": conf,
            "confidence_label": est["confidence_label"],
            "risk_flags": risk_flags,
            "valuation": est,
            "valuation_method": est["method"],
        }
        if plausibility:
            result["price_verdict"] = plausibility.get("verdict")
            result["price_vs_reference"] = plausibility.get("ratio")

        # ── auditoria de realismo (2026-08) ────────────────────────────────
        # `net_profit_potential` acima trata `estimated_value` como receita.
        # Mas `estimated_value` é uma mediana de preços PEDIDOS, e falta-lhe
        # o IVA do regime da margem. A auditoria converte o pedido em receita
        # realista e desconta o IVA, produzindo o número que o revendedor
        # efetivamente embolsa. Os campos antigos ficam intactos para não
        # partir consumidores existentes; os novos são os fiáveis.
        try:
            from valuation.realism import audit_from_valuation

            audit = audit_from_valuation(
                {**vehicle_data, "days_to_sell": days_to_sell}, est
            )
            result["realistic"] = audit.to_dict()
            result["realistic_net_profit"] = audit.net_profit
            result["realistic_net_profit_worst_case"] = audit.net_profit_worst_case
            result["realistic_sale_price"] = audit.realistic_sale_price
            result["realistic_roi_percentage"] = audit.roi_pct
            result["realistic_verdict"] = audit.verdict
            result["max_purchase_price"] = audit.break_even_price
            result["vat_on_margin"] = audit.iva_margem
            # Riscos detetados pela auditoria acrescentam-se aos existentes,
            # sem duplicar.
            for flag in audit.risk_flags:
                if flag not in risk_flags:
                    risk_flags.append(flag)
        except Exception as exc:  # pragma: no cover — auditoria é aditiva
            logger.debug("Auditoria de realismo indisponível: %s", exc)
            result["realistic_verdict"] = "indisponivel"

        return result

    # ------------------------------------------------------------- legacy --

    _REPAIR_COST_BY_CONDITION = [
        (8.0, 0),
        (6.0, 500),
        (4.0, 1500),
        (2.0, 3000),
        (0.0, 5000),
    ]

    def _estimate_repair_costs(self, condition_score: float) -> float:
        for threshold, cost in self._REPAIR_COST_BY_CONDITION:
            if condition_score >= threshold:
                return float(cost)
        return 5000.0

    # Compatibilidade com código antigo que chamava estes métodos diretamente.
    def _get_segment_price(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        est = self._statistical_estimate(vehicle_data)
        return est["value"] if est else None

    def _median_excl_self(self, price_list, self_id=None, self_price=None):
        if not price_list:
            return None
        arr = np.array(price_list, dtype=float)
        if self_price is not None and len(arr) > 1:
            arr = arr[arr != self_price]
        if len(arr) == 0:
            return None
        return float(np.median(arr))


# Global instance
_hybrid_valuator = None
_valuator_loaded_at: float = 0.0
_VALUATOR_TTL_SECONDS = 1800  # reconstrói índices de comparáveis a cada 30 min


def get_valuator() -> HybridValuator:
    """Get or create the global hybrid valuator instance.

    Reconstrói automaticamente após _VALUATOR_TTL_SECONDS: os índices de
    comparáveis são construídos em memória a partir da BD e, sem TTL, um
    processo longo (scheduler) avaliava anúncios novos com comparáveis velhos.
    """
    import time

    global _hybrid_valuator, _valuator_loaded_at
    now = time.time()
    if _hybrid_valuator is None or (now - _valuator_loaded_at) > _VALUATOR_TTL_SECONDS:
        _hybrid_valuator = HybridValuator()
        _valuator_loaded_at = now
    return _hybrid_valuator


def reset_valuator() -> None:
    """Reinicia a instância global (útil após reprocessamento/treino)."""
    global _hybrid_valuator, _valuator_loaded_at
    _hybrid_valuator = None
    _valuator_loaded_at = 0.0


def estimate_market_value(vehicle_data: Dict[str, Any]) -> Optional[float]:
    """Convenience function for estimating market value."""
    return get_valuator().estimate_value(vehicle_data)


def calculate_deal_score(vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for calculating deal score."""
    return get_valuator().calculate_deal_score(vehicle_data)
