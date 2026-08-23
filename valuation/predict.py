"""
Runtime contract for vehicle-price models.

The training and inference paths share the ``FeatureStore`` definition, the
feature order and the artifact metadata contract.  Missing optional values may
still be represented by the FeatureStore's historical encodings, but a field
or feature explicitly required by a manifest never becomes a silent zero.
"""
from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from joblib import load

from core.settings import settings
from valuation.feature_store import FeatureStore

logger = logging.getLogger(__name__)

SUPPORTED_VEHICLE_TYPES = ("carros", "motos")
_VEHICLE_TYPE_ALIASES = {
    "car": "carros",
    "cars": "carros",
    "carro": "carros",
    "carros": "carros",
    "moto": "motos",
    "motos": "motos",
    "motorcycle": "motos",
    "motorcycles": "motos",
}


def normalize_vehicle_type(value: Any, default: Optional[str] = "carros") -> str:
    """Return the one canonical vehicle type used by model artifacts."""
    raw = getattr(value, "value", value)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if default is None:
            raise ValueError("vehicle_type is required")
        raw = default
    key = str(raw).strip().lower()
    try:
        return _VEHICLE_TYPE_ALIASES[key]
    except KeyError as exc:
        raise ValueError(
            f"unsupported vehicle_type {raw!r}; expected one of {SUPPORTED_VEHICLE_TYPES}"
        ) from exc


def required_input_fields(vehicle_type: str) -> Tuple[str, ...]:
    """Fields that must be evidenced before a model can be invoked."""
    vtype = normalize_vehicle_type(vehicle_type)
    fields = ["year", "brand", "model"]
    if vtype == "carros":
        fields.append("km")
    return tuple(fields)


def canonical_feature_names(
    declared: Optional[Sequence[str]] = None,
    *,
    allow_empty: bool = False,
) -> List[str]:
    """Validate and normalize a manifest's feature order."""
    if declared is None:
        return list(FeatureStore.ALLOWED_FEATURES)
    if isinstance(declared, (str, bytes)) or not isinstance(declared, Sequence):
        raise ValueError("feature_names must be a sequence of strings")
    names = list(declared)
    if not names and not allow_empty:
        raise ValueError("feature_names cannot be empty when declared")
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("feature_names contains an invalid name")
    if len(set(names)) != len(names):
        raise ValueError("feature_names contains duplicates")
    unknown = [name for name in names if name not in FeatureStore.ALLOWED_FEATURES]
    if unknown:
        raise ValueError(f"feature_names contains unsupported features: {unknown}")
    return names


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return not bool(np.isfinite(float(value)))
    except (TypeError, ValueError, OverflowError):
        return False


def missing_required_fields(
    vehicle: Mapping[str, Any],
    required_fields: Iterable[str],
) -> List[str]:
    """Return required raw fields with no usable evidence."""
    return [field for field in required_fields if _is_missing(vehicle.get(field))]


def normalize_required_fields(
    declared: Optional[Sequence[str]],
    vehicle_type: str,
) -> List[str]:
    """Validate manifest raw-field requirements, with a safe legacy default."""
    if declared is None:
        return list(required_input_fields(vehicle_type))
    if isinstance(declared, (str, bytes)) or not isinstance(declared, Sequence):
        raise ValueError("required_fields must be a sequence of strings")
    fields = list(declared)
    if any(not isinstance(field, str) or not field.strip() for field in fields):
        raise ValueError("required_fields contains an invalid field")
    if len(set(fields)) != len(fields):
        raise ValueError("required_fields contains duplicates")
    return fields


def build_feature_vector(
    fs: FeatureStore,
    vehicle: Mapping[str, Any],
    feature_names: Sequence[str],
    *,
    required_fields: Optional[Sequence[str]] = None,
    reference_year: Optional[int] = None,
) -> np.ndarray:
    """Compute one strict, ordered feature vector."""
    names = canonical_feature_names(feature_names)
    required = list(required_fields or [])
    missing = missing_required_fields(vehicle, required)
    if missing:
        raise ValueError(
            "required input fields missing or invalid: " + ", ".join(missing)
        )

    features = fs.compute_features(dict(vehicle), reference_year=reference_year)
    missing_features = [name for name in names if name not in features]
    if missing_features:
        raise ValueError(
            "required computed features missing: " + ", ".join(missing_features)
        )
    values = []
    for name in names:
        try:
            value = float(features[name])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"feature {name!r} is not numeric") from exc
        if not math.isfinite(value):
            raise ValueError(f"feature {name!r} is not finite")
        values.append(value)
    return np.asarray([values], dtype=float)


