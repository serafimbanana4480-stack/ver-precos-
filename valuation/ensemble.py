"""Ensemble de avaliação: combina comparáveis + ML + referência PVP.

Filosofia
---------
A informação nunca é transformada em valor quando não existe. O ensemble só
combina opiniões quando há dados reais para cada uma:

* **comparáveis** -- mediana ponderada (autoridade primária quando há ≥3 comps);
* **ML** -- previsão do extra-trees, usada para triangulação (protegida contra
  outliers) e só pedida quando a estimativa de comparáveis é incerta ou a
  referência é fraca;
* **referência PVP** -- âncora absoluta, usada para triangulação e, quando há
  âncora real numa versão *base*/*sport_trim*, como fallback de BAIXA
  confiança para veículos sem nenhum comparável directo.

Fallbacks proibidos (mantêm ``dados_insuficientes``):
  * variantes de performance real (A 35 AMG, M3, Panamera, …) -- a referência
    de base daria um valor falso;
  * modelos sem nenhuma âncora PVP (Lexus IS, Jaguar E-Pace, …).

Estas duas regras mantêm os veículos-problema do enunciado sem estimativa,
mesmo com o fallback activado.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from valuation.canonical_vehicle import CanonicalVehicle, PerformanceClass
from valuation.comparables import MarketEstimate, _insufficient
from valuation.market_math import finite
from valuation.market_reference import estimate_reference_value, validate_estimate
from valuation.predict import normalize_vehicle_type

logger = logging.getLogger(__name__)

#: Versões elegíveis a um fallback de referência. Exclui a performance real
#: (AMG/M/RS/Turbo/…), contra a qual a referência de base é falsa.
_FALLBACK_ALLOWED_PERF = frozenset(
    {PerformanceClass.BASE, PerformanceClass.SPORT_TRIM}
)

#: Confiança mínima da referência PVP para justificar um fallback.
_REF_FALLBACK_MIN_CONF: float = 0.55
#: Teto de confiança para qualquer estimativa sem comparáveis directos.
#: Um fallback nunca atinge "confiança média": é sempre "baixa".
_REF_FALLBACK_MAX_CONF: float = 0.44

#: Banda de coerência para incluir um componente no blend.
_INLIER_LO: float = 0.40
_INLIER_HI: float = 2.50

_PREDICTOR: Optional[Any] = None  # backward-compatible cars cache handle
_PREDICTOR_TRIED: bool = False  # backward-compatible test/reset handle
_PREDICTORS: Dict[str, Optional[Any]] = {}
_PREDICTOR_TRIED_BY_TYPE: Dict[str, bool] = {}


def _get_predictor(vehicle_type: str = "carros"):
    """Carrega preguiçosamente o artefacto do tipo solicitado.

    O cache é indexado por ``vehicle_type``.  O predictor de carros nunca é
    usado como fallback para motos (ou vice-versa); a ausência do artefacto do
    tipo pedido mantém a opinião ML ausente.
    """
    global _PREDICTOR, _PREDICTOR_TRIED
    vtype = normalize_vehicle_type(vehicle_type)
    if vtype == "carros" and not _PREDICTOR_TRIED:
        # Preserve the old module-level reset convention used by callers and
        # tests while making the actual cache type-aware.
        _PREDICTOR_TRIED = True
    if _PREDICTOR_TRIED_BY_TYPE.get(vtype):
        return _PREDICTORS.get(vtype)
    _PREDICTOR_TRIED_BY_TYPE[vtype] = True
    try:
        from valuation.predict import PricePredictor

        p = PricePredictor(vtype)
        value = p if p.model_loaded_ok else None
        _PREDICTORS[vtype] = value
        if vtype == "carros":
            _PREDICTOR = value
    except Exception as exc:  # pragma: no cover - defensivo
        logger.debug("ML indisponível para o ensemble (%s): %s", vtype, exc)
        _PREDICTORS[vtype] = None
        if vtype == "carros":
            _PREDICTOR = None
    return _PREDICTORS.get(vtype)


def reference_for(vehicle: Dict[str, Any], canon: CanonicalVehicle) -> Dict[str, Any]:
    """Consulta a referência PVP de um anúncio a partir dos seus dados canónicos."""
    vehicle_type = normalize_vehicle_type(vehicle.get("vehicle_type"))
    brand = vehicle.get("brand") or vehicle.get("normalized_brand")
    model = vehicle.get("model") or getattr(canon, "model_family", None) or ""
    year = finite(vehicle.get("year")) or finite(getattr(canon, "year", None))
    km = finite(vehicle.get("km"))
    fuel = getattr(canon, "fuel", "unknown")
    fuel = fuel if fuel != "unknown" else None
    engine_cc = vehicle.get("engine_size")
    return estimate_reference_value(
        brand or None, model or None, year, km, fuel, vehicle_type, engine_cc
    )


def _inlier(value: Any, ref_value: Any) -> bool:
    """True se ``value`` está numa banda plausível em torno de ``ref_value``."""
    ref = finite(ref_value)
    val = finite(value)
    if ref is None or ref <= 0 or val is None or val <= 0:
        return False
    ratio = val / ref
    return _INLIER_LO <= ratio <= _INLIER_HI


def _ml_predict(vehicle, predictor, vehicle_type: Optional[str] = None):
    """Valor ML (se disponível e finito), para triangulação."""
    if predictor is None:
        return None
    requested = normalize_vehicle_type(
        vehicle_type if vehicle_type is not None else vehicle.get("vehicle_type")
    )
    configured = getattr(predictor, "vehicle_type", None)
    if configured is not None:
        try:
            if normalize_vehicle_type(configured) != requested:
                logger.warning(
                    "Opinião ML cross-type recusada: predictor=%s vehicle=%s",
                    configured,
                    requested,
                )
                return None
        except ValueError:
            return None
    try:
        return finite(predictor.predict(vehicle))
    except Exception as exc:
        logger.debug("predição ML falhou para o ensemble: %s", exc)
        return None


def _label(confidence: float) -> str:
    if confidence >= 0.65:
        return "alta"
    if confidence >= 0.45:
        return "media"
    if confidence >= 0.25:
        return "baixa"
    return "muito_baixa"


# ---------------------------------------------------------------------------
# Triangulação: comparáveis × ML × referência
# ---------------------------------------------------------------------------


def _blend_with_comparables(
    vehicle: Dict[str, Any],
    comparable: MarketEstimate,
    predictor,
    ref: Optional[Dict[str, Any]],
    canon,
    vehicle_type: str = "carros",
) -> MarketEstimate:
    """Triangula a mediana de comparáveis com ML (+eventualmente referência)."""
    center = comparable.value or 0.0
    conf_base = max(0.40, min(0.95, comparable.confidence))
    components: List[tuple] = [(center, conf_base, "comparaveis")]

    # ML: pedida apenas quando a estimativa de comparáveis é incerta.
    if comparable.confidence < 0.60:
        ml_val = _ml_predict(vehicle, predictor, vehicle_type)
        if ml_val is not None and ml_val > 0 and _inlier(ml_val, center):
            components.append((ml_val, 0.30, "ml"))

    ref = ref or {}
    ref_val = finite(ref.get("value"))
    ref_conf = finite(ref.get("confidence"))
    ref_added = False
    if (
        ref_val is not None
        and ref_val > 0
        and ref_conf is not None
        and ref_conf >= 0.50
        and _inlier(ref_val, center)
    ):
        components.append((ref_val, 0.20, "referencia"))
        ref_added = True

    num = sum(v * w for v, w, _ in components)
    den = sum(w for _, w, _ in components) or 1.0
    blended = num / den

    low = finite(comparable.low) or blended
    high = finite(comparable.high) or blended
    for val, _, src in components[1:]:
        if src == "ml":
            low = min(low, val * 0.90)
            high = max(high, val * 1.10)
        elif src == "referencia":
            rlow = finite(ref.get("low"))
            rhigh = finite(ref.get("high"))
            if rlow:
                low = min(low, rlow)
            if rhigh:
                high = max(high, rhigh)

    # Confiança: sobe só se ML e referência concordam com a base; nunca desce.
    conf = conf_base
    if center > 0:
        if any(c[2] == "ml" and abs(c[0] - center) / center <= 0.15 for c in components):
            conf += 0.05
        if any(
            c[2] == "referencia" and abs(c[0] - center) / center <= 0.20
            for c in components
        ):
            conf += 0.05
    conf = min(0.95, max(conf, comparable.confidence))

    notes = list(comparable.notes) + [
        "ensemble: {} opinião(ões) de ML/referência incorporada(s)".format(
            len(components) - 1
        )
    ]
    ml_for_details = next((v for v, _, s in components if s == "ml"), None)
    ref_summary: Optional[Dict[str, Any]] = None
    if ref_added:
        ref_summary = {
            "value": ref_val,
            "low": finite(ref.get("low")),
            "high": finite(ref.get("high")),
            "confidence": ref_conf,
            "matched_model": ref.get("matched_model"),
        }

    return MarketEstimate(
        value=round(blended, 2),
        low=round(low, 2),
        high=round(high, 2),
        status="ok",
        method="ensemble_comparaveis_ml_referencia",
        level=comparable.level,
        comparables_used=comparable.comparables_used,
        comparables_rejected=comparable.comparables_rejected,
        mean_similarity=comparable.mean_similarity,
        dispersion_pct=comparable.dispersion_pct,
        confidence=round(conf, 3),
        confidence_label=_label(conf),
        explanation=(
            comparable.explanation
            + " Valor triangulado com {} opinião(ões) adicional(es).".format(
                len(components) - 1
            )
        ),
        used=comparable.used,
        rejected=comparable.rejected,
        rejection_summary=comparable.rejection_summary,
        notes=notes,
        ml_estimate=ml_for_details,
        reference_estimate=ref_summary,
    )


def _reference_fallback(
    vehicle: Dict[str, Any],
    comparable: MarketEstimate,
    ref: Optional[Dict[str, Any]],
    predictor,
    canon,
    vehicle_type: str = "carros",
) -> MarketEstimate:
    """Fallback de baixa confiança via âncora PVP — só para base/sport_trim."""
    ref = ref or {}
    ref_val = finite(ref.get("value"))
    ref_conf = finite(ref.get("confidence"))
    perf_ok = canon is not None and canon.performance_class in _FALLBACK_ALLOWED_PERF

    if not perf_ok:
        notes = list(comparable.notes) + [
            "Fallback de referência recusado: versão de performance "
            "(evita estimativa falsa de base-vs-AMG)."
        ]
        return _insufficient(comparable.explanation, comparable.rejected,
                             comparable.rejection_summary, notes)

    if ref_val is None or ref_conf is None or ref_conf < _REF_FALLBACK_MIN_CONF:
        notes = list(comparable.notes)
        if ref_val is None:
            notes.append("Sem âncora PVP: nenhuma referência de mercado disponível.")
        else:
            notes.append(
                "Âncora PVP fraca (conf {0:.2f} < {1}): não atinge o limiar".format(
                    ref_conf, _REF_FALLBACK_MIN_CONF
                )
            )
        return _insufficient(comparable.explanation, comparable.rejected,
                             comparable.rejection_summary, notes)

    # Sanity: a referência não pode violar limites absolutos / rácio.
    price = finite(vehicle.get("price"))
    chk = validate_estimate(ref_val, vehicle, asking_price=price)
    if not chk.get("is_valid"):
        notes = list(comparable.notes) + [
            "Referência PVP rejeitada pelo validador de sanidade: "
            + "; ".join(chk.get("issues", []))
        ]
        return _insufficient(comparable.explanation, comparable.rejected,
                             comparable.rejection_summary, notes)

    # Banda mínima ±30 % para marcar claramente a baixa confiança.
    low = finite(ref.get("low"))
    high = finite(ref.get("high"))
    if not low or not high or ref_val <= 0:
        spread = 0.40
    else:
        spread = max(0.30, (high - low) / 2.0 / ref_val)
    low = ref_val * (1 - spread)
    high = ref_val * (1 + spread)

    conf = min(_REF_FALLBACK_MAX_CONF, round(ref_conf * 0.65, 3))
    label = _label(conf)

    base_note = (
        "Âncora PVP validada: âncora '{0}' (conf {1:.2f}). "
        "Estimativa de baixa confiabilidade (sem comparáveis directos)."
    ).format(ref.get("matched_model"), ref_conf)
    notes = [base_note]
    ml_val: Optional[float] = None
    # Triangulação ML apenas para âncoras de confiança intermédia.
    if ref_conf is not None and 0.50 <= ref_conf < 0.65:
        ml_val = _ml_predict(vehicle, predictor, vehicle_type)
        if (
            ml_val is not None
            and ml_val > 0
            and _inlier(ml_val, ref_val)
            and 0.75 <= ml_val / ref_val <= 1.25
        ):
            notes.append("ML confirma a referência ({0:.0f} €).".format(ml_val))
            conf = min(_REF_FALLBACK_MAX_CONF, conf + 0.08)
            label = _label(conf)

    age = int(round(ref.get("age", 0) or 0))
    explanation = (
        "Estimativa de referência PVP (baixa confiabilidade): âncora "
        "'{0}' a {1} anos. Sem comparáveis directos na base.".format(
            ref.get("matched_model"), age
        )
    )

    return MarketEstimate(
        value=round(ref_val, 2),
        low=round(low, 2),
        high=round(high, 2),
        status="low_confidence",
        method="referencia_pvp_baixa_confianca",
        level=None,
        comparables_used=0,
        comparables_rejected=0,
        mean_similarity=None,
        dispersion_pct=None,
        confidence=round(conf, 3),
        confidence_label=label,
        explanation=explanation,
        used=[],
        rejected=list(comparable.rejected),
        rejection_summary=comparable.rejection_summary,
        notes=notes,
        ml_estimate=ml_val,
        reference_estimate={
            "value": ref_val,
            "low": finite(ref.get("low")),
            "high": finite(ref.get("high")),
            "confidence": ref_conf,
            "matched_model": ref.get("matched_model"),
        },
    )


def blend_estimate(
    vehicle: Dict[str, Any],
    comparable: MarketEstimate,
    *,
    predictor=None,
    ref: Optional[Dict[str, Any]] = None,
    canon: Optional[CanonicalVehicle] = None,
) -> MarketEstimate:
    """Combina o resultado de comparáveis com ML e referência PVP.

    - ``ok`` de comparáveis: triangulados com ML (+referência).
    - Insuficientes: fallback de referência quando houver âncora fiável e a
      versão não for de performance; caso contrário mantém
      ``dados_insuficientes`` (nunca inventa).
    """
    vehicle_type = normalize_vehicle_type(vehicle.get("vehicle_type"))
    if predictor is None:
        predictor = _get_predictor(vehicle_type)
    elif getattr(predictor, "vehicle_type", None) is not None:
        try:
            if normalize_vehicle_type(predictor.vehicle_type) != vehicle_type:
                # An explicitly supplied predictor is never silently reused
                # across types.  The type-specific lazy cache remains the only
                # automatic route.
                predictor = None
        except ValueError:
            predictor = None
    if comparable.status == "ok" and comparable.value is not None:
        return _blend_with_comparables(
            vehicle, comparable, predictor, ref, canon, vehicle_type
        )
    return _reference_fallback(
        vehicle, comparable, ref, predictor, canon, vehicle_type
    )
