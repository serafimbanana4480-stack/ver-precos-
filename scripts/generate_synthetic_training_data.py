"""
Generate realistic synthetic training data for AutoDeal ML model.
Uses Portuguese market benchmarks (2026) to create ground-truth data.
"""
from __future__ import annotations
import sqlite3
import random
import numpy as np
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# ── Portuguese Market Benchmarks 2026 ──

BRAND_SEGMENTS = {
    'exotic': ['Ferrari', 'Lamborghini', 'Aston Martin', 'McLaren', 'Bugatti', 'Rolls-Royce', 'Bentley'],
    'luxury': ['Porsche', 'Maserati'],
    'premium': ['BMW', 'Mercedes-Benz', 'Audi', 'Lexus', 'Jaguar', 'Land Rover', 'Volvo', 'Tesla', 'MINI'],
    'mainstream': ['Volkswagen', 'Ford', 'Renault', 'Peugeot', 'Citroën', 'Opel', 'Toyota', 'Honda', 
                   'Nissan', 'Hyundai', 'Kia', 'SEAT', 'Skoda', 'Fiat', 'Mitsubishi', 'Suzuki', 
                   'Mazda', 'Subaru', 'Jeep', 'DS', 'MG', 'Smart', 'Alfa Romeo', 'Dacia'],
    'budget': ['Rover', 'Lada'],
}

# Depreciation by segment (% of new value remaining after N years)
DEPRECIATION = {
    'exotic':     {1: 0.88, 2: 0.80, 3: 0.75, 5: 0.68, 8: 0.60, 10: 0.55, 15: 0.50},
    'luxury':     {1: 0.85, 2: 0.78, 3: 0.72, 5: 0.62, 8: 0.52, 10: 0.45, 15: 0.38},
    'premium':    {1: 0.78, 2: 0.68, 3: 0.58, 5: 0.48, 8: 0.38, 10: 0.32, 15: 0.25},
    'mainstream': {1: 0.82, 2: 0.72, 3: 0.62, 5: 0.50, 8: 0.38, 10: 0.30, 15: 0.22},
    'budget':     {1: 0.85, 2: 0.75, 3: 0.65, 5: 0.52, 8: 0.40, 10: 0.30, 15: 0.20},
}

# New car price ranges by segment (EUR)
NEW_PRICE_RANGES = {
    'exotic':     (150000, 400000),
    'luxury':     (80000, 180000),
    'premium':    (35000, 80000),
    'mainstream': (18000, 45000),
    'budget':     (10000, 20000),
}

# Fuel type distribution and market premium
FUEL_TYPES = ['gasolina', 'diesel', 'hibrido', 'eletrico', 'gpl']
FUEL_WEIGHTS = [0.40, 0.25, 0.20, 0.10, 0.05]  # PT market 2026
FUEL_PREMIUM = {
    'gasolina': 0.0,
    'diesel': -0.12,      # ZAL restrictions, stigma
    'hibrido': 0.08,      # Partial IMT exemption
    'eletrico': 0.15,     # Full exemptions, ZAL access
    'gpl': -0.10,         # Niche, restrictions
}

# Transmission
TRANSMISSIONS = ['manual', 'automatico']
TRANS_WEIGHTS = [0.45, 0.55]

# Districts in Portugal
DISTRICTS = ['Lisboa', 'Porto', 'Braga', 'Aveiro', 'Setubal', 'Faro', 'Leiria', 
             'Coimbra', 'Santarem', 'Viseu', 'Madeira', 'Acores']
DISTRICT_PREMIUM = {
    'Lisboa': 1.05, 'Porto': 1.03, 'Braga': 1.02, 'Aveiro': 1.01,
    'Setubal': 0.98, 'Faro': 0.97, 'Leiria': 0.96, 'Coimbra': 0.96,
    'Santarem': 0.95, 'Viseu': 0.94, 'Madeira': 0.92, 'Acores': 0.90,
}

