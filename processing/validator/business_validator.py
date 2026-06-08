"""
Business validator for business rule validation.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BusinessValidator:
    """Business validator for business rule validation."""
    
    def __init__(self):
        """Initialize business validator."""
        self.business_rules = {}
        self.validation_history = []
        self._initialize_business_rules()
    
    def _initialize_business_rules(self):
        """Initialize business validation rules."""
        
        self.business_rules = {
            'price_rules': {
                'min_price': 100,
                'max_price': 1000000,
                'price_mileage_ratio_max': 0.1,  # Price per km should not exceed 0.1€
                'price_age_ratio_max': 50000,    # Price per year should not exceed 50,000€
                'price_engine_ratio_max': 100000, # Price per liter should not exceed 100,000€
                'luxury_threshold': 50000,        # Price above this is considered luxury
                'budget_threshold': 5000          # Price below this is considered budget
            },
            'mileage_rules': {
                'max_mileage': 500000,
                'max_mileage_per_year': 30000,
                'low_mileage_threshold': 20000,
                'high_mileage_threshold': 150000
            },
            'age_rules': {
                'max_age': 50,
                'new_car_threshold': 2,
                'old_car_threshold': 15,
                'vintage_threshold': 30
            },
            'engine_rules': {
                'min_engine_size': 0.5,
                'max_engine_size': 10.0,
                'small_engine_threshold': 1.5,
                'large_engine_threshold': 3.0
            },
            'market_rules': {
                'max_price_variance': 0.5,  # 50% variance from market average
                'min_listings_for_analysis': 5,
                'price_drop_threshold': 0.3,  # 30% price drop considered suspicious
                'duplicate_listing_threshold': 7  # Same listing within 7 days is duplicate
            }
        }
    
    def validate_price_business_rules(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate price-related business rules."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'rule_violations': {}
        }
        
        if 'price' not in df.columns:
            validation_results['errors'].append("Price column not found")
            validation_results['valid'] = False
            return validation_results
        
        price_rules = self.business_rules['price_rules']
        
        # Check price range
        invalid_prices = df[(df['price'] < price_rules['min_price']) | 
                           (df['price'] > price_rules['max_price'])]
        
        if not invalid_prices.empty:
            validation_results['errors'].append(f"Found {len(invalid_prices)} records with invalid price range")
            validation_results['rule_violations']['invalid_price_range'] = len(invalid_prices)
            validation_results['valid'] = False
        
        # Check price-mileage ratio
        if 'mileage' in df.columns:
            df_temp = df.copy()
            df_temp['price_per_km'] = df_temp['price'] / (df_temp['mileage'] + 1)
            high_ratio = df_temp[df_temp['price_per_km'] > price_rules['price_mileage_ratio_max']]
            
            if not high_ratio.empty:
                validation_results['warnings'].append(f"Found {len(high_ratio)} records with unusually high price per kilometer")
                validation_results['rule_violations']['high_price_per_km'] = len(high_ratio)
        
        # Check price-age ratio
        if 'year' in df.columns:
            df_temp = df.copy()
            df_temp['car_age'] = datetime.now().year - df_temp['year']
            df_temp['price_per_year'] = df_temp['price'] / (df_temp['car_age'] + 1)
            high_age_ratio = df_temp[df_temp['price_per_year'] > price_rules['price_age_ratio_max']]
            
            if not high_age_ratio.empty:
                validation_results['warnings'].append(f"Found {len(high_age_ratio)} records with unusually high price per year")
                validation_results['rule_violations']['high_price_per_year'] = len(high_age_ratio)
        
        # Check price-engine ratio
        if 'engine_size' in df.columns:
            df_temp = df.copy()
            df_temp['price_per_liter'] = df_temp['price'] / df_temp['engine_size']
            high_engine_ratio = df_temp[df_temp['price_per_liter'] > price_rules['price_engine_ratio_max']]
            
            if not high_engine_ratio.empty:
                validation_results['warnings'].append(f"Found {len(high_engine_ratio)} records with unusually high price per liter")
                validation_results['rule_violations']['high_price_per_liter'] = len(high_engine_ratio)
        
        # Categorize prices
        luxury_cars = df[df['price'] > price_rules['luxury_threshold']]
        budget_cars = df[df['price'] < price_rules['budget_threshold']]
        
        validation_results['price_categories'] = {
            'luxury_count': len(luxury_cars),
            'budget_count': len(budget_cars),
            'regular_count': len(df) - len(luxury_cars) - len(budget_cars)
        }
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_price_business_rules',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'rule_violations': validation_results['rule_violations']
        })
        
        return validation_results
    
    def validate_mileage_business_rules(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate mileage-related business rules."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'rule_violations': {}
        }
        
        if 'mileage' not in df.columns:
            validation_results['errors'].append("Mileage column not found")
            validation_results['valid'] = False
            return validation_results
        
        mileage_rules = self.business_rules['mileage_rules']
        
        # Check mileage range
        invalid_mileage = df[(df['mileage'] < 0) | (df['mileage'] > mileage_rules['max_mileage'])]
        
        if not invalid_mileage.empty:
            validation_results['errors'].append(f"Found {len(invalid_mileage)} records with invalid mileage")
            validation_results['rule_violations']['invalid_mileage'] = len(invalid_mileage)
            validation_results['valid'] = False
        
        # Check mileage vs age consistency
        if 'year' in df.columns:
            df_temp = df.copy()
            df_temp['car_age'] = datetime.now().year - df_temp['year']
            df_temp['max_reasonable_mileage'] = df_temp['car_age'] * mileage_rules['max_mileage_per_year']
            
            unreasonable_mileage = df_temp[df_temp['mileage'] > df_temp['max_reasonable_mileage']]
            
            if not unreasonable_mileage.empty:
                validation_results['warnings'].append(f"Found {len(unreasonable_mileage)} records with unreasonable mileage for car age")
                validation_results['rule_violations']['unreasonable_mileage'] = len(unreasonable_mileage)
        
        # Categorize mileage
        low_mileage = df[df['mileage'] < mileage_rules['low_mileage_threshold']]
        high_mileage = df[df['mileage'] > mileage_rules['high_mileage_threshold']]
        
        validation_results['mileage_categories'] = {
            'low_mileage_count': len(low_mileage),
            'high_mileage_count': len(high_mileage),
            'normal_mileage_count': len(df) - len(low_mileage) - len(high_mileage)
        }
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_mileage_business_rules',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'rule_violations': validation_results['rule_violations']
        })
        
        return validation_results
    
    def validate_age_business_rules(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate age-related business rules."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'rule_violations': {}
        }
        
        if 'year' not in df.columns:
            validation_results['errors'].append("Year column not found")
            validation_results['valid'] = False
            return validation_results
        
        age_rules = self.business_rules['age_rules']
        current_year = datetime.now().year
        
        # Calculate car age
        df_temp = df.copy()
        df_temp['car_age'] = current_year - df_temp['year']
        
        # Check age range
        invalid_age = df_temp[(df_temp['car_age'] < 0) | (df_temp['car_age'] > age_rules['max_age'])]
        
        if not invalid_age.empty:
            validation_results['errors'].append(f"Found {len(invalid_age)} records with invalid car age")
            validation_results['rule_violations']['invalid_age'] = len(invalid_age)
            validation_results['valid'] = False
        
        # Categorize age
        new_cars = df_temp[df_temp['car_age'] <= age_rules['new_car_threshold']]
        old_cars = df_temp[df_temp['car_age'] >= age_rules['old_car_threshold']]
        vintage_cars = df_temp[df_temp['car_age'] >= age_rules['vintage_threshold']]
        
        validation_results['age_categories'] = {
            'new_car_count': len(new_cars),
            'old_car_count': len(old_cars),
            'vintage_car_count': len(vintage_cars),
            'regular_car_count': len(df) - len(new_cars) - len(vintage_cars)
        }
        
        # Check for future cars
        future_cars = df_temp[df_temp['car_age'] < 0]
        if not future_cars.empty:
            validation_results['warnings'].append(f"Found {len(future_cars)} cars with future years")
            validation_results['rule_violations']['future_cars'] = len(future_cars)
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_age_business_rules',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'rule_violations': validation_results['rule_violations']
        })
        
        return validation_results
    
    def validate_engine_business_rules(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate engine-related business rules."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'rule_violations': {}
        }
        
        if 'engine_size' not in df.columns:
            validation_results['errors'].append("Engine size column not found")
            validation_results['valid'] = False
            return validation_results
        
        engine_rules = self.business_rules['engine_rules']
        
        # Check engine size range
        invalid_engine = df[(df['engine_size'] < engine_rules['min_engine_size']) | 
                          (df['engine_size'] > engine_rules['max_engine_size'])]
        
        if not invalid_engine.empty:
            validation_results['errors'].append(f"Found {len(invalid_engine)} records with invalid engine size")
            validation_results['rule_violations']['invalid_engine_size'] = len(invalid_engine)
            validation_results['valid'] = False
        
        # Categorize engine size
        small_engines = df[df['engine_size'] < engine_rules['small_engine_threshold']]
        large_engines = df[df['engine_size'] > engine_rules['large_engine_threshold']]
        
        validation_results['engine_categories'] = {
            'small_engine_count': len(small_engines),
            'large_engine_count': len(large_engines),
            'medium_engine_count': len(df) - len(small_engines) - len(large_engines)
        }
        
        # Check engine-fuel consistency
        if 'fuel_type' in df.columns:
            # Electric cars should have small or no engine size
            electric_cars = df[df['fuel_type'] == 'Electric']
            electric_with_large_engine = electric_cars[electric_cars['engine_size'] > 2.0]
            
            if not electric_with_large_engine.empty:
                validation_results['warnings'].append(f"Found {len(electric_with_large_engine)} electric cars with large engine sizes")
                validation_results['rule_violations']['electric_large_engine'] = len(electric_with_large_engine)
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_engine_business_rules',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'rule_violations': validation_results['rule_violations']
        })
        
        return validation_results
    
    def validate_market_consistency(self, df: pd.DataFrame, reference_data: pd.DataFrame = None) -> Dict[str, Any]:
        """Validate market consistency rules."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'rule_violations': {}
        }
        
        market_rules = self.business_rules['market_rules']
        
        if reference_data is None:
            validation_results['warnings'].append("No reference data provided for market consistency validation")
            return validation_results
        
        # Check price variance from market
        if 'price' in df.columns and 'make' in df.columns and 'model' in df.columns:
            price_violations = []
            
            for make in df['make'].unique():
                for model in df[df['make'] == make]['model'].unique():
                    # Get market average for this make-model
                    market_data_subset = reference_data[
                        (reference_data['make'] == make) & 
                        (reference_data['model'] == model)
                    ]
                    
                    if len(market_data_subset) >= market_rules['min_listings_for_analysis']:
                        market_avg = market_data_subset['price'].mean()
                        
                        # Check current data against market
                        current_data_subset = df[
                            (df['make'] == make) & 
                            (df['model'] == model)
                        ]
                        
                        for idx, row in current_data_subset.iterrows():
                            price_variance = abs(row['price'] - market_avg) / market_avg
                            
                            if price_variance > market_rules['max_price_variance']:
                                price_violations.append(idx)
            
            if price_violations:
                validation_results['warnings'].append(f"Found {len(price_violations)} records with high price variance from market")
                validation_results['rule_violations']['high_price_variance'] = len(price_violations)
        
        # Check for duplicate listings (same make, model, year, price within time window)
        if 'date_scraped' in df.columns:
            df_temp = df.copy()
            df_temp['date_scraped'] = pd.to_datetime(df_temp['date_scraped'])
            
            # Sort by date
            df_temp = df_temp.sort_values('date_scraped')
            
            # Find potential duplicates
            duplicate_candidates = []
            
            for i in range(len(df_temp)):
                for j in range(i + 1, len(df_temp)):
                    # Check if same make, model, year, and similar price
                    same_make_model = (df_temp.iloc[i]['make'] == df_temp.iloc[j]['make'] and 
                                    df_temp.iloc[i]['model'] == df_temp.iloc[j]['model'] and
                                    df_temp.iloc[i]['year'] == df_temp.iloc[j]['year'])
                    
                    if same_make_model:
                        price_diff = abs(df_temp.iloc[i]['price'] - df_temp.iloc[j]['price']) / df_temp.iloc[i]['price']
                        date_diff = (df_temp.iloc[j]['date_scraped'] - df_temp.iloc[i]['date_scraped']).days
                        
                        if price_diff < 0.1 and date_diff <= market_rules['duplicate_listing_threshold']:
                            duplicate_candidates.append(j)
            
            if duplicate_candidates:
                validation_results['warnings'].append(f"Found {len(duplicate_candidates)} potential duplicate listings")
                validation_results['rule_violations']['potential_duplicates'] = len(duplicate_candidates)
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_market_consistency',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'rule_violations': validation_results['rule_violations']
        })
        
        return validation_results
    
    def validate_business_logic(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate overall business logic."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'business_violations': {}
        }
        
        # Validate price vs condition logic
        if 'price' in df.columns and 'condition' in df.columns:
            # Poor condition cars shouldn't be too expensive
            poor_condition_expensive = df[
                (df['condition'] == 'Poor') & 
                (df['price'] > 30000)
            ]
            
            if not poor_condition_expensive.empty:
                validation_results['warnings'].append(f"Found {len(poor_condition_expensive)} poor condition cars with high prices")
                validation_results['business_violations']['poor_condition_expensive'] = len(poor_condition_expensive)
            
            # Excellent condition cars shouldn't be too cheap
            excellent_condition_cheap = df[
                (df['condition'] == 'Excellent') & 
                (df['price'] < 5000)
            ]
            
            if not excellent_condition_cheap.empty:
                validation_results['warnings'].append(f"Found {len(excellent_condition_cheap)} excellent condition cars with very low prices")
                validation_results['business_violations']['excellent_condition_cheap'] = len(excellent_condition_cheap)
        
        # Validate fuel type vs engine size logic
        if 'fuel_type' in df.columns and 'engine_size' in df.columns:
            # Electric cars typically have smaller engines
            electric_large_engine = df[
                (df['fuel_type'] == 'Electric') & 
                (df['engine_size'] > 3.0)
            ]
            
            if not electric_large_engine.empty:
                validation_results['warnings'].append(f"Found {len(electric_large_engine)} electric cars with large engine sizes")
                validation_results['business_violations']['electric_large_engine'] = len(electric_large_engine)
        
        # Validate transmission vs year logic
        if 'transmission' in df.columns and 'year' in df.columns:
            # Very old cars typically don't have automatic transmission
            old_automatic = df[
                (df['year'] < 1990) & 
                (df['transmission'] == 'Automatic')
            ]
            
            if not old_automatic.empty:
                validation_results['warnings'].append(f"Found {len(old_automatic)} very old cars with automatic transmission")
                validation_results['business_violations']['old_automatic'] = len(old_automatic)
        
        # Validate location vs price logic (if location data available)
        if 'location' in df.columns and 'price' in df.columns:
            # Check for price anomalies by location
            location_stats = df.groupby('location')['price'].agg(['mean', 'std']).reset_index()
            
            for _, row in location_stats.iterrows():
                location = row['location']
                mean_price = row['mean']
                std_price = row['std']
                
                # Find outliers in this location
                location_data = df[df['location'] == location]
                outliers = location_data[
                    (location_data['price'] < mean_price - 2 * std_price) |
                    (location_data['price'] > mean_price + 2 * std_price)
                ]
                
                if not outliers.empty:
                    validation_results['warnings'].append(f"Found {len(outliers)} price outliers in {location}")
                    validation_results['business_violations'][f'price_outliers_{location}'] = len(outliers)
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_business_logic',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'business_violations': validation_results['business_violations']
        })
        
        return validation_results
    
    def validate_all_business_rules(self, df: pd.DataFrame, reference_data: pd.DataFrame = None) -> Dict[str, Any]:
        """Validate all business rules."""
        
        all_results = {
            'overall_valid': True,
            'validation_summary': {},
            'detailed_results': {}
        }
        
        # Run all business validations
        validation_methods = [
            ('price_rules', self.validate_price_business_rules),
            ('mileage_rules', self.validate_mileage_business_rules),
            ('age_rules', self.validate_age_business_rules),
            ('engine_rules', self.validate_engine_business_rules),
            ('market_consistency', lambda x: self.validate_market_consistency(x, reference_data)),
            ('business_logic', self.validate_business_logic)
        ]
        
        for method_name, method_func in validation_methods:
            try:
                result = method_func(df)
                all_results['detailed_results'][method_name] = result
                all_results['validation_summary'][method_name] = result['valid']
                
                if not result['valid']:
                    all_results['overall_valid'] = False
                    
            except Exception as e:
                logger.error(f"Error in business validation method {method_name}: {e}")
                all_results['detailed_results'][method_name] = {
                    'valid': False,
                    'errors': [str(e)]
                }
                all_results['validation_summary'][method_name] = False
                all_results['overall_valid'] = False
        
        # Log comprehensive validation
        self.validation_history.append({
            'operation': 'validate_all_business_rules',
            'timestamp': datetime.now().isoformat(),
            'overall_valid': all_results['overall_valid'],
            'validation_summary': all_results['validation_summary']
        })
        
        return all_results
    
    def generate_business_report(self, df: pd.DataFrame, reference_data: pd.DataFrame = None) -> Dict[str, Any]:
        """Generate comprehensive business validation report."""
        
        validation_results = self.validate_all_business_rules(df, reference_data)
        
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_records': len(df)
            },
            'business_validation_results': validation_results,
            'business_recommendations': self._generate_business_recommendations(validation_results),
            'validation_history': self.validation_history
        }
        
        return report
    
    def _generate_business_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate business recommendations based on validation results."""
        
        recommendations = []
        
        for method_name, result in validation_results['detailed_results'].items():
            if not result['valid']:
                if method_name == 'price_rules':
                    recommendations.append("Review pricing strategy - some prices may be unrealistic")
                elif method_name == 'mileage_rules':
                    recommendations.append("Verify mileage data - some values may be incorrect")
                elif method_name == 'age_rules':
                    recommendations.append("Check car year data - some ages may be invalid")
                elif method_name == 'engine_rules':
                    recommendations.append("Review engine specifications - some values may be incorrect")
                elif method_name == 'market_consistency':
                    recommendations.append("Analyze market positioning - some prices may be out of market range")
                elif method_name == 'business_logic':
                    recommendations.append("Review business logic - some data combinations may be inconsistent")
        
        if validation_results['overall_valid']:
            recommendations.append("Business validation passed - data follows business rules")
        
        return recommendations
    
    def update_business_rules(self, rule_category: str, new_rules: Dict[str, Any]) -> bool:
        """Update business rules."""
        
        try:
            if rule_category in self.business_rules:
                self.business_rules[rule_category].update(new_rules)
                logger.info(f"Updated business rules for {rule_category}")
                return True
            else:
                logger.error(f"Rule category '{rule_category}' not found")
                return False
                
        except Exception as e:
            logger.error(f"Error updating business rules: {e}")
            return False
    
    def get_business_rules_summary(self) -> Dict[str, Any]:
        """Get summary of current business rules."""
        
        return {
            'business_rules': self.business_rules,
            'rule_categories': list(self.business_rules.keys()),
            'last_updated': datetime.now().isoformat()
        }
