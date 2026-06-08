"""
Hybrid Pricing Engine
Combines statistical, comparable clustering, ML (if valid), and AI reasoning
FINAL_PRICE = 40% Statistical + 30% Comparable + 20% ML + 10% AI
"""
from __future__ import annotations
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import sqlite3
import numpy as np

from config import settings
from utils.observability import track_pricing

logger = logging.getLogger(__name__)


class HybridPricingEngine:
    """
    Hybrid pricing engine combining multiple pricing strategies
    
    Weights:
    - 40% Statistical (median of comparables)
    - 30% Comparable clustering (K-means)
    - 20% ML model (ONLY if R² ≥ 0.6)
    - 10% AI reasoning adjustment
    """
    
    def __init__(self, db_path: Optional[str] = None, models_dir: Optional[str] = None):
        # Use config.settings if not provided
        if db_path is None:
            if settings.use_sqlite:
                db_url = settings.database_url
                if db_url.startswith("sqlite:///"):
                    db_path = db_url.replace("sqlite:///", "")
                elif db_url.startswith("sqlite://"):
                    db_path = db_url.replace("sqlite://", "")
                else:
                    db_path = "autodeal.db"
            else:
                db_path = settings.database_url
        
        if models_dir is None:
            models_dir = str(settings.models_dir)
        
        self.db_path = db_path
        self.models_dir = Path(models_dir)
    
    @track_pricing(method='hybrid')
    def calculate_price(self, vehicle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate hybrid price for vehicle
        
        Args:
            vehicle: Vehicle dictionary
            
        Returns:
            Dictionary with pricing components and final price
        """
        try:
            components = {}
            
            # 1. Statistical Pricing (primary driver, now robust)
            statistical_price, comparables_count, comparable_level = self._statistical_pricing(vehicle)
            components['statistical'] = statistical_price
            components['statistical_comparables'] = comparables_count
            components['comparable_level'] = comparable_level
            
            # 2. Comparable Clustering (30%)
            comparable_price, cluster_size = self._comparable_clustering_pricing(vehicle)
            components['comparable'] = comparable_price
            components['comparable_cluster_size'] = cluster_size
            
            # 3. ML Model (20%) - ONLY if valid
            ml_price, ml_confidence, ml_version = self._ml_pricing(vehicle)
            components['ml'] = ml_price
            components['ml_confidence'] = ml_confidence
            components['ml_version'] = ml_version
            
            # 4. AI Reasoning Adjustment (10%)
            ai_adjustment, ai_reason = self._ai_reasoning_adjustment(vehicle)
            components['ai_adjustment'] = ai_adjustment
            components['ai_adjustment_reason'] = ai_reason
            
            insufficient_data = (
                comparables_count < 5
                and (comparable_price is None or cluster_size < 3)
            )
            final_price = self._calculate_hybrid_price(components)
            if insufficient_data and final_price is None:
                pricing_confidence = 'insufficient'
            elif comparables_count < 5 or cluster_size < 3:
                pricing_confidence = 'low'
            else:
                pricing_confidence = 'high' if (ml_price and ml_confidence) else 'medium'

            return {
                'statistical_price': statistical_price,
                'statistical_comparables_count': comparables_count,
                'comparable_price': comparable_price,
                'comparable_cluster_size': cluster_size,
                'ml_price': ml_price,
                'ml_confidence': ml_confidence,
                'ml_model_version': ml_version,
                'ai_adjustment': ai_adjustment,
                'ai_adjustment_reason': ai_reason,
                'final_price': final_price,
                'insufficient_data': insufficient_data and final_price is None,
                'pricing_confidence': pricing_confidence,
                'price_components': components,
                'calculated_at': datetime.utcnow().isoformat(),
                'calculation_method': 'hybrid' if final_price else 'insufficient_data',
            }
            
        except Exception as e:
            logger.error(f"Error calculating hybrid price: {e}")
            # Fallback to statistical only
            statistical_price, _, _ = self._statistical_pricing(vehicle)
            return {
                'statistical_price': statistical_price,
                'statistical_comparables_count': 0,
                'comparable_price': None,
                'comparable_cluster_size': 0,
                'ml_price': None,
                'ml_confidence': None,
                'ml_model_version': None,
                'ai_adjustment': 0.0,
                'ai_adjustment_reason': 'Calculation error - using statistical only',
                'final_price': statistical_price,
                'price_components': {'statistical': statistical_price},
                'calculated_at': datetime.utcnow().isoformat(),
                'calculation_method': 'statistical_fallback'
            }
    
    @track_pricing(method='statistical')
    def _statistical_pricing(self, vehicle: Dict[str, Any]) -> tuple[float, int, str]:
        """
        Robust statistical pricing using quality-aware comparable medians.
        """
        from database.db import get_db_context
        from sqlalchemy import text
        
        brand = vehicle.get('brand', '')
        model = vehicle.get('model', '')
        year = vehicle.get('year')
        if year is None:
            # Try to extract year from title or model
            import re
            title = str(vehicle.get('title', ''))
            year_match = re.search(r'\b(19|20)\d{2}\b', title)
            if year_match:
                year = int(year_match.group(0))
            else:
                year = 2020  # Fallback
            logger.warning(f"Year missing for vehicle, extracted fallback year={year} from title")
        km = vehicle.get('km')
        price = vehicle.get('price', 0) or 0
        vehicle_type = vehicle.get('vehicle_type', '')
        
        if price <= 0:
            return None, 0, "no_price"
        
        bike_clause = "AND vehicle_type IN ('moto', 'scooter', 'quad')" \
            if vehicle_type and vehicle_type.lower() in ["moto", "scooter", "quad"] else \
            "AND (vehicle_type IS NULL OR vehicle_type NOT IN ('moto', 'scooter', 'quad'))"
        
        with get_db_context() as db:
            # Level 1: Same brand + model word + year ±2
            model_word = model.split()[0] if model else ''
            from sqlalchemy import and_, or_
            from database.models import Vehicle as VehicleModel
            
            # Build conditions dynamically (NO SQL injection)
            conditions = [
                VehicleModel.brand == brand,
                VehicleModel.model.like(f"{model_word}%"),
                VehicleModel.year.between(year - 2, year + 2),
                VehicleModel.is_active == True,
                VehicleModel.price > 0,
            ]
            if vehicle_type and vehicle_type.lower() in ["moto", "scooter", "quad"]:
                conditions.append(VehicleModel.vehicle_type.in_(["moto", "scooter", "quad"]))
            else:
                conditions.append(
                    or_(VehicleModel.vehicle_type.is_(None), 
                        VehicleModel.vehicle_type.notin_(["moto", "scooter", "quad"]))
                )
            
            query1 = db.query(VehicleModel.price, VehicleModel.km).filter(and_(*conditions))
            rows = query1.all()
            
            level = "none"
            median_price = None
            
            prices = [r[0] for r in rows]
            if len(rows) >= 3 and self._price_in_iqr(price, prices):
                median_price = float(np.median(prices))
                level = "model_year"
            else:
                # Level 2: Same brand + year ±3
                conditions2 = [
                    VehicleModel.brand == brand,
                    VehicleModel.year.between(year - 3, year + 3),
                    VehicleModel.is_active == True,
                    VehicleModel.price > 0,
                ]
                if vehicle_type and vehicle_type.lower() in ["moto", "scooter", "quad"]:
                    conditions2.append(VehicleModel.vehicle_type.in_(["moto", "scooter", "quad"]))
                else:
                    conditions2.append(
                        or_(VehicleModel.vehicle_type.is_(None), 
                            VehicleModel.vehicle_type.notin_(["moto", "scooter", "quad"]))
                    )
                query2 = db.query(VehicleModel.price, VehicleModel.km).filter(and_(*conditions2))
                rows = query2.all()
                
                if len(rows) >= 3:
                    median_price = float(np.median([r[0] for r in rows]))
                    level = "brand_year"
                else:
                    # Level 3: Same brand (any year)
                    conditions3 = [
                        VehicleModel.brand == brand,
                        VehicleModel.is_active == True,
                        VehicleModel.price > 0,
                    ]
                    if vehicle_type and vehicle_type.lower() in ["moto", "scooter", "quad"]:
                        conditions3.append(VehicleModel.vehicle_type.in_(["moto", "scooter", "quad"]))
                    else:
                        conditions3.append(
                            or_(VehicleModel.vehicle_type.is_(None), 
                                VehicleModel.vehicle_type.notin_(["moto", "scooter", "quad"]))
                        )
                    query3 = db.query(VehicleModel.price, VehicleModel.km).filter(and_(*conditions3))
                    rows = query3.all()
                    
                    if len(rows) >= 3:
                        median_price = float(np.median([r[0] for r in rows]))
                        level = "brand"
        
        # Adjust median for KM difference
        adjusted_median = median_price
        if median_price is not None and km and km > 0:
            comp_kms = [r[1] for r in rows if r[1] and r[1] > 0]
            if comp_kms:
                comp_median_km = float(np.median(comp_kms))
                km_diff_pct = (km - comp_median_km) / max(comp_median_km, 1)
                km_adjustment = max(-0.10, min(0.10, km_diff_pct * -0.20))
                adjusted_median = median_price * (1 + km_adjustment)
        
        # Quality-aware blending
        if level == "model_year":
            est_value = adjusted_median * 0.70 + price * 0.30
        elif level == "brand_year":
            ratio = adjusted_median / price if adjusted_median else 1.0
            ratio = max(0.94, min(1.06, ratio))
            est_value = price * ratio
        elif level == "brand":
            ratio = adjusted_median / price if adjusted_median else 1.0
            ratio = max(0.96, min(1.04, ratio))
            est_value = price * ratio
        else:
            est_value = price * 0.98
        
        # --- Auction Ground Truth Calibration ---
        auction_factor, auction_count, auction_level = self._get_auction_calibration(
            brand, model, year, bike_clause
        )
        if auction_factor < 1.0:
            est_value = est_value * auction_factor
            logger.info(
                f"Auction calibration applied for {brand} {model} ({year}): "
                f"factor={auction_factor:.3f}, level={auction_level}, count={auction_count}"
            )
        
        # --- Segment-based market reality check ---
        # Prevent fantasy pricing from distorting the market
        est_value = self._apply_segment_sanity_check(brand, model, year, price, est_value, vehicle_type)
        
        # Final sanity clamp based on price level
        if price >= 50000:
            low_mult, high_mult = 0.60, 1.30
        elif price >= 30000:
            low_mult, high_mult = 0.55, 1.25
        elif price >= 15000:
            low_mult, high_mult = 0.50, 1.20
        else:
            low_mult, high_mult = 0.45, 1.15
        est_value = max(price * low_mult, min(price * high_mult, est_value))
        
        n_comp = len(rows) if rows else 0
        return round(est_value, 2), n_comp, level
    
    def _apply_segment_sanity_check(
        self, brand: str, model: str, year: int, 
        price: float, est_value: float, vehicle_type: str
    ) -> float:
        """
        Apply segment-based market reality checks to prevent fantasy pricing.
        
        Uses known market segments for Portuguese used car/moto market.
        If a vehicle's price is wildly outside its segment, cap the estimated value.
        """
        import re
        age = max(0, datetime.now().year - year)
        
        # Define segment caps (PT market, EUR)
        # Format: (max_price_for_age_bracket, description)
        segment_caps = {
            # Ultra-luxury / exotic
            'exotic': {
                'brands': ['Ferrari', 'Lamborghini', 'Aston Martin', 'McLaren', 'Bugatti'],
                'caps': [(10, 300000), (20, 180000), (float('inf'), 120000)]
            },
            # Luxury brands
            'luxury': {
                'brands': ['Porsche', 'Maserati', 'Bentley', 'Rolls-Royce'],
                'caps': [(5, 200000), (15, 120000), (float('inf'), 80000)]
            },
            # Premium brands
            'premium': {
                'brands': ['BMW', 'Mercedes-Benz', 'Audi', 'Lexus', 'Jaguar', 'Land Rover', 'Volvo', 'Tesla'],
                'caps': [(3, 120000), (8, 80000), (15, 50000), (float('inf'), 35000)]
            },
            # Mainstream brands
            'mainstream': {
                'brands': ['Volkswagen', 'Ford', 'Renault', 'Peugeot', 'Citroën', 'Opel', 'Toyota', 
                          'Honda', 'Nissan', 'Hyundai', 'Kia', 'Seat', 'Skoda', 'Fiat', 'Mini',
                          'Mitsubishi', 'Suzuki', 'Mazda', 'Subaru', 'Jeep', 'DS', 'MG', 'Smart',
                          'Alfa Romeo', 'Dacia'],
                'caps': [(3, 60000), (8, 40000), (15, 25000), (float('inf'), 15000)]
            },
            # Budget brands
            'budget': {
                'brands': ['Rover', 'Lada', 'Tata', 'Mahindra'],
                'caps': [(10, 15000), (float('inf'), 8000)]
            },
            # Moto brands
            'moto_premium': {
                'brands': ['BMW', 'Ducati', 'Harley-Davidson', 'Triumph', 'Moto Guzzi'],
                'caps': [(3, 30000), (10, 20000), (float('inf'), 12000)],
                'is_moto': True
            },
            'moto_mainstream': {
                'brands': ['Honda', 'Yamaha', 'Kawasaki', 'Suzuki', 'KTM', 'Aprilia', 'Vespa'],
                'caps': [(3, 18000), (10, 12000), (float('inf'), 7000)],
                'is_moto': True
            },
            'moto_budget': {
                'brands': ['CF Moto', 'Benda', 'Jawa', 'Royal Enfield', 'Benelli', 'Sym'],
                'caps': [(3, 12000), (float('inf'), 7000)],
                'is_moto': True
            },
        }
        
        # Determine if this is a moto
        is_moto = vehicle_type and vehicle_type.lower() in ['moto', 'motos', 'scooter', 'quad']
        
        # Find matching segment
        matched_segment = None
        for segment_name, segment_data in segment_caps.items():
            seg_is_moto = segment_data.get('is_moto', False)
            # Skip moto segments for cars and vice versa
            if is_moto and not seg_is_moto:
                continue
            if not is_moto and seg_is_moto:
                continue
            
            if brand in segment_data['brands']:
                matched_segment = segment_data
                break
        
        if matched_segment is None:
            # Unknown brand - apply generic conservative caps
            if is_moto:
                generic_caps = [(3, 15000), (float('inf'), 8000)]
            else:
                generic_caps = [(5, 50000), (15, 30000), (float('inf'), 20000)]
        else:
            generic_caps = matched_segment['caps']
        
        # Find applicable cap based on age
        segment_max = None
        for max_age, max_price in generic_caps:
            if age <= max_age:
                segment_max = max_price
                break
        
        if segment_max is None:
            segment_max = generic_caps[-1][1]
        
        # If price is wildly above segment max, the estimated value should NOT follow
        # the fantasy price. Cap it at segment max with some tolerance.
        if price > segment_max * 1.5:
            # Fantasy pricing detected - cap estimated value
            fantasy_cap = segment_max * 1.3
            logger.warning(
                f"Fantasy pricing detected for {brand} {model} ({year}): "
                f"price={price:.0f}€ vs segment_max={segment_max:.0f}€. "
                f"Capping estimated value at {fantasy_cap:.0f}€"
            )
            est_value = min(est_value, fantasy_cap)
        
        # Also cap extremely low prices (< 20% of segment floor)
        segment_floor = 200 if is_moto else 500
        if price < segment_floor and age < 30:
            logger.warning(
                f"Suspiciously low price for {brand} {model} ({year}): "
                f"price={price:.0f}€. Possible salvage/major issues."
            )
        
        return est_value
    
    def _price_in_iqr(self, price: float, prices: list) -> bool:
        """Check if price is within reasonable range of comparable prices."""
        if len(prices) < 3:
            return True
        q1 = float(np.percentile(prices, 25))
        q3 = float(np.percentile(prices, 75))
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return lower <= price <= upper
    
    def _get_auction_calibration(
        self, brand: str, model: str, year: int, bike_clause: str
    ) -> tuple[float, int, str]:
        """
        Calculate auction-based calibration factor using SQLAlchemy ORM (no SQL injection).
        """
        from database.db import get_db_context
        from database.models import Vehicle as VehicleModel, AuctionTransaction as AuctionModel
        from sqlalchemy import and_, or_
        import numpy as np
        
        model_word = model.split()[0] if model else ''
        
        def _build_vehicle_conditions():
            """Build safe query conditions for vehicles."""
            conditions = [
                VehicleModel.is_active == True,
                VehicleModel.price > 0,
            ]
            return conditions
        
        def _build_auction_conditions():
            """Build safe query conditions for auction transactions."""
            conditions = [
                AuctionModel.is_active == True,
                AuctionModel.adjudication_price > 0,
            ]
            return conditions
        
        def _query_factor(db, brand_val: str, model_pattern: Optional[str], year_start: int, year_end: int, 
                         min_auction_count: int = 2):
            """Helper to compute factor for a given match level using ORM."""
            # Auction query
            auction_conditions = _build_auction_conditions()
            auction_conditions.append(AuctionModel.brand == brand_val)
            if model_pattern:
                auction_conditions.append(AuctionModel.model.like(model_pattern))
            auction_conditions.append(AuctionModel.year.between(year_start, year_end))
            
            auction_rows = db.query(AuctionModel.adjudication_price).filter(and_(*auction_conditions)).all()
            
            if len(auction_rows) < min_auction_count:
                return None, 0
            
            auction_prices = [r[0] for r in auction_rows]
            auction_median = float(np.median(auction_prices))
            
            # Asking-price query
            asking_conditions = _build_vehicle_conditions()
            asking_conditions.append(VehicleModel.brand == brand_val)
            if model_pattern:
                asking_conditions.append(VehicleModel.model.like(model_pattern))
            asking_conditions.append(VehicleModel.year.between(year_start, year_end))
            
            asking_rows = db.query(VehicleModel.price).filter(and_(*asking_conditions)).all()
            if len(asking_rows) < 1:
                return None, len(auction_rows)
            
            asking_prices = [r[0] for r in asking_rows]
            asking_median = float(np.median(asking_prices))
            
            if asking_median <= 0:
                return None, len(auction_rows)
            
            factor = auction_median / asking_median
            factor = max(0.55, min(0.95, factor))
            return factor, len(auction_rows)
        
        with get_db_context() as db:
            # Level 1: Same brand + model word + year ±2
            factor, count = _query_factor(db, brand, f"{model_word}%", year - 2, year + 2)
            if factor is not None:
                return factor, count, "auction_model_year"
            
            # Level 2: Same brand + year ±3
            factor, count = _query_factor(db, brand, None, year - 3, year + 3)
            if factor is not None:
                return factor, count, "auction_brand_year"
            
            # Level 3: Same brand (any year)
            factor, count = _query_factor(db, brand, None, 1900, 2100)
            if factor is not None:
                return factor, count, "auction_brand"
        
        return 1.0, 0, "none"
    
    @track_pricing(method='comparable_clustering')
    def _comparable_clustering_pricing(self, vehicle: Dict[str, Any]) -> tuple[float, int]:
        """
        Comparable clustering pricing — used as secondary validation only.
        """
        from database.db import get_db_context
        from sqlalchemy import text
        brand = vehicle.get('brand', '')
        year = vehicle.get('year')
        if year is None:
            import re
            title = str(vehicle.get('title', ''))
            year_match = re.search(r'\b(19|20)\d{2}\b', title)
            if year_match:
                year = int(year_match.group(0))
            else:
                year = 2020
        price = vehicle.get('price', 0) or 0
        
        if price <= 0:
            return None, 0
        
        min_price = price * 0.7
        max_price = price * 1.3
        
        with get_db_context() as db:
            query = text("""
                SELECT price, year, km
                FROM vehicles
                WHERE brand LIKE :brand_pattern
                AND price BETWEEN :min_p AND :max_p
                AND year BETWEEN :y_start AND :y_end
                AND is_active = 1
                LIMIT 50
            """)
            result = db.execute(query, {
                "brand_pattern": f"%{brand}%",
                "min_p": min_price,
                "max_p": max_price,
                "y_start": year - 3,
                "y_end": year + 3
            })
            cluster = result.fetchall()
        
        if len(cluster) < 3:
            return None, 0
        
        prices = [c[0] for c in cluster]
        cluster_price = float(np.median(prices))
        
        return round(cluster_price, 2), len(cluster)
    
    @track_pricing(method='ml')
    def _ml_pricing(self, vehicle: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[str]]:
        """
        ML model pricing (ONLY if model is valid with R² ≥ 0.6)
        
        Tries multiple model files in order:
        1. metrics_carros.json + xgboost_carros.json (car-specific, no leakage)
        2. model_metrics.json + xgboost_model.json (legacy)
        
        Returns:
            (ml_price, confidence, model_version) or (None, None, None) if model invalid
        """
        # Candidate model sets to try
        candidates = [
            ("metrics_carros.json", "xgboost_carros.json", "carros_v2"),
            ("model_metrics.json", "xgboost_model.json", "legacy"),
        ]
        
        for metrics_name, model_name, version_label in candidates:
            metrics_file = self.models_dir / metrics_name
            model_file = self.models_dir / model_name
            
            if not metrics_file.exists() or not model_file.exists():
                continue
            
            try:
                with open(metrics_file) as f:
                    metrics = json.load(f)
                
                r2 = metrics.get('r2', -1)
                features = metrics.get('features', [])
                
                # Check for target leakage features
                leakage_features = {'price_per_hp', 'price_per_cc', 'depreciation_proxy'}
                if any(feat in features for feat in leakage_features):
                    logger.debug(f"Model {version_label} has target-leakage features, skipping")
                    continue
                
                # Quality gate: R² must be ≥ 0.6
                if r2 < 0.6:
                    logger.debug(f"Model {version_label} R² ({r2}) below threshold (0.6), skipping")
                    continue
                
                # Load and use XGBoost model
                import xgboost as xgb
                from joblib import load as joblib_load
                
                model_path = Path(model_file)
                
                # Only try joblib if the file has a .joblib or .pkl extension
                if model_path.suffix in ('.joblib', '.pkl', '.pickle'):
                    try:
                        model = joblib_load(str(model_file))
                        ml_features = self._prepare_ml_features(vehicle, features)
                        
                        if ml_features is None:
                            continue
                        
                        prediction = model.predict([ml_features])[0]
                        confidence = min(0.95, max(0.5, r2))
                        
                        logger.info(f"ML prediction ({version_label}): {prediction:.2f} (R²={r2:.4f}, confidence={confidence:.2f})")
                        return float(prediction), confidence, version_label
                    except Exception as joblib_err:
                        logger.debug(f"Joblib load failed for {version_label}: {joblib_err}")
                
                # Fallback to xgboost native format
                try:
                    model = xgb.Booster()
                    model.load_model(str(model_file))
                    
                    ml_features = self._prepare_ml_features(vehicle, features)
                    
                    if ml_features is None:
                        continue
                    
                    dmatrix = xgb.DMatrix([ml_features], feature_names=features if features else None)
                    prediction = model.predict(dmatrix)[0]
                    
                    confidence = min(0.95, max(0.5, r2))
                    
                    logger.info(f"ML prediction ({version_label}): {prediction:.2f} (R²={r2:.4f}, confidence={confidence:.2f})")
                    return float(prediction), confidence, version_label
                except Exception as xgb_err:
                    logger.debug(f"XGBoost native load failed for {version_label}: {xgb_err}")
                    continue
                    
            except Exception as e:
                logger.debug(f"Error checking ML model {version_label}: {e}")
                continue
        
        # No valid model found
        logger.debug("No valid ML model available for pricing")
        return None, None, None
    
    def _prepare_ml_features(self, vehicle: Dict[str, Any], feature_names: List[str]) -> Optional[List[float]]:
        """
        Prepare features for ML model from vehicle data using trained label encoders.
        
        Args:
            vehicle: Vehicle data dictionary
            feature_names: List of expected feature names
            
        Returns:
            List of feature values or None if cannot prepare
        """
        if not feature_names:
            logger.warning("No feature names available, cannot prepare ML features")
            return None
        
        try:
            from datetime import datetime
            import numpy as np
            from joblib import load as joblib_load
            
            # Load label encoders if available
            encoders_path = self.models_dir / "encoders_carros.joblib"
            encoders = {}
            if encoders_path.exists():
                try:
                    encoders = joblib_load(str(encoders_path))
                except Exception as e:
                    logger.warning(f"Could not load encoders: {e}")
            
            # Build feature row
            row = {}
            
            # Basic features
            raw_year = vehicle.get("year")
            if raw_year is None:
                import re
                title = str(vehicle.get('title', ''))
                year_match = re.search(r'\b(19|20)\d{2}\b', title)
                raw_year = int(year_match.group(0)) if year_match else 2020
            row["year"] = float(raw_year)
            row["km"] = float(vehicle.get("km", 0) or 0)
            row["horsepower"] = float(vehicle.get("horsepower", 0) or 0)
            row["engine_size"] = float(vehicle.get("engine_size", 0) or 0)
            row["doors"] = float(vehicle.get("doors", 0) or 0)
            row["condition_score"] = float(vehicle.get("condition_score", 5.0) or 5.0)
            
            # Encoded categoricals using trained label encoders
            for col in ["brand", "model", "fuel_type", "transmission", "district"]:
                encoded_col = f"{col}_encoded"
                if encoded_col in feature_names:
                    if col in encoders:
                        val = str(vehicle.get(col, "unknown") or "unknown")
                        le = encoders[col]
                        try:
                            row[encoded_col] = float(le.transform([val])[0])
                        except ValueError:
                            # Unknown category -> use median or 0
                            row[encoded_col] = 0.0
                    else:
                        row[encoded_col] = 0.0
            
            # Derived features (must match training exactly)
            age = float(datetime.now().year - row["year"])
            row["age"] = age
            row["km_per_year"] = row["km"] / max(age, 1)
            row["log_km"] = np.log1p(row["km"])
            row["location_premium"] = 1.0  # Simplified; training used district-based mapping
            row["price_per_hp"] = 0.0  # Cannot compute without target price during prediction
            row["price_per_cc"] = 0.0
            row["depreciation_proxy"] = 0.0
            row["brand_rarity"] = 0.0
            
            # Build feature vector in exact order expected by model
            features = []
            for fname in feature_names:
                features.append(float(row.get(fname, 0.0)))
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing ML features: {e}")
            return None
    
    @track_pricing(method='ai_reasoning')
    def _ai_reasoning_adjustment(self, vehicle: Dict[str, Any]) -> tuple[float, str]:
        """
        AI reasoning adjustment based on LLM and Vision analysis
        
        Adjust price based on:
        - LLM risk score (high risk = price reduction)
        - Vision condition score (poor condition = price reduction)
        """
        ai_risk_score = vehicle.get('ai_risk_score', 5.0)
        condition_score = vehicle.get('condition_score', 6.0)
        
        adjustment = 0.0
        reasons = []
        
        # Adjust based on AI risk
        if ai_risk_score > 7.0:
            adjustment -= 0.10  # 10% reduction for high risk
            reasons.append("High AI risk detected")
        elif ai_risk_score < 3.0:
            adjustment += 0.05  # 5% increase for low risk
            reasons.append("Low AI risk")
        
        # Adjust based on condition
        if condition_score < 5.0:
            adjustment -= 0.10  # 10% reduction for poor condition
            reasons.append("Poor visual condition")
        elif condition_score > 8.0:
            adjustment += 0.05  # 5% increase for excellent condition
            reasons.append("Excellent visual condition")
        
        reason_str = ", ".join(reasons) if reasons else "No AI adjustment needed"
        
        return adjustment, reason_str
    
    def _calculate_hybrid_price(self, components: Dict[str, Any]) -> float:
        """
        Calculate final hybrid price from components.
        
        With robust statistical pricing as the primary driver:
        - 80% Statistical (quality-aware comparable medians)
        - 20% Comparable clustering (sanity check)
        - ML is currently disabled due to training-serving skew (price leakage)
        - AI adjustment applied as small multiplier
        """
        statistical = components.get('statistical')
        comparable = components.get('comparable')
        ai_adjustment = components.get('ai_adjustment', 0.0)

        if statistical is None:
            # No statistical estimate — try comparable only
            if comparable and comparable > 0:
                base_price = float(comparable)
            else:
                return None
        else:
            statistical_val = float(statistical)
            
            if comparable and comparable > 0:
                comparable_val = float(comparable)
                # Weighted blend: statistical dominates
                base_price = statistical_val * 0.80 + comparable_val * 0.20
            else:
                base_price = statistical_val

        if base_price <= 0:
            return None

        final_price = base_price * (1 + ai_adjustment)
        return round(final_price, 2)


# Singleton instance - uses config.settings
pricing_engine = HybridPricingEngine(db_path=None, models_dir=None)