# Popular models by brand
MODELS_BY_BRAND = {
    'BMW': ['Serie 1', 'Serie 3', 'Serie 5', 'X1', 'X3', 'X5'],
    'Mercedes-Benz': ['Classe A', 'Classe C', 'Classe E', 'GLA', 'GLC', 'GLE'],
    'Audi': ['A3', 'A4', 'A6', 'Q3', 'Q5', 'Q7'],
    'Volkswagen': ['Golf', 'Polo', 'Tiguan', 'Passat', 'T-Roc'],
    'Renault': ['Clio', 'Captur', 'Megane', 'Kadjar', 'Duster'],
    'Peugeot': ['208', '308', '3008', '5008', '2008'],
    'Ford': ['Focus', 'Fiesta', 'Kuga', 'Puma', 'Mondeo'],
    'Toyota': ['Yaris', 'Corolla', 'C-HR', 'RAV4', 'Auris'],
    'Honda': ['Civic', 'Jazz', 'CR-V', 'HR-V'],
    'Nissan': ['Qashqai', 'Juke', 'Micra', 'X-Trail'],
    'Hyundai': ['i30', 'Tucson', 'Kona', 'i20'],
    'Kia': ['Ceed', 'Sportage', 'Stonic', 'Picanto'],
    'SEAT': ['Ibiza', 'Leon', 'Ateca', 'Arona'],
    'Skoda': ['Octavia', 'Fabia', 'Karoq', 'Kodiaq'],
    'Fiat': ['500', 'Panda', 'Tipo', '500X'],
    'Opel': ['Corsa', 'Astra', 'Mokka', 'Crossland'],
    'Citroën': ['C3', 'C4', 'C5 Aircross', 'Berlingo'],
    'Volvo': ['XC40', 'XC60', 'V40', 'S60'],
    'Dacia': ['Sandero', 'Duster', 'Logan', 'Jogger'],
    'MINI': ['Cooper', 'Countryman', 'Clubman'],
    'Tesla': ['Model 3', 'Model Y'],
    'Porsche': ['911', 'Cayenne', 'Macan', 'Panamera'],
}


def get_segment(brand: str) -> str:
    for segment, brands in BRAND_SEGMENTS.items():
        if brand in brands:
            return segment
    return 'mainstream'


def get_depreciation_factor(segment: str, age: int) -> float:
    """Get depreciation factor for segment and age."""
    dep = DEPRECIATION.get(segment, DEPRECIATION['mainstream'])
    ages = sorted(dep.keys())
    if age <= 0:
        return 1.0
    for i, a in enumerate(ages):
        if age <= a:
            if i == 0:
                return dep[a]
            prev_age = ages[i - 1]
            prev_val = dep[prev_age]
            curr_val = dep[a]
            # Linear interpolation
            ratio = (age - prev_age) / (a - prev_age)
            return prev_val - (prev_val - curr_val) * ratio
    # Beyond max age
    max_age = ages[-1]
    max_val = dep[max_age]
    # Continue declining at ~2% per year
    return max_val * (0.98 ** (age - max_age))


