"""
Unified ML training pipeline.
Supports XGBoost, LightGBM, CatBoost with auto-selection of best model.
Uses TimeSeriesSplit to prevent data leakage.
Optimizations: Optuna hyperparameter tuning, ensemble (VotingRegressor),
feature selection, and outlier removal with IsolationForest.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score, mean_absolute_percentage_error
from sklearn.ensemble import VotingRegressor, IsolationForest
from sklearn.feature_selection import SelectKBest, f_regression
from joblib import dump

from core.settings import settings
from valuation.feature_store import FeatureStore

logger = logging.getLogger(__name__)


def _val_str(val) -> str:
    if val is None:
        return "unknown"
    if hasattr(val, "value"):
        return val.value
    return str(val)


def remove_outliers_isolation_forest(X: np.ndarray, y: np.ndarray, 
                                      contamination: float = 0.1) -> Tuple[np.ndarray, np.ndarray]:
    """
    Remove outliers from features using IsolationForest.
    
    Args:
        X: Feature matrix
        y: Target vector
        contamination: Expected proportion of outliers
        
    Returns:
        Tuple of (X_filtered, y_filtered)
    """
    iso_forest = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100
    )
    
    # Fit on features only (not target)
    outlier_labels = iso_forest.fit_predict(X)
    
    # Keep inliers (label = 1)
    inlier_mask = outlier_labels == 1
    
    n_removed = int((~inlier_mask).sum())
    if n_removed > 0:
        logger.info(f"IsolationForest removed {n_removed} outliers ({n_removed/len(X)*100:.1f}%)")
    
    return X[inlier_mask], y[inlier_mask]


def select_features_kbest(X: np.ndarray, y: np.ndarray, 
                          k: int = 10) -> Tuple[np.ndarray, object]:
    """
    Select top k features using SelectKBest with f_regression.
    
    Args:
        X: Feature matrix
        y: Target vector
        k: Number of top features to select
        
    Returns:
        Tuple of (X_selected, selector)
    """
    # Ensure k doesn't exceed number of features
    k = min(k, X.shape[1])
    
    selector = SelectKBest(f_regression, k=k)
    X_selected = selector.fit_transform(X, y)
    
    # Log selected features
    mask = selector.get_support()
    logger.info(f"SelectKBest selected {k} features (mask: {mask})")
    
    return X_selected, selector


def select_features_l1(X: np.ndarray, y: np.ndarray, 
                       C: float = 1.0) -> Tuple[np.ndarray, object]:
    """
    Select features using L1 regularization (Lasso).
    
    Args:
        X: Feature matrix
        y: Target vector
        C: Inverse of regularization strength
        
    Returns:
        Tuple of (X_selected, selector)
    """
    from sklearn.linear_model import Lasso
    
    # Fit Lasso
    lasso = Lasso(alpha=1.0/C, random_state=42)
    lasso.fit(X, y)
    
    # Get feature importance (absolute coefficients)
    coef = np.abs(lasso.coef_)
    
    # Select features with non-zero coefficients
    mask = coef > 0
    
    # If all coefficients are zero, keep all features
    if not np.any(mask):
        logger.warning("L1 regularization resulted in all zero coefficients, keeping all features")
        mask = np.ones(X.shape[1], dtype=bool)
    
    X_selected = X[:, mask]
    n_selected = int(mask.sum())
    logger.info(f"L1 regularization selected {n_selected} features")
    
    return X_selected, mask


def get_optuna_params(trial, model_name: str) -> Dict:
    """
    Define hyperparameter search space for Optuna.
    
    Args:
        trial: Optuna trial object
        model_name: Name of the model (xgboost, lightgbm, catboost)
        
    Returns:
        Dictionary of hyperparameters
    """
    if model_name == "xgboost":
        return {
            "n_estimators": trial.suggest_int("xgb_n_estimators", 300, 1000),
            "max_depth": trial.suggest_int("xgb_max_depth", 4, 12),
            "learning_rate": trial.suggest_float("xgb_learning_rate", 0.01, 0.1, log=True),
            "subsample": trial.suggest_float("xgb_subsample", 0.6, 0.9),
            "colsample_bytree": trial.suggest_float("xgb_colsample_bytree", 0.6, 0.9),
            "min_child_weight": trial.suggest_int("xgb_min_child_weight", 1, 10),
            "reg_lambda": trial.suggest_float("xgb_reg_lambda", 0.1, 10.0, log=True),
            "reg_alpha": trial.suggest_float("xgb_reg_alpha", 0.1, 10.0, log=True),
        }
    
    elif model_name == "lightgbm":
        return {
            "n_estimators": trial.suggest_int("lgb_n_estimators", 300, 1000),
            "max_depth": trial.suggest_int("lgb_max_depth", 4, 12),
            "learning_rate": trial.suggest_float("lgb_learning_rate", 0.01, 0.1, log=True),
            "subsample": trial.suggest_float("lgb_subsample", 0.6, 0.9),
            "colsample_bytree": trial.suggest_float("lgb_colsample_bytree", 0.6, 0.9),
            "min_child_samples": trial.suggest_int("lgb_min_child_samples", 3, 20),
            "reg_lambda": trial.suggest_float("lgb_reg_lambda", 0.1, 10.0, log=True),
            "reg_alpha": trial.suggest_float("lgb_reg_alpha", 0.1, 10.0, log=True),
        }
    
    elif model_name == "catboost":
        return {
            "iterations": trial.suggest_int("cat_iterations", 300, 1000),
            "depth": trial.suggest_int("cat_depth", 4, 12),
            "learning_rate": trial.suggest_float("cat_learning_rate", 0.01, 0.1, log=True),
            "subsample": trial.suggest_float("cat_subsample", 0.6, 0.9),
            "l2_leaf_reg": trial.suggest_float("cat_l2_leaf_reg", 0.1, 10.0, log=True),
        }
    
    return {}


def create_model_with_params(model_name: str, params: Dict, n_features: int = None):
    """
    Create a model instance with given parameters.
    
    Args:
        model_name: Name of the model
        params: Hyperparameter dictionary
        n_features: Number of features (for feature selection)
        
    Returns:
        Model instance
    """
    if model_name == "xgboost":
        import xgboost as xgb
        return xgb.XGBRegressor(
            n_estimators=params.get("n_estimators", 500),
            max_depth=params.get("max_depth", 8),
            learning_rate=params.get("learning_rate", 0.03),
            subsample=params.get("subsample", 0.8),
            colsample_bytree=params.get("colsample_bytree", 0.8),
            min_child_weight=params.get("min_child_weight", 3),
            reg_lambda=params.get("reg_lambda", 2.0),
            reg_alpha=params.get("reg_alpha", 1.0),
            random_state=42,
        )
    
    elif model_name == "lightgbm":
        import lightgbm as lgb
        return lgb.LGBMRegressor(
            n_estimators=params.get("n_estimators", 500),
            max_depth=params.get("max_depth", 8),
            learning_rate=params.get("learning_rate", 0.03),
            subsample=params.get("subsample", 0.8),
            colsample_bytree=params.get("colsample_bytree", 0.8),
            min_child_samples=params.get("min_child_samples", 5),
            reg_lambda=params.get("reg_lambda", 2.0),
            reg_alpha=params.get("reg_alpha", 1.0),
            random_state=42,
            verbose=-1,
        )
    
    elif model_name == "catboost":
        from catboost import CatBoostRegressor
        return CatBoostRegressor(
            iterations=params.get("iterations", 500),
            depth=params.get("depth", 8),
            learning_rate=params.get("learning_rate", 0.03),
            subsample=params.get("subsample", 0.8),
            random_seed=42,
            verbose=False,
            l2_leaf_reg=params.get("l2_leaf_reg", 2.0),
        )
    
    return None


def optimize_hyperparams_optuna(X: np.ndarray, y: np.ndarray, 
                                 model_name: str,
                                 n_trials: int = 50) -> Dict:
    """
    Optimize hyperparameters using Optuna.
    
    Args:
        X: Feature matrix
        y: Target vector
        model_name: Name of the model to optimize
        n_trials: Number of Optuna trials
        
    Returns:
        Best hyperparameters
    """
    import optuna
    
    def objective(trial):
        try:
            params = get_optuna_params(trial, model_name)
            model = create_model_with_params(model_name, params)
            
            # Use TimeSeriesSplit for CV
            tscv = TimeSeriesSplit(n_splits=3)
            cv_scores = []
            
            for train_idx, val_idx in tscv.split(X):
                X_train, X_val = X[train_idx], X[val_idx]
                y_train, y_val = y[train_idx], y[val_idx]
                
                model.fit(X_train, y_train)
                y_pred = model.predict(X_val)
                score = r2_score(y_val, y_pred)
                cv_scores.append(score)
            
            return np.mean(cv_scores)
        except Exception as e:
            logger.warning(f"Trial failed with error: {e}")
            # Return a very low score to indicate failure
            return -1e9
    
    # Create study
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    
    logger.info(f"Optuna best params for {model_name}: {study.best_params}")
    logger.info(f"Optuna best R² score: {study.best_value:.4f}")
    
    return study.best_params


def create_ensemble_model(X: np.ndarray, y: np.ndarray,
                          use_optuna: bool = True,
                          n_trials: int = 20) -> VotingRegressor:
    """
    Create ensemble model using VotingRegressor with XGBoost+LightGBM+CatBoost.
    
    Args:
        X: Feature matrix (for hyperparameter optimization)
        y: Target vector
        use_optuna: Whether to optimize hyperparameters with Optuna
        n_trials: Number of Optuna trials per model
        
    Returns:
        VotingRegressor ensemble
    """
    estimators = []
    
    # XGBoost
    try:
        import xgboost as xgb
        
        if use_optuna:
            xgb_params = optimize_hyperparams_optuna(X, y, "xgboost", n_trials)
            xgb_model = create_model_with_params("xgboost", xgb_params)
        else:
            xgb_model = xgb.XGBRegressor(
                n_estimators=500, max_depth=8, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8,
                min_child_weight=3, reg_lambda=2.0, reg_alpha=1.0,
                random_state=42,
            )
        
        estimators.append(("xgboost", xgb_model))
        logger.info("Added XGBoost to ensemble")
        
    except ImportError:
        logger.warning("XGBoost not installed, skipping for ensemble")
    
    # LightGBM
    try:
        import lightgbm as lgb
        
        if use_optuna:
            lgb_params = optimize_hyperparams_optuna(X, y, "lightgbm", n_trials)
            lgb_model = create_model_with_params("lightgbm", lgb_params)
        else:
            lgb_model = lgb.LGBMRegressor(
                n_estimators=500, max_depth=8, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8,
                min_child_samples=5, reg_lambda=2.0, reg_alpha=1.0,
                random_state=42, verbose=-1,
            )
        
        estimators.append(("lightgbm", lgb_model))
        logger.info("Added LightGBM to ensemble")
        
    except ImportError:
        logger.warning("LightGBM not installed, skipping for ensemble")
    
    # CatBoost
    try:
        from catboost import CatBoostRegressor
        
        if use_optuna:
            cat_params = optimize_hyperparams_optuna(X, y, "catboost", n_trials)
            cat_model = create_model_with_params("catboost", cat_params)
        else:
            cat_model = CatBoostRegressor(
                iterations=500, depth=8, learning_rate=0.03,
                subsample=0.8, random_seed=42, verbose=False,
                l2_leaf_reg=2.0,
            )
        
        estimators.append(("catboost", cat_model))
        logger.info("Added CatBoost to ensemble")
        
    except ImportError:
        logger.warning("CatBoost not installed, skipping for ensemble")
    
    if not estimators:
        raise ValueError("No models available for ensemble. Install xgboost, lightgbm, or catboost.")
    
    # Create VotingRegressor with soft voting (averaging predictions)
    ensemble = VotingRegressor(estimators=estimators, n_jobs=-1)
    logger.info(f"Created ensemble with {len(estimators)} models")
    
    return ensemble


def load_raw_data(vehicle_type: str = "carros") -> pd.DataFrame:
    from database.db import get_db_context
    from database.models import Vehicle, VehicleType

    with get_db_context() as db:
        query = db.query(Vehicle).filter(
            Vehicle.vehicle_type == VehicleType(vehicle_type),
            Vehicle.price > 500,
            Vehicle.price < 500000,
            Vehicle.year.isnot(None),
        )
        # For cars, require KM data (essential); for motorcycles be more lenient
        if vehicle_type == "carros":
            query = query.filter(Vehicle.km.isnot(None), Vehicle.km > 0)
        
        rows = query.all()

        records = [{
            "year": v.year, "km": v.km or 0,
            "horsepower": v.horsepower or 0, "engine_size": v.engine_size or 0,
            "doors": v.doors or 4,
            "fuel_type": _val_str(v.fuel_type),
            "transmission": _val_str(v.transmission),
            "brand": v.brand or "Unknown",
            "model": v.model or "",
            "location": v.location or "",
            "price": v.price,
            "first_seen": v.first_seen,
        } for v in rows]

    df = pd.DataFrame(records)
    logger.info(f"Loaded {len(df)} rows for {vehicle_type}")
    return df


def train_model(vehicle_type: str = "carros", force_retrain: bool = False) -> Optional[Dict]:
    raw = load_raw_data(vehicle_type)
    if len(raw) < settings.ml_min_samples:
        logger.warning(f"Only {len(raw)} samples for {vehicle_type}, need {settings.ml_min_samples}")
        return None

    fs = FeatureStore()
    fs.build_brand_index(raw["brand"].tolist())
    fs.build_model_index(raw["model"].tolist())

    records = []
    for r in raw.to_dict("records"):
        feat = fs.compute_features(r)
        feat["price"] = r["price"]
        records.append(feat)
    df = pd.DataFrame(records).dropna(subset=["price"]).fillna(0)

    feature_cols = FeatureStore.ALLOWED_FEATURES
    X = df[feature_cols].values
    y = df["price"].values

    if np.any(y <= 0):
        logger.warning(f"Removing {int((y <= 0).sum())} rows with non-positive price")
        mask = y > 0
        X, y = X[mask], y[mask]

    # === OPTIMIZATION 4: Outlier Removal with IsolationForest ===
    logger.info("Applying IsolationForest for outlier removal...")
    X, y = remove_outliers_isolation_forest(X, y, contamination=0.1)
    logger.info(f"Samples after outlier removal: {len(X)}")

    # === OPTIMIZATION 3: Feature Selection ===
    # Option A: SelectKBest (uncomment to use)
    # logger.info("Applying SelectKBest for feature selection...")
    # X, feature_selector = select_features_kbest(X, y, k=10)
    
    # Option B: L1 regularization (uncomment to use)
    logger.info("Applying L1 regularization for feature selection...")
    X, feature_mask = select_features_l1(X, y, C=1.0)
    
    # If using L1, we need to track selected feature names
    if isinstance(feature_mask, np.ndarray) and feature_mask.dtype == bool:
        selected_features = [feature_cols[i] for i in range(len(feature_cols)) if feature_mask[i]]
        logger.info(f"Selected features: {selected_features}")
    else:
        selected_features = feature_cols

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    tscv = TimeSeriesSplit(n_splits=5)
    results = {}

    # === OPTIMIZATION 2: Ensemble Model ===
    logger.info("Creating ensemble model with XGBoost+LightGBM+CatBoost...")
    use_optuna_for_ensemble = True  # Set to False to skip Optuna for faster training
    ensemble_model = create_ensemble_model(
        X_scaled, y, 
        use_optuna=use_optuna_for_ensemble,
        n_trials=20  # Reduce for faster training, increase for better results
    )

    models = {"ensemble": ensemble_model}

    # Also keep individual models for comparison
    try:
        import xgboost as xgb
        
        # === OPTIMIZATION 1: Optuna Hyperparameter Tuning ===
        logger.info("Optimizing XGBoost hyperparameters with Optuna...")
        xgb_params = optimize_hyperparams_optuna(X_scaled, y, "xgboost", n_trials=30)
        xgb_model = create_model_with_params("xgboost", xgb_params)
        models["xgboost"] = xgb_model
    except ImportError:
        logger.warning("XGBoost not installed")

    try:
        import lightgbm as lgb
        
        logger.info("Optimizing LightGBM hyperparameters with Optuna...")
        lgb_params = optimize_hyperparams_optuna(X_scaled, y, "lightgbm", n_trials=30)
        lgb_model = create_model_with_params("lightgbm", lgb_params)
        models["lightgbm"] = lgb_model
    except ImportError:
        logger.warning("LightGBM not installed")

    try:
        from catboost import CatBoostRegressor
        
        logger.info("Optimizing CatBoost hyperparameters with Optuna...")
        cat_params = optimize_hyperparams_optuna(X_scaled, y, "catboost", n_trials=30)
        cat_model = create_model_with_params("catboost", cat_params)
        models["catboost"] = cat_model
    except ImportError:
        logger.warning("CatBoost not installed")

    if not models:
        logger.error("No ML framework available. Install xgboost, lightgbm, or catboost.")
        return None

    best_r2 = -1e9
    best_model = None
    best_name = None

    for name, model in models.items():
        cv_r2 = []
        cv_mae = []
        cv_mape = []

        for train_idx, test_idx in tscv.split(X_scaled):
            X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            cv_r2.append(r2_score(y_test, y_pred))
            cv_mae.append(mean_absolute_error(y_test, y_pred))
            cv_mape.append(mean_absolute_percentage_error(y_test, y_pred) * 100)

        avg_r2 = np.mean(cv_r2)
        avg_mae = np.mean(cv_mae)
        avg_mape = np.mean(cv_mape)

        results[name] = {"r2": float(avg_r2), "mae": float(avg_mae), "mape_pct": float(avg_mape)}

        logger.info(f"{name} CV R²={avg_r2:.4f} MAE=€{avg_mae:.0f} MAPE={avg_mape:.1f}%")

        if avg_r2 > best_r2 and avg_r2 >= settings.ml_min_r2:
            best_r2 = avg_r2
            best_model = model
            best_name = name

    if best_model is None:
        if not models:
            return {"metrics": results, "status": "failed", "best_r2": float(best_r2)}
        best_name = max(results, key=lambda k: results[k]["r2"])
        best_model = models[best_name]
        best_r2 = results[best_name]["r2"]
        logger.warning(f"No model met R²>={settings.ml_min_r2}. "
                       f"Saving best: {best_name} (R²={best_r2:.4f})")

    logger.info(f"Training final {best_name} model on all data...")
    best_model.fit(X_scaled, y)
    model_dir = Path(settings.models_dir)
    model_dir.mkdir(exist_ok=True)

    # Handle ensemble model saving (save individual models)
    if best_name == "ensemble":
        # Save each estimator in the ensemble
        for i, (est_name, est_model) in enumerate(best_model.named_estimators.items()):
            ext_map = {"xgboost": "json", "lightgbm": "txt", "catboost": "cbm"}
            ext = ext_map.get(est_name, "json")
            model_path = f"model_{vehicle_type}_{est_name}.{ext}"
            
            try:
                if est_name == "xgboost":
                    est_model.save_model(str(model_dir / model_path))
                elif est_name == "lightgbm":
                    est_model.booster_.save_model(str(model_dir / model_path))
                elif est_name == "catboost":
                    est_model.save_model(str(model_dir / model_path))
                logger.info(f"Saved {est_name} model to {model_path}")
            except Exception as e:
                logger.error(f"Failed to save {est_name} model: {e}")
        
        # Save ensemble metadata
        model_path = f"ensemble_{vehicle_type}"
    else:
        # Original saving logic for individual models
        ext_map = {"xgboost": "json", "lightgbm": "txt", "catboost": "cbm"}
        ext = ext_map.get(best_name, "json")
        model_path = f"model_{vehicle_type}.{ext}"

        if best_name == "xgboost":
            best_model.save_model(str(model_dir / model_path))
        elif best_name == "lightgbm":
            best_model.booster_.save_model(str(model_dir / model_path))
        elif best_name == "catboost":
            best_model.save_model(str(model_dir / model_path))

    dump(scaler, str(model_dir / f"scaler_{vehicle_type}.joblib"))

    fs.save_index(model_dir / f"brand_index_{vehicle_type}.json")

    metadata = {
        "model_type": best_name,
        "model_path": model_path,
        "scaler_path": f"scaler_{vehicle_type}.joblib",
        "brand_index_path": f"brand_index_{vehicle_type}.json",
        "vehicle_type": vehicle_type,
        "feature_names": selected_features,  # Use selected features
        "metrics": results[best_name],
        "n_samples": len(df),
        "trained_at": datetime.now().isoformat(),
        "optimizations": {
            "optuna_tuning": True,
            "ensemble_model": best_name == "ensemble",
            "feature_selection": True,
            "outlier_removal": True,
        }
    }

    with open(model_dir / f"best_model_{vehicle_type}.json", "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"{best_name} model for {vehicle_type}: R²={best_r2:.4f}, MAE=€{results[best_name]['mae']:.0f}")
    return metadata


def train_all_models(force_retrain: bool = False) -> Dict[str, Optional[Dict]]:
    results = {}
    for vtype in ["carros", "motos"]:
        logger.info(f"Training {vtype} model...")
        results[vtype] = train_model(vtype, force_retrain)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = train_all_models(force_retrain=True)
    print(json.dumps({k: v.get("metrics") if v else None for k, v in results.items()}, indent=2))
