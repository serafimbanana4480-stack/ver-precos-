"""
VER PRECOS — Production Pipeline
=================================
One script to run everything: scrape → clean → train → evaluate

Usage:
    python scripts/pipeline.py scrape    # Scrape all sources
    python scripts/pipeline.py train     # Train model on current data
    python scripts/pipeline.py all       # Scrape + train
    python scripts/pipeline.py dashboard # Launch dashboard
"""
import sys, time, argparse, logging, json, sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/autodeal.db"


def scrape_all():
    """Run all available scrapers and save to DB."""
    import requests, re
    from database.db import get_db_context
    from database.models import Vehicle, Source, VehicleType, FuelType, Transmission

    results = {}
    start = time.time()

    # ── AutoUncle ─────────────────────────────────────────────────────────
    logger.info("Scraping AutoUncle...")
    try:
        from scrapers.autouncle_lightweight import AutoUncleLightweight
        s = AutoUncleLightweight()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        # Get sitemap
        r = requests.get(
            'https://www.autouncle.pt/sitemaps/pt/autouncle_brand-car_model-pages_links.xml',
            headers=headers, timeout=15,
        )
        urls = re.findall(r'<loc>(.*?)</loc>', r.text)

        popular = ['BMW','Mercedes','Audi','Volkswagen','Renault','Peugeot','Toyota','Ford',
                   'Opel','Seat','Nissan','Hyundai','Kia','Volvo','Citro','Fiat','Dacia','Skoda',
                   'Mini','Mazda','Honda','Mitsubishi','Suzuki','Jeep','Land','Porsche','Alfa',
                   'BYD','Polestar','Tesla','Jaguar','Lexus','DS','Smart','Lancia']
        top_urls = [u for u in urls if any(b.lower() in u.lower() for b in popular)][:30]

        au_listings = []
        for i, url in enumerate(top_urls):
            try:
                resp = s.session.get(url, timeout=20)
                if resp.status_code == 200:
                    listings = s._parse_page(resp.text, 0)
                    au_listings.extend(listings)
            except Exception:
                pass
            time.sleep(0.2)

        # Save
        saved = 0
        with get_db_context() as db:
            for l in au_listings:
                url = l.get('url', '')
                if not url: continue
                existing = db.query(Vehicle).filter(Vehicle.url == url).first()
                if existing: continue

                brand = str(l.get('brand', 'Unknown'))[:100]
                if not brand or brand.lower() in ('unknown', '', 'none'): continue
                price = l.get('price')
                if not price or float(price) <= 0: continue

                v = Vehicle(
                    source=Source.AUTOPT,
                    source_id=str(l.get('source_id', url))[:100], url=url,
                    vehicle_type=VehicleType.carros,
                    brand=brand, model=str(l.get('model', ''))[:100],
                    year=l.get('year'), km=l.get('km'), price=float(price),
                    title=str(l.get('title', ''))[:500],
                    horsepower=l.get('horsepower'), engine_size=l.get('engine_size'),
                    location=str(l.get('location', ''))[:200],
                    images=l.get('images', []) or [], image_count=l.get('image_count', 0),
                    deal_grade=l.get('deal_rating'), seller_name=l.get('seller_name'),
                    is_active=True,
                    first_seen=datetime.now(), last_seen=datetime.now(),
                )
                db.add(v)
                saved += 1
            db.commit()

        results['autouncle'] = f"{len(au_listings)} found, {saved} new"
        logger.info(f"AutoUncle: {len(au_listings)} found, {saved} saved")
    except Exception as e:
        results['autouncle'] = f"ERROR: {e}"
        logger.error(f"AutoUncle failed: {e}")

    # ── Leilosoc ───────────────────────────────────────────────────────────
    logger.info("Scraping Leilosoc...")
    try:
        from scrapers.leilosoc_lightweight import LeilosocLightweight
        s2 = LeilosocLightweight()
        le_listings = s2.scrape_listings(max_listings=120)

        saved = 0
        with get_db_context() as db:
            for l in le_listings:
                url = l.get('url', '')
                if not url: continue
                existing = db.query(Vehicle).filter(Vehicle.url == url).first()
                if existing: continue

                brand = str(l.get('brand', 'Unknown'))[:100]
                price = l.get('price')
                if not brand or not price or float(price) <= 0: continue

                v = Vehicle(
                    source=Source.LEILOSOC,
                    source_id=str(l.get('source_id', url))[:100], url=url,
                    vehicle_type=VehicleType.carros,
                    brand=brand, model=str(l.get('model', ''))[:100],
                    year=l.get('year'), km=l.get('km'), price=float(price),
                    title=str(l.get('title', ''))[:500],
                    location=str(l.get('location', ''))[:200],
                    seller_name=l.get('seller_name'),
                    is_active=True,
                    first_seen=datetime.now(), last_seen=datetime.now(),
                )
                db.add(v)
                saved += 1
            db.commit()

        results['leilosoc'] = f"{len(le_listings)} found, {saved} new"
        logger.info(f"Leilosoc: {len(le_listings)} found, {saved} saved")
    except Exception as e:
        results['leilosoc'] = f"ERROR: {e}"
        logger.error(f"Leilosoc failed: {e}")

    elapsed = time.time() - start
    logger.info(f"Scraping done in {elapsed:.1f}s")
    return results