def generate_synthetic_vehicle(vehicle_id: int) -> dict:
    """Generate one realistic synthetic vehicle for training."""
    # Pick brand and segment
    all_brands = []
    for segment, brands in BRAND_SEGMENTS.items():
        # Weight by segment popularity
        weight = {'exotic': 1, 'luxury': 3, 'premium': 20, 'mainstream': 60, 'budget': 5}[segment]
        all_brands.extend([(b, segment) for b in brands] * weight)
    
    brand, segment = random.choice(all_brands)
    
    # Pick model
    models = MODELS_BY_BRAND.get(brand, ['Standard'])
    model = random.choice(models)
    
    # Year: weighted towards recent
    current_year = datetime.now().year
    age_weights = []
    for age in range(0, 21):
        if age == 0:
            w = 5
        elif age <= 3:
            w = 15
        elif age <= 8:
            w = 20
        elif age <= 15:
            w = 10
        else:
            w = 2
        age_weights.append(w)
    
    age = random.choices(range(21), weights=age_weights)[0]
    year = current_year - age
    
    # New price base
    new_min, new_max = NEW_PRICE_RANGES[segment]
    new_price = random.uniform(new_min, new_max)
    
    # Apply depreciation
    dep_factor = get_depreciation_factor(segment, age)
    base_price = new_price * dep_factor
    
    # Fuel type
    fuel = random.choices(FUEL_TYPES, weights=FUEL_WEIGHTS)[0]
    fuel_adj = FUEL_PREMIUM[fuel]
    
    # KM: realistic for age
    km_per_year = random.gauss(15000, 5000)  # mean 15k, std 5k
    km_per_year = max(2000, min(50000, km_per_year))
    km = int(km_per_year * max(age, 0.5))
    
    # KM adjustment: low KM = premium, high KM = discount
    expected_km = age * 15000 if age > 0 else 7500
    km_ratio = km / max(expected_km, 1)
    if km_ratio < 0.7:
        km_adj = 1.05
    elif km_ratio > 1.5:
        km_adj = 0.90
    else:
        km_adj = 1.0
    
    # Transmission
    transmission = random.choices(TRANSMISSIONS, weights=TRANS_WEIGHTS)[0]
    trans_adj = 1.05 if transmission == 'automatico' else 1.0
    
    # District
    district = random.choice(DISTRICTS)
    loc_adj = DISTRICT_PREMIUM.get(district, 1.0)
    
    # Engine size and HP based on segment
    if segment == 'exotic':
        engine_size = random.randint(3500, 6500)
        hp = random.randint(450, 900)
    elif segment == 'luxury':
        engine_size = random.randint(2500, 4500)
        hp = random.randint(300, 550)
    elif segment == 'premium':
        engine_size = random.randint(1500, 3500)
        hp = random.randint(120, 350)
    else:
        engine_size = random.randint(1000, 2500)
        hp = random.randint(75, 200)
    
    # Add noise to price (±8%)
    noise = random.gauss(1.0, 0.08)
    
    # Final price calculation
    final_price = base_price * (1 + fuel_adj) * km_adj * trans_adj * loc_adj * noise
    final_price = max(500, final_price)  # Minimum realistic price
    
    return {
        'source_id': f'synth_{vehicle_id:06d}',
        'source': 'SYNTHETIC',
        'brand': brand,
        'model': model,
        'year': year,
        'km': km,
        'price': round(final_price, 2),
        'fuel_type': fuel,
        'transmission': transmission,
        'district': district,
        'engine_size': engine_size,
        'horsepower': hp,
        'vehicle_type': 'carros',
        'age': age,
    }


def generate_training_dataset(n_samples: int = 5000, db_path: str = 'autodeal.db') -> int:
    """Generate synthetic training data and save to database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if auction_transactions table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auction_transactions'")
    if not cursor.fetchone():
        logger.error("auction_transactions table does not exist!")
        conn.close()
        return 0
    
    inserted = 0
    for i in range(n_samples):
        vehicle = generate_synthetic_vehicle(i)
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO auction_transactions (
                    source, source_id, url, brand, model, year, km, 
                    adjudication_price, fuel_type, transmission, location,
                    engine_size, horsepower, vehicle_type, auction_type,
                    title, description, scraped_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'SYNTHETIC', vehicle['source_id'], f"https://synthetic.autodeal.pt/{vehicle['source_id']}",
                vehicle['brand'], vehicle['model'],
                vehicle['year'], vehicle['km'], vehicle['price'],
                vehicle['fuel_type'], vehicle['transmission'], vehicle['district'],
                vehicle['engine_size'], vehicle['horsepower'], vehicle['vehicle_type'],
                'synthetic_benchmark', 
                f"{vehicle['brand']} {vehicle['model']} {vehicle['year']}",
                f"Synthetic vehicle for ML training. Segment: {get_segment(vehicle['brand'])}, "
                f"Age: {vehicle['age']}y, KM: {vehicle['km']}, Fuel: {vehicle['fuel_type']}",
                datetime.now().isoformat(), 1
            ))
            inserted += 1
        except Exception as e:
            logger.warning(f"Error inserting synthetic vehicle {i}: {e}")
    
    conn.commit()
    
    # Stats
    cursor.execute('SELECT COUNT(*) FROM auction_transactions WHERE is_active = 1')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT source, COUNT(*) FROM auction_transactions WHERE is_active = 1 GROUP BY source')
    by_source = cursor.fetchall()
    
    conn.close()
    
    logger.info(f"Inserted {inserted} synthetic auction transactions")
    logger.info(f"Total auction transactions: {total}")
    for src, cnt in by_source:
        logger.info(f"  {src}: {cnt}")
    
    return inserted


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    n = generate_training_dataset(n_samples=5000)
    print(f"\nGenerated {n} synthetic training samples")
