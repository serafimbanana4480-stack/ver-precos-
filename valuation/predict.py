"""
Unified vehicle valuation prediction module.
Uses FeatureStore for consistent feature computation with dynamic brand index.

v2 (2026-08-01): carregamento defensivo do modelo.
* Se o artefacto estiver em falta ou for incompatível, ``model`` fica None e
  ``load_error`` explica a causa — nunca um regressor vazio que rebenta com
  ``Check failed: num_feature != 0`` em cada previsão.
* Validação de contagem de features antes de prever.
* ``update_vehicle_valuations`` escreve o resultado estruturado em
  ``valuation_details`` e é seguro para anúncios sem estimativa (marca como
  avaliados em vez de ciclar para sempre).
"""
from __future__ import annotations
import json
import logging
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from joblib import load
from core.settings import settings
from valuation.feature_store import FeatureStore

logger = logging.getLogger(__name__)


class PricePredictor:
    """Production inference pipeline. Loads best model + brand index from disk."""

    def __init__(self, vehicle_type: str = "carros"):
        self.vehicle_type = vehicle_type
        self.model = None
        self.model_name = None
        self.scaler = None
        self.feature_names: List[str] = []
        self.metrics: Dict[str, float] = {}
        self.low_metrics: Dict[str, float] = {}
        self.high_metrics: Dict[str, float] = {}
        self.fs = FeatureStore()
        # Segmented (low-end) model for two-stage routing
        self.low_model = None
        self.low_scaler = None
        self.low_threshold: Optional[float] = None
        # Segmented (high-end) CatBoost model for three-way routing
        self.high_model = None
        self.high_scaler = None
        self.high_threshold: Optional[float] = None
        self.high_log_target: bool = False
        self.high_cat_features: List[int] = []
        self.full_log_target: bool = False
        # Estado de carregamento (v2)
        self.model_loaded_ok: bool = False
        self.load_error: Optional[str] = None
        self._load_model()

    def _fail(self, msg: str) -> None:
        """Regista a falha e garante estado ML desativado e explícito."""
        self.load_error = msg
        self.model = None
        self.model_loaded_ok = False
        logger.error("Modelo %s indisponível: %s", self.vehicle_type, msg)

    def _load_model(self) -> None:
        model_dir = Path(settings.models_dir)
        metadata_path = model_dir / f"best_model_{self.vehicle_type}.json"
        if not metadata_path.exists():
            self._fail(f"metadados em falta: {metadata_path}")
            return
        try:
            with open(metadata_path, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            self._fail(f"metadados ilegíveis ({type(e).__name__}: {e})")
            return

        self.model_name = meta.get("model_type", "xgboost")
        self.metrics = meta.get("metrics", {})
        # Métricas por segmento (intervalos band-aware no HybridValuator)
        self.low_metrics = meta.get("low_metrics", {})
        self.high_metrics = meta.get("high_metrics_true_ge_20k", {})
        self.feature_names = meta.get("feature_names", [])
        self.low_threshold = meta.get("low_threshold")
        self.high_threshold = meta.get("high_threshold")
        self.high_log_target = meta.get("high_log_target", False)
        self.high_cat_features = meta.get("high_cat_features", [])
        self.full_log_target = meta.get("full_log_target", False)

        try:
            self.fs.load_index(model_dir / meta.get("brand_index_path", f"brand_index_{self.vehicle_type}.json"))
        except Exception as e:
            logger.warning("Brand index não carregado (%s); encoding dinâmico ficará vazio", e)

        # --- modelo principal: ficheiro tem de existir e carregar sem erro ---
        import_path = model_dir / meta.get("model_path", "")
        if not import_path.exists():
            self._fail(
                f"artefacto em falta: {import_path.name} referenciado nos metadados "
                f"mas não existe em {model_dir}. É preciso re-treinar "
                f"(ex.: `python main.py train --force`)."
            )
            return
        try:
            if self.model_name == "xgboost":
                import xgboost as xgb
                candidate = xgb.XGBRegressor()
                candidate.load_model(str(import_path))
                n_feat = int(candidate.get_booster().num_features())
                if n_feat == 0:
                    raise ValueError("booster carregado tem 0 features (artefacto vazio/corrompido)")
                if self.feature_names and n_feat != len(self.feature_names):
                    raise ValueError(
                        f"modelo espera {n_feat} features mas os metadados declaram "
                        f"{len(self.feature_names)} — pipeline treino/inferência desalinhado"
                    )
                self.model = candidate
            elif self.model_name == "lightgbm":
                import lightgbm as lgb
                self.model = lgb.Booster(model_file=str(import_path))
                try:
                    n_feat = int(self.model.num_feature())
                except Exception:
                    n_feat = int(self.model.dump_model().get("max_feature_idx", -1)) + 1
                if n_feat > 0 and self.feature_names and n_feat != len(self.feature_names):
                    raise ValueError(
                        f"modelo espera {n_feat} features mas os metadados declaram "
                        f"{len(self.feature_names)} — pipeline treino/inferência desalinhado"
                    )
            elif self.model_name == "catboost":
                from catboost import CatBoostRegressor
                self.model = CatBoostRegressor()
                self.model.load_model(str(import_path))
            elif self.model_name in ("random_forest", "extra_trees", "huber") or str(import_path).endswith(".joblib"):
                self.model = load(str(import_path))
                n_in = getattr(self.model, "n_features_in_", None)
                if n_in and self.feature_names and int(n_in) != len(self.feature_names):
                    raise ValueError(
                        f"modelo espera {n_in} features mas os metadados declaram "
                        f"{len(self.feature_names)} — pipeline treino/inferência desalinhado"
                    )
            else:
                self._fail(f"tipo de modelo desconhecido: {self.model_name}")
                return
        except Exception as e:
            self._fail(
                f"falha a carregar {import_path.name} ({type(e).__name__}: {e}). "
                "Provável incompatibilidade de versão ou artefacto corrompido — "
                "re-treinar o modelo."
            )
            return

        # --- scaler ---
        scaler_path = model_dir / meta.get("scaler_path", f"scaler_{self.vehicle_type}.joblib")
        if scaler_path.exists():
            try:
                self.scaler = load(str(scaler_path))
                n_in = getattr(self.scaler, "n_features_in_", None)
                if n_in and self.feature_names and int(n_in) != len(self.feature_names):
                    logger.warning(
                        "Scaler espera %s features, metadados declaram %d — scaler ignorado",
                        n_in, len(self.feature_names),
                    )
                    self.scaler = None
            except Exception as e:
                logger.warning("Scaler não carregado (%s); previsões sem scaling", e)
                self.scaler = None

        # --- modelo LOW opcional (não bloqueia o principal) ---
        low_model_path = meta.get("low_model_path")
        if low_model_path:
            low_path = model_dir / low_model_path
            if low_path.exists():
                try:
                    import xgboost as xgb
                    self.low_model = xgb.XGBRegressor()
                    self.low_model.load_model(str(low_path))
                    low_scaler_path = model_dir / meta.get("low_scaler_path", f"scaler_{self.vehicle_type}_low.joblib")
                    if low_scaler_path.exists():
                        self.low_scaler = load(str(low_scaler_path))
                except Exception as e:
                    logger.warning("Modelo LOW não carregado (%s); routing low-end desativado", e)
                    self.low_model = None
                    self.low_scaler = None

        # --- modelo HIGH opcional ---
        high_model_path = meta.get("high_model_path")
        if high_model_path:
            high_path = model_dir / high_model_path
            if high_path.exists():
                try:
                    from catboost import CatBoostRegressor
                    self.high_model = CatBoostRegressor()
                    high_fmt = "json" if str(high_path).endswith(".json") else "cbm"
                    self.high_model.load_model(str(high_path), format=high_fmt)
                    high_scaler_path = model_dir / meta.get("high_scaler_path", f"scaler_{self.vehicle_type}_high.joblib")
                    if high_scaler_path.exists():
                        self.high_scaler = load(str(high_scaler_path))
                except Exception as e:
                    logger.warning("Modelo HIGH não carregado (%s); routing high-end desativado", e)
                    self.high_model = None

        self.model_loaded_ok = True
        logger.info(
            "Loaded %s for %s (R²=%s)%s%s",
            self.model_name, self.vehicle_type, self.metrics.get("r2", "N/A"),
            " + LOW model" if self.low_model else "",
            " + HIGH model" if self.high_model else "",
        )

    def predict(self, vehicle_data: Dict[str, Any]) -> Optional[float]:
        if self.model is None or not self.model_loaded_ok:
            return None
        try:
            features = self.fs.compute_features(vehicle_data)
            X = np.array([[features.get(f, 0.0) for f in self.feature_names]], dtype=float)

            # Validação explícita treino/inferência
            if self.feature_names and X.shape[1] != len(self.feature_names):
                logger.error(
                    "Feature mismatch: inferência produziu %d colunas, modelo espera %d",
                    X.shape[1], len(self.feature_names),
                )
                return None
            if not np.isfinite(X).all():
                X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

            if self.scaler:
                X_full = self.scaler.transform(X)
            else:
                X_full = X
            full_pred = float(self.model.predict(X_full)[0])
            if self.full_log_target:
                full_pred = float(np.expm1(full_pred))
            full_pred = max(full_pred, 0.0)

            # High-end routing
            if self.high_model is not None and self.high_threshold and full_pred >= self.high_threshold:
                if self.high_cat_features:
                    X_high = X.astype(object)
                    for c in self.high_cat_features:
                        X_high[0, c] = str(int(X_high[0, c]))
                elif self.high_scaler is not None:
                    X_high = self.high_scaler.transform(X)
                else:
                    X_high = X
                high_pred = float(self.high_model.predict(X_high)[0])
                if self.high_log_target:
                    high_pred = float(np.expm1(high_pred))
                return max(high_pred, 0.0)

            # Low-end routing
            if (self.low_model is not None and self.low_scaler is not None
                    and self.low_threshold and full_pred < self.low_threshold):
                X_low = self.low_scaler.transform(X)
                low_pred = float(self.low_model.predict(X_low)[0])
                return max(low_pred, 0.0)

            return full_pred
        except Exception as e:
            logger.error(
                "Prediction error (%s: %s) | modelo=%s | anúncio=%s",
                type(e).__name__, e, self.model_name, vehicle_data.get("id"),
            )
            return None

    def predict_with_interval(self, vehicle_data: Dict[str, Any]) -> Optional[Tuple[float, float, float]]:
        pred = self.predict(vehicle_data)
        if pred is None:
            return None
        mape = self.metrics.get("mape_pct", 30.0) / 100.0
        margin = pred * mape
        return (pred - margin, pred, pred + margin)


def _vehicle_to_data(v) -> Dict[str, Any]:
    return {
        "id": v.id,
        "year": v.year, "km": v.km, "horsepower": v.horsepower,
        "engine_size": v.engine_size, "doors": v.doors,
        "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
        "transmission": v.transmission.value if v.transmission else "unknown",
        "brand": v.brand or "Unknown", "model": v.model or "",
        "version": v.version or "",
        "location": v.location or "", "district": v.district or "",
        "source": v.source.value if v.source else "",
        "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros",
        "title": v.title or "",
        "price": v.price or 0,
        "condition_score": v.condition_score or 3.0,
        "is_national": v.is_national,
    }


def update_vehicle_valuations(batch_size: int = 100, force: bool = False) -> int:
    """Reavalia anúncios com o motor coerente (valuation/service).

    Substitui a escrita legada (que só gravava 4 campos e deixava as colunas
    ``credible_profit``/``deal_grade``/``profit_is_publishable``/… congeladas,
    origem das «vantagens» falsas no dashboard). Agora **todos** os campos
    derivados nascem do mesmo bloco e são escritos em conjunto.

    Retomável e idempotente: por omissão só processa quem ainda não tem a
    versão atual; ``force=True`` reprocessa tudo (limitado a ``batch_size``).
    """
    from database.db import get_db_context
    from database.models import Vehicle
    from sqlalchemy import or_
    from valuation.service import (
        VALUATION_VERSION, ValuationService, load_market_rows, vehicle_to_dict,
    )

    with get_db_context() as db:
        query = db.query(Vehicle).filter(Vehicle.is_active == True)  # noqa: E712
        if not force:
            query = query.filter(
                or_(
                    Vehicle.valuation_details.is_(None),
                    Vehicle.valuation_details["valuation_version"].as_string() != VALUATION_VERSION,
                )
            )
        vehicles = query.limit(batch_size).all()
        if not vehicles:
            return 0

        rows = [vehicle_to_dict(v) for v in vehicles]
        svc = ValuationService.from_rows([r for r in rows], apply_dedupe=False)
        by_id = {r["id"]: r for r in rows}
        updated = 0
        for v in vehicles:
            res = svc.evaluate(by_id[v.id])
            fields = res.derived_fields()
            for k, val in fields.items():
                setattr(v, k, val)
            updated += 1
        db.commit()

    logger.info("Updated %d vehicle valuations (v%s)", updated, VALUATION_VERSION)
    return updated