def _safe_artifact_path(model_dir: Path, raw_path: Any, label: str) -> Path:
    """Resolve a manifest path without allowing traversal or reparse escapes."""
    if not isinstance(raw_path, (str, Path)) or not str(raw_path).strip():
        raise ValueError(f"{label} is missing")
    relative = Path(str(raw_path))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must be a relative path inside models_dir")

    root = Path(model_dir).resolve()
    lexical = root / relative
    try:
        candidate = lexical.resolve()
        candidate.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} escapes models_dir") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if not current.exists():
            continue
        try:
            if os.path.islink(current):
                raise ValueError(f"{label} uses a symlink/reparse point")
            attributes = int(getattr(os.lstat(current), "st_file_attributes", 0))
            if attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                raise ValueError(f"{label} uses a Windows reparse point")
        except OSError as exc:
            raise ValueError(f"cannot inspect {label}") from exc
    return candidate


def _path_type_mismatch(path: Path, vehicle_type: str) -> bool:
    """Reject obvious cross-type artifact names (generic names remain valid)."""
    name = path.name.lower()
    other = "motos" if vehicle_type == "carros" else "carros"
    return other in name and vehicle_type not in name


def _feature_count(model: Any, model_name: str) -> Optional[int]:
    try:
        if model_name == "xgboost":
            return int(model.get_booster().num_features())
        if model_name == "lightgbm":
            try:
                return int(model.num_feature())
            except Exception:
                return int(model.dump_model().get("max_feature_idx", -1)) + 1
        if model_name == "catboost" and hasattr(model, "get_feature_count"):
            return int(model.get_feature_count())
        value = getattr(model, "n_features_in_", None)
        return int(value) if value is not None else None
    except Exception:
        return None