def train_model():
    """Train XGBoost model on current data."""
    import numpy as np
    import xgboost as xgb
    from joblib import dump
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import r2_score, mean_absolute_error, mean_absolute_percentage_error
    from core.settings import settings
    from valuation.feature_store import FeatureStore
    from database.db import SessionLocal
    from database.models import Vehicle, VehicleType
    import pandas as pd

    logger.info("Loading training data...")
    db = SessionLocal()
    rows = db.query(Vehicle).filter(
        Vehicle.vehicle_type == VehicleType('carros'),
        Vehicle.price > 1000, Vehicle.price < 100000,
        Vehicle.year.isnot(None),
        Vehicle.km.isnot(None), Vehicle.km > 0, Vehicle.km <= 300000,
    ).all()

    records = [{
        'year': v.year, 'km': v.km or 0, 'horsepower': v.horsepower or 0,
        'engine_size': v.engine_size or 0, 'doors': v.doors or 4,
        'brand': v.brand or 'Unknown', 'model': v.model or '', 'price': v.price,
        'fuel_type': v.fuel_type.value if v.fuel_type else 'unknown',
        'transmission': v.transmission.value if v.transmission else 'unknown',
        'location': v.location or '',
        'source': v.source.value if v.source else 'OLX',
    } for v in rows]
    db.close()

    df = pd.DataFrame(records)
    logger.info(f"Training on {len(df)} samples")

    fs = FeatureStore()
    fs.build_brand_index(df['brand'].dropna().tolist())
    fs.build_model_index(df['model'].dropna().tolist())

    features_list = [fs.compute_features(row.to_dict()) for _, row in df.iterrows()]

    feature_cols = [
        'year', 'km', 'horsepower', 'engine_size', 'doors',
        'age', 'km_per_year', 'fuel_type', 'transmission', 'brand', 'model',
        'district', 'depreciation_factor', 'fuel_premium', 'location_premium',
        'age_group', 'km_category', 'brand_popularity', 'is_auction',
    ]

    X = np.array([[f.get(c, 0.0) for c in feature_cols] for f in features_list])
    y = df['price'].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    tscv = TimeSeriesSplit(n_splits=5)
    cv_r2, cv_mae, cv_mape = [], [], []

    for tr, te in tscv.split(X_scaled):
        m = xgb.XGBRegressor(n_estimators=500, max_depth=8, learning_rate=0.03,
                              subsample=0.8, colsample_bytree=0.8, random_state=42)
        m.fit(X_scaled[tr], y[tr])
        yp = m.predict(X_scaled[te])
        cv_r2.append(r2_score(y[te], yp))
        cv_mae.append(mean_absolute_error(y[te], yp))
        cv_mape.append(mean_absolute_percentage_error(y[te], yp) * 100)

    avg_r2, avg_mae, avg_mape = np.mean(cv_r2), np.mean(cv_mae), np.mean(cv_mape)
    logger.info(f"CV: R²={avg_r2:.4f}, MAE=€{avg_mae:.0f}, MAPE={avg_mape:.1f}%")

    fm = xgb.XGBRegressor(n_estimators=500, max_depth=8, learning_rate=0.03,
                           subsample=0.8, colsample_bytree=0.8, random_state=42)
    fm.fit(X_scaled, y)

    # Save
    model_dir = Path(settings.models_dir)
    model_dir.mkdir(exist_ok=True)
    fm.save_model(str(model_dir / 'model_carros.json'))
    dump(scaler, str(model_dir / 'scaler_carros.joblib'))
    fs.save_index(model_dir / 'brand_index_carros.json')

    metadata = {
        'model_type': 'xgboost', 'model_path': 'model_carros.json',
        'scaler_path': 'scaler_carros.joblib',
        'brand_index_path': 'brand_index_carros.json',
        'vehicle_type': 'carros', 'feature_names': feature_cols,
        'metrics': {'r2': float(avg_r2), 'mae': float(avg_mae), 'mape_pct': float(avg_mape)},
        'n_samples': len(df), 'trained_at': datetime.now().isoformat(),
    }
    with open(model_dir / 'best_model_carros.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Model saved: R²={avg_r2:.4f}, MAE=€{avg_mae:.0f}")

    # Update valuations
    logger.info("Updating valuations...")
    from valuation.predict import update_vehicle_valuations
    n = update_vehicle_valuations(5000)
    logger.info(f"Updated {n} vehicles")

    return {'r2': avg_r2, 'mae': avg_mae, 'mape': avg_mape, 'n_samples': len(df)}


def show_stats():
    """Show current database statistics."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vehicles WHERE is_active=1")
    total = cur.fetchone()[0]
    cur.execute("SELECT source, COUNT(*) FROM vehicles WHERE is_active=1 GROUP BY source ORDER BY COUNT(*) DESC")
    sources = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM vehicles WHERE estimated_value IS NOT NULL")
    with_val = cur.fetchone()[0]
    conn.close()

    print(f"\n{'='*50}")
    print(f"  VER PRECOS — Database Stats")
    print(f"  Total: {total:,} vehicles | With valuation: {with_val:,}")
    print(f"  Sources:")
    for s, c in sources:
        print(f"    {s:<18} {c:>5}")
    print(f"{'='*50}\n")


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='VER PRECOS Pipeline')
    parser.add_argument('action', nargs='?', default='stats',
                       choices=['scrape', 'train', 'all', 'dashboard', 'stats'])
    args = parser.parse_args()

    if args.action == 'scrape':
        scrape_all()
        show_stats()
    elif args.action == 'train':
        train_model()
        show_stats()
    elif args.action == 'all':
        scrape_all()
        train_model()
        show_stats()
    elif args.action == 'dashboard':
        import os
        os.system('streamlit run dashboard/app.py --server.port 8501')
    else:
        show_stats()
