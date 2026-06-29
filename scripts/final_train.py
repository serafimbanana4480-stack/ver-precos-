"""
Final training + cleanup script for VER PRECOS.
1. Remove duplicate vehicles (same URL or source+source_id)
2. Train XGBoost model on all training-ready data
3. Update valuations for all vehicles
"""
import sys, json, logging
from pathlib import Path
from datetime import datetime
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)


def remove_duplicates():
    """Remove duplicate vehicles keeping the one with most data."""
    from database.db import get_db_context
    from database.models import Vehicle
    from sqlalchemy import func

    with get_db_context() as db:
        # Find duplicates by URL
        dups = db.query(
            Vehicle.url, func.count(Vehicle.id).label('cnt')
        ).group_by(Vehicle.url).having(func.count(Vehicle.id) > 1).all()
        
        removed = 0
        for url, cnt in dups:
            vehicles = db.query(Vehicle).filter(Vehicle.url == url).order_by(Vehicle.id).all()
            # Keep the one with most non-null fields
            best = max(vehicles, key=lambda v: sum(1 for x in [v.year, v.km, v.horsepower, v.fuel_type] if x is not None))
            for v in vehicles:
                if v.id != best.id:
                    db.delete(v)
                    removed += 1
        
        db.commit()
        logger.info(f"Removed {removed} duplicate vehicles by URL")
        return removed


def final_training():
    """Train final XGBoost model on all data."""
    from core.settings import settings
    from valuation.feature_store import FeatureStore
    from valuation.train import load_raw_data
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import r2_score, mean_absolute_error, mean_absolute_percentage_error
    from joblib import dump
    import xgboost as xgb

    logger.info("Loading training data...")
    df = load_raw_data('carros')
    logger.info(f"Loaded {len(df)} rows")

    if len(df) < 100:
        logger.error("Not enough data to train")
        return None

    # Feature store
    fs = FeatureStore()
    fs.build_brand_index(df['brand'].dropna().tolist())
    fs.build_model_index(df['model'].dropna().tolist())

    # Compute features
    features_list = [fs.compute_features(row.to_dict()) for _, row in df.iterrows()]

    feature_cols = [
        'year', 'km', 'horsepower', 'engine_size', 'doors',
        'age', 'km_per_year', 'fuel_type', 'transmission',
        'brand', 'model', 'district',
        'depreciation_factor', 'fuel_premium', 'location_premium',
        'age_group', 'km_category', 'brand_popularity',
    ]

    X = np.array([[f.get(c, 0.0) for c in feature_cols] for f in features_list])
    y = df['price'].values

    logger.info(f"X shape: {X.shape}")

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Cross-validation
    tscv = TimeSeriesSplit(n_splits=5)
    cv_r2, cv_mae, cv_mape = [], [], []

    for train_idx, test_idx in tscv.split(X_scaled):
        X_tr, X_te = X_scaled[train_idx], X_scaled[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        model = xgb.XGBRegressor(
            n_estimators=500, max_depth=8, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
        )
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)

        cv_r2.append(r2_score(y_te, y_pred))
        cv_mae.append(mean_absolute_error(y_te, y_pred))
        cv_mape.append(mean_absolute_percentage_error(y_te, y_pred) * 100)

    avg_r2 = np.mean(cv_r2)
    avg_mae = np.mean(cv_mae)
    avg_mape = np.mean(cv_mape)

    logger.info(f"CV Results: R²={avg_r2:.4f}, MAE=€{avg_mae:.0f}, MAPE={avg_mape:.1f}%")

    # Train final model on ALL data
    logger.info("Training final model on all data...")
    final_model = xgb.XGBRegressor(
        n_estimators=500, max_depth=8, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
    )
    final_model.fit(X_scaled, y)

    # Save
    model_dir = Path(settings.models_dir)
    model_dir.mkdir(exist_ok=True)
    final_model.save_model(str(model_dir / 'model_carros.json'))
    dump(scaler, str(model_dir / 'scaler_carros.joblib'))
    fs.save_index(model_dir / 'brand_index_carros.json')

    metadata = {
        'model_type': 'xgboost',
        'model_path': 'model_carros.json',
        'scaler_path': 'scaler_carros.joblib',
        'brand_index_path': 'brand_index_carros.json',
        'vehicle_type': 'carros',
        'feature_names': feature_cols,
        'metrics': {
            'r2': float(avg_r2),
            'mae': float(avg_mae),
            'mape_pct': float(avg_mape),
        },
        'n_samples': len(df),
        'trained_at': datetime.now().isoformat(),
    }

    with open(model_dir / 'best_model_carros.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Model saved! R²={avg_r2:.4f}, MAE=€{avg_mae:.0f}, n={len(df)}")
    return metadata


def update_all_valuations():
    """Update valuations for all vehicles without one."""
    from valuation.predict import update_vehicle_valuations
    n = update_vehicle_valuations(5000)
    logger.info(f"Updated {n} vehicle valuations")
    return n


if __name__ == '__main__':
    import sqlite3

    # Step 1: Check DB state
    conn = sqlite3.connect('data/autodeal.db')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM vehicles WHERE is_active=1')
    total = cur.fetchone()[0]
    cur.execute('SELECT source, COUNT(*) FROM vehicles WHERE is_active=1 GROUP BY source ORDER BY COUNT(*) DESC')
    sources = cur.fetchall()
    conn.close()

    print(f"\n{'='*60}")
    print(f"  VER PRECOS - Final Training Pipeline")
    print(f"  {total} active vehicles")
    for s, c in sources:
        print(f"    {s}: {c}")
    print(f"{'='*60}\n")

    # Step 2: Remove duplicates
    print("Step 1: Removing duplicates...")
    removed = remove_duplicates()

    # Step 3: Train
    print("\nStep 2: Training model...")
    result = final_training()

    # Step 4: Update valuations
    print("\nStep 3: Updating valuations...")
    updated = update_all_valuations()

    # Final report
    print(f"\n{'='*60}")
    print(f"  FINAL RESULTS")
    print(f"  Duplicates removed: {removed}")
    print(f"  Vehicles with valuation: {updated}")
    if result:
        m = result['metrics']
        print(f"  Model: XGBoost R²={m['r2']:.4f}, MAE=€{m['mae']:.0f}, MAPE={m['mape_pct']:.1f}%")
        print(f"  Training samples: {result['n_samples']}")
    print(f"{'='*60}")