class PricePredictor:
    """Production inference pipeline for exactly one vehicle type."""

    def __init__(self, vehicle_type: str = "carros"):
        self.vehicle_type = normalize_vehicle_type(vehicle_type)
        self.model = None
        self.model_name: Optional[str] = None
        self.scaler = None
        self.scaler_declared = False
        self.feature_names: List[str] = []
        self.required_features: List[str] = []
        self.required_fields: List[str] = []
        self.metrics: Dict[str, Any] = {}
        self.low_metrics: Dict[str, Any] = {}
        self.high_metrics: Dict[str, Any] = {}
        self.fs = FeatureStore()
        self.low_model = None
        self.low_scaler = None
        self.low_scaler_declared = False
        self.low_threshold: Optional[float] = None
        self.low_log_target: bool = False
        self.high_model = None
        self.high_scaler = None
        self.high_scaler_declared = False
        self.high_threshold: Optional[float] = None
        self.high_log_target: bool = False
        self.high_cat_features: List[int] = []
        self.full_log_target: bool = False
        self.feature_reference_year: Optional[int] = None
        self.metadata: Dict[str, Any] = {}
        self.model_loaded_ok: bool = False
        self.load_error: Optional[str] = None
        self._load_model()

    def _fail(self, msg: str) -> None:
        """Register a fail-closed load error and disable every route."""
        self.load_error = msg
        self.model = None
        self.scaler = None
        self.low_model = None
        self.low_scaler = None
        self.high_model = None
        self.high_scaler = None
        self.model_loaded_ok = False
        logger.error("Modelo %s indisponível: %s", self.vehicle_type, msg)

    @staticmethod
    def _route_value(meta: Mapping[str, Any], route: str, key: str) -> Any:
        section = meta.get("routing")
        if isinstance(section, Mapping):
            route_data = section.get(route)
            if isinstance(route_data, Mapping) and key in route_data:
                return route_data[key]
        return meta.get(f"{route}_{key}")

    def _resolve(self, model_dir: Path, raw_path: Any, label: str) -> Path:
        path = _safe_artifact_path(model_dir, raw_path, label)
        if _path_type_mismatch(path, self.vehicle_type):
            raise ValueError(
                f"{label} parece pertencer a outro vehicle_type: {path.name}"
            )
        return path

    def _validate_feature_count(self, model: Any, model_name: str, label: str) -> None:
        count = _feature_count(model, model_name)
        if count is not None and count != len(self.feature_names):
            raise ValueError(
                f"{label} espera {count} features mas o manifesto declara "
                f"{len(self.feature_names)} — pipeline treino/inferência desalinhado"
            )

    def _load_scaler(
        self,
        model_dir: Path,
        raw_path: Any,
        *,
        label: str,
        required: bool,
    ) -> Any:
        if raw_path is None or (isinstance(raw_path, str) and not raw_path.strip()):
            if required:
                raise ValueError(f"{label} declarado mas sem caminho")
            return None
        path = self._resolve(model_dir, raw_path, label)
        if not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"{label} em falta ou vazio: {path}")
        try:
            scaler = load(str(path))
        except Exception as exc:
            raise ValueError(
                f"falha a carregar {label} ({type(exc).__name__}: {exc})"
            ) from exc
        n_in = getattr(scaler, "n_features_in_", None)
        if n_in is not None and int(n_in) != len(self.feature_names):
            raise ValueError(
                f"{label} espera {n_in} features mas o manifesto declara "
                f"{len(self.feature_names)}"
            )
        return scaler

    def _load_model(self) -> None:
        model_dir = Path(settings.models_dir)
        metadata_path = model_dir / f"best_model_{self.vehicle_type}.json"
        if not metadata_path.is_file():
            self._fail(f"metadados em falta: {metadata_path}")
            return
        try:
            with open(metadata_path, encoding="utf-8") as handle:
                meta = json.load(handle)
            if not isinstance(meta, dict):
                raise ValueError("metadata must be a JSON object")
        except Exception as exc:
            self._fail(f"metadados ilegíveis ({type(exc).__name__}: {exc})")
            return

        try:
            declared_type = meta.get("vehicle_type")
            if declared_type is not None and normalize_vehicle_type(declared_type) != self.vehicle_type:
                raise ValueError(
                    f"metadata vehicle_type={declared_type!r} não corresponde a "
                    f"{self.vehicle_type!r}"
                )
            self.metadata = meta
            self.model_name = str(meta.get("model_type") or "").strip().lower()
            if not self.model_name:
                raise ValueError("model_type ausente")
            self.metrics = meta.get("metrics") if isinstance(meta.get("metrics"), dict) else {}
            self.low_metrics = meta.get("low_metrics") if isinstance(meta.get("low_metrics"), dict) else {}
            self.high_metrics = meta.get("high_metrics_true_ge_20k") if isinstance(meta.get("high_metrics_true_ge_20k"), dict) else {}

            self.feature_names = canonical_feature_names(
                meta.get("feature_names") if "feature_names" in meta else None
            )
            declared_required_features = meta.get("required_features")
            if declared_required_features is None and isinstance(meta.get("feature_contract"), Mapping):
                declared_required_features = meta["feature_contract"].get("required_features")
            self.required_features = canonical_feature_names(
                declared_required_features if declared_required_features is not None else self.feature_names
            )
            if not set(self.required_features).issubset(self.feature_names):
                raise ValueError("required_features must be a subset of feature_names")

            declared_required_fields = meta.get("required_fields")
            if declared_required_fields is None and isinstance(meta.get("feature_contract"), Mapping):
                declared_required_fields = meta["feature_contract"].get("required_fields")
            self.required_fields = normalize_required_fields(
                declared_required_fields, self.vehicle_type
            )

            if "feature_reference_year" in meta:
                reference_year = int(meta["feature_reference_year"])
                if not 1900 <= reference_year <= 2200:
                    raise ValueError("feature_reference_year fora do intervalo suportado")
                self.feature_reference_year = reference_year
                self.fs.reference_year = reference_year

            model_path = self._resolve(model_dir, meta.get("model_path"), "model_path")
            if not model_path.is_file() or model_path.stat().st_size <= 0:
                raise ValueError(f"artefacto do modelo em falta ou vazio: {model_path}")

            if self.model_name == "xgboost":
                import xgboost as xgb

                candidate = xgb.XGBRegressor()
                candidate.load_model(str(model_path))
                self._validate_feature_count(candidate, self.model_name, "modelo")
                self.model = candidate
            elif self.model_name == "lightgbm":
                import lightgbm as lgb

                candidate = lgb.Booster(model_file=str(model_path))
                self._validate_feature_count(candidate, self.model_name, "modelo")
                self.model = candidate
            elif self.model_name == "catboost":
                from catboost import CatBoostRegressor

                candidate = CatBoostRegressor()
                candidate.load_model(str(model_path))
                self._validate_feature_count(candidate, self.model_name, "modelo")
                self.model = candidate
            elif self.model_name in ("random_forest", "extra_trees", "huber") or model_path.suffix.lower() == ".joblib":
                candidate = load(str(model_path))
                self._validate_feature_count(candidate, self.model_name, "modelo")
                self.model = candidate
            else:
                raise ValueError(f"tipo de modelo desconhecido: {self.model_name}")

            self.scaler_declared = "scaler_path" in meta
            self.scaler = self._load_scaler(
                model_dir,
                meta.get("scaler_path"),
                label="scaler_path",
                required=self.scaler_declared,
            )

            if "brand_index_path" in meta:
                index_path = self._resolve(model_dir, meta.get("brand_index_path"), "brand_index_path")
                if not index_path.is_file() or index_path.stat().st_size <= 0:
                    raise ValueError(f"brand_index_path em falta ou vazio: {index_path}")
                try:
                    parsed = json.loads(index_path.read_text(encoding="utf-8"))
                    if not isinstance(parsed, dict):
                        raise ValueError("brand/model index must be an object")
                    self.fs.load_index(index_path)
                except Exception as exc:
                    raise ValueError(
                        f"brand_index_path inválido ({type(exc).__name__}: {exc})"
                    ) from exc

            self.low_threshold = self._numeric_route_value(meta, "low", "threshold")
            self.high_threshold = self._numeric_route_value(meta, "high", "threshold")
            self.full_log_target = bool(meta.get("full_log_target", False))
            self.low_log_target = bool(self._route_value(meta, "low", "log_target") or meta.get("low_log_target", False))
            self.high_log_target = bool(self._route_value(meta, "high", "log_target") or meta.get("high_log_target", False))
            cat_features = self._route_value(meta, "high", "cat_features")
            if cat_features is None:
                cat_features = meta.get("high_cat_features", [])
            if not isinstance(cat_features, list) or any(not isinstance(item, int) for item in cat_features):
                raise ValueError("high_cat_features inválido")
            if any(item < 0 or item >= len(self.feature_names) for item in cat_features):
                raise ValueError("high_cat_features fora do vetor de features")
            self.high_cat_features = list(cat_features)

            self._load_low_route(model_dir, meta)
            self._load_high_route(model_dir, meta)
        except Exception as exc:
            self._fail(
                f"contrato/artefacto inválido ({type(exc).__name__}: {exc})"
            )
            return

        self.model_loaded_ok = True
        logger.info(
            "Loaded %s for %s (R²=%s)%s%s",
            self.model_name,
            self.vehicle_type,
            self.metrics.get("r2", "N/A"),
            " + LOW model" if self.low_model is not None else "",
            " + HIGH model" if self.high_model is not None else "",
        )

    def _numeric_route_value(
        self, meta: Mapping[str, Any], route: str, key: str
    ) -> Optional[float]:
        value = self._route_value(meta, route, key)
        if value is None:
            return None
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"{route}_{key} inválido")
        return number

    def _load_low_route(self, model_dir: Path, meta: Mapping[str, Any]) -> None:
        raw_model = self._route_value(meta, "low", "model_path")
        raw_scaler = self._route_value(meta, "low", "scaler_path")
        self.low_scaler_declared = raw_scaler is not None
        if raw_scaler is not None:
            self.low_scaler = self._load_scaler(
                model_dir,
                raw_scaler,
                label="low_scaler_path",
                required=True,
            )
        if not raw_model:
            if raw_scaler is not None:
                raise ValueError("low_scaler_path declarado sem low_model_path")
            return
        path = self._resolve(model_dir, raw_model, "low_model_path")
        if not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"low_model_path em falta ou vazio: {path}")
        import xgboost as xgb

        model = xgb.XGBRegressor()
        model.load_model(str(path))
        self._validate_feature_count(model, "xgboost", "low_model")
        self.low_model = model

    def _load_high_route(self, model_dir: Path, meta: Mapping[str, Any]) -> None:
        raw_model = self._route_value(meta, "high", "model_path")
        raw_scaler = self._route_value(meta, "high", "scaler_path")
        self.high_scaler_declared = raw_scaler is not None
        if raw_scaler is not None:
            self.high_scaler = self._load_scaler(
                model_dir,
                raw_scaler,
                label="high_scaler_path",
                required=True,
            )
        if not raw_model:
            if raw_scaler is not None:
                raise ValueError("high_scaler_path declarado sem high_model_path")
            return
        path = self._resolve(model_dir, raw_model, "high_model_path")
        if not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"high_model_path em falta ou vazio: {path}")
        from catboost import CatBoostRegressor

        model = CatBoostRegressor()
        model.load_model(str(path), format="json" if path.suffix.lower() == ".json" else "cbm")
        self._validate_feature_count(model, "catboost", "high_model")
        self.high_model = model

    def _route_prediction(
        self,
        model: Any,
        X: np.ndarray,
        *,
        scaler: Any = None,
        cat_features: Optional[Sequence[int]] = None,
        log_target: bool = False,
    ) -> Optional[float]:
        routed = scaler.transform(X) if scaler is not None else X
        if cat_features:
            routed = X.astype(object)
            for index in cat_features:
                routed[0, index] = str(int(routed[0, index]))
        raw = np.asarray(model.predict(routed)).reshape(-1)
        if raw.size != 1 or not np.isfinite(raw[0]):
            return None
        value = float(np.expm1(raw[0]) if log_target else raw[0])
        if not math.isfinite(value) or value <= 0:
            return None
        return value

    def predict(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        """Predict only when the configured vehicle type and feature contract match."""
        if self.model is None or not self.model_loaded_ok:
            return None
        if not isinstance(vehicle_data, Mapping):
            return None
        try:
            supplied_type = vehicle_data.get("vehicle_type")
            if supplied_type is not None and normalize_vehicle_type(supplied_type) != self.vehicle_type:
                logger.warning(
                    "Recusada previsão cross-type: predictor=%s vehicle=%s",
                    self.vehicle_type,
                    supplied_type,
                )
                return None
            X = build_feature_vector(
                self.fs,
                vehicle_data,
                self.feature_names,
                required_fields=self.required_fields,
                reference_year=self.feature_reference_year,
            )
            if X.shape != (1, len(self.feature_names)) or not np.isfinite(X).all():
                return None
            full_pred = self._route_prediction(
                self.model,
                X,
                scaler=self.scaler,
                log_target=self.full_log_target,
            )
            if full_pred is None:
                return None

            if self.high_model is not None and self.high_threshold is not None and full_pred >= self.high_threshold:
                high_pred = self._route_prediction(
                    self.high_model,
                    X,
                    scaler=self.high_scaler if not self.high_cat_features else None,
                    cat_features=self.high_cat_features,
                    log_target=self.high_log_target,
                )
                if high_pred is not None:
                    return high_pred

            if self.low_model is not None and self.low_threshold is not None and full_pred < self.low_threshold:
                low_pred = self._route_prediction(
                    self.low_model,
                    X,
                    scaler=self.low_scaler,
                    log_target=self.low_log_target,
                )
                if low_pred is not None:
                    return low_pred
            return full_pred
        except Exception as exc:
            logger.error(
                "Prediction error (%s: %s) | modelo=%s | anúncio=%s",
                type(exc).__name__,
                exc,
                self.model_name,
                vehicle_data.get("id"),
            )
            return None

    def predict_with_interval(
        self, vehicle_data: Dict[str, Any]
    ) -> Optional[Tuple[float, float, float]]:
        pred = self.predict(vehicle_data)
        if pred is None:
            return None
        try:
            mape = float(self.metrics.get("mape_pct", 30.0) or 30.0) / 100.0
        except (TypeError, ValueError):
            mape = 0.30
        margin = pred * max(0.0, mape)
        return (pred - margin, pred, pred + margin)


def _vehicle_to_data(v) -> Dict[str, Any]:
    return {
        "id": v.id,
        "year": v.year,
        "km": v.km,
        "horsepower": v.horsepower,
        "engine_size": v.engine_size,
        "doors": v.doors,
        "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
        "transmission": v.transmission.value if v.transmission else "unknown",
        "brand": v.brand,
        "model": v.model,
        "version": v.version,
        "location": v.location,
        "district": v.district,
        "source": v.source.value if v.source else "",
        "vehicle_type": normalize_vehicle_type(v.vehicle_type),
        "title": v.title,
        "price": v.price,
        "condition_score": v.condition_score,
        "is_national": v.is_national,
    }


def update_vehicle_valuations(batch_size: int = 100, force: bool = False) -> int:
    """Reevaluate listings through the canonical ``valuation.service`` writer."""
    from valuation.service import revalue_database

    stats = revalue_database(
        batch_size=min(max(int(batch_size), 1), 1000),
        force=force,
        limit=batch_size,
    )
    processed = int(stats.get("processed", 0))
    logger.info("Updated %d vehicle valuations (stats=%s)", processed, stats)
    return processed
