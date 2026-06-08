"""
Data transformer for processing car listings.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataTransformer:
    """Data transformer for processing and cleaning car listings."""
    
    def __init__(self):
        """Initialize data transformer."""
        self.transformation_rules = {}
        self.transformation_history = []
        
    def clean_price_data(self, df: pd.DataFrame, price_column: str = 'price') -> pd.DataFrame:
        """Clean and standardize price data."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_clean = df.copy()
        
        # Convert to string for processing
        df_clean[price_column] = df_clean[price_column].astype(str)
        
        # Remove currency symbols and clean
        df_clean[price_column] = df_clean[price_column].str.replace(r'[€$]', '', regex=True)
        df_clean[price_column] = df_clean[price_column].str.replace(r'[.,]', '', regex=True)
        df_clean[price_column] = df_clean[price_column].str.replace(r'\s', '', regex=True)
        
        # Convert to numeric
        df_clean[price_column] = pd.to_numeric(df_clean[price_column], errors='coerce')
        
        # Remove invalid prices
        df_clean = df_clean[
            (df_clean[price_column] > 0) & 
            (df_clean[price_column] < 1000000)  # Reasonable upper limit
        ]
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'clean_price_data',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def clean_mileage_data(self, df: pd.DataFrame, mileage_column: str = 'mileage') -> pd.DataFrame:
        """Clean and standardize mileage data."""
        
        if mileage_column not in df.columns:
            logger.warning(f"Mileage column '{mileage_column}' not found")
            return df
        
        df_clean = df.copy()
        
        # Convert to string for processing
        df_clean[mileage_column] = df_clean[mileage_column].astype(str)
        
        # Extract numeric values
        df_clean[mileage_column] = df_clean[mileage_column].str.replace(r'[^\d]', '', regex=True)
        df_clean[mileage_column] = pd.to_numeric(df_clean[mileage_column], errors='coerce')
        
        # Remove invalid mileage
        df_clean = df_clean[
            (df_clean[mileage_column] >= 0) & 
            (df_clean[mileage_column] < 1000000)  # Reasonable upper limit
        ]
        
        # Fill missing mileage with median
        median_mileage = df_clean[mileage_column].median()
        df_clean[mileage_column] = df_clean[mileage_column].fillna(median_mileage)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'clean_mileage_data',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def clean_year_data(self, df: pd.DataFrame, year_column: str = 'year') -> pd.DataFrame:
        """Clean and standardize year data."""
        
        if year_column not in df.columns:
            logger.warning(f"Year column '{year_column}' not found")
            return df
        
        df_clean = df.copy()
        
        # Convert to string for processing
        df_clean[year_column] = df_clean[year_column].astype(str)
        
        # Extract 4-digit years
        df_clean[year_column] = df_clean[year_column].str.extract(r'(\d{4})')
        df_clean[year_column] = pd.to_numeric(df_clean[year_column], errors='coerce')
        
        # Filter valid years
        current_year = datetime.now().year
        df_clean = df_clean[
            (df_clean[year_column] >= 1900) & 
            (df_clean[year_column] <= current_year + 1)  # Allow next year
        ]
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'clean_year_data',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def clean_make_model_data(self, df: pd.DataFrame, make_column: str = 'make', model_column: str = 'model') -> pd.DataFrame:
        """Clean and standardize make and model data."""
        
        df_clean = df.copy()
        
        # Clean make data
        if make_column in df_clean.columns:
            df_clean[make_column] = df_clean[make_column].astype(str).str.strip().str.title()
            df_clean[make_column] = df_clean[make_column].str.replace(r'\s+', ' ', regex=True)
        
        # Clean model data
        if model_column in df_clean.columns:
            df_clean[model_column] = df_clean[model_column].astype(str).str.strip().str.title()
            df_clean[model_column] = df_clean[model_column].str.replace(r'\s+', ' ', regex=True)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'clean_make_model_data',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def standardize_fuel_type(self, df: pd.DataFrame, fuel_column: str = 'fuel_type') -> pd.DataFrame:
        """Standardize fuel type data."""
        
        if fuel_column not in df.columns:
            logger.warning(f"Fuel type column '{fuel_column}' not found")
            return df
        
        df_clean = df.copy()
        
        # Create fuel type mapping
        fuel_mapping = {
            'gasolina': 'Gasoline',
            'gasóleo': 'Diesel',
            'diesel': 'Diesel',
            'elétrico': 'Electric',
            'electric': 'Electric',
            'híbrido': 'Hybrid',
            'hybrid': 'Hybrid',
            'gpl': 'LPG',
            'lpg': 'LPG',
            'gnv': 'CNG',
            'cng': 'CNG'
        }
        
        # Apply mapping
        df_clean[fuel_column] = df_clean[fuel_column].astype(str).str.lower().str.strip()
        df_clean[fuel_column] = df_clean[fuel_column].map(fuel_mapping).fillna('Unknown')
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'standardize_fuel_type',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def standardize_transmission(self, df: pd.DataFrame, transmission_column: str = 'transmission') -> pd.DataFrame:
        """Standardize transmission data."""
        
        if transmission_column not in df.columns:
            logger.warning(f"Transmission column '{transmission_column}' not found")
            return df
        
        df_clean = df.copy()
        
        # Create transmission mapping
        transmission_mapping = {
            'automático': 'Automatic',
            'automatic': 'Automatic',
            'manual': 'Manual',
            'manual': 'Manual',
            'automática': 'Automatic',
            'manual': 'Manual',
            'cvt': 'CVT',
            'tiptronic': 'Tiptronic',
            'dsg': 'DSG'
        }
        
        # Apply mapping
        df_clean[transmission_column] = df_clean[transmission_column].astype(str).str.lower().str.strip()
        df_clean[transmission_column] = df_clean[transmission_column].map(transmission_mapping).fillna('Unknown')
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'standardize_transmission',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def clean_engine_size(self, df: pd.DataFrame, engine_column: str = 'engine_size') -> pd.DataFrame:
        """Clean and standardize engine size data."""
        
        if engine_column not in df.columns:
            logger.warning(f"Engine size column '{engine_column}' not found")
            return df
        
        df_clean = df.copy()
        
        # Extract engine size in liters
        df_clean[engine_column] = df_clean[engine_column].astype(str)
        
        # Extract numeric values (both liters and cc)
        df_clean[engine_column] = df_clean[engine_column].str.extract(r'(\d+\.?\d*)')
        df_clean[engine_column] = pd.to_numeric(df_clean[engine_column], errors='coerce')
        
        # Convert cc to liters (if > 100, assume cc)
        df_clean[engine_column] = df_clean[engine_column].apply(
            lambda x: x / 1000 if x > 100 else x
        )
        
        # Filter valid engine sizes
        df_clean = df_clean[
            (df_clean[engine_column] >= 0.5) & 
            (df_clean[engine_column] <= 10.0)
        ]
        
        # Fill missing with median
        median_engine = df_clean[engine_column].median()
        df_clean[engine_column] = df_clean[engine_column].fillna(median_engine)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'clean_engine_size',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def clean_location_data(self, df: pd.DataFrame, location_column: str = 'location') -> pd.DataFrame:
        """Clean and standardize location data."""
        
        if location_column not in df.columns:
            logger.warning(f"Location column '{location_column}' not found")
            return df
        
        df_clean = df.copy()
        
        # Clean location data
        df_clean[location_column] = df_clean[location_column].astype(str).str.strip().str.title()
        df_clean[location_column] = df_clean[location_column].str.replace(r'\s+', ' ', regex=True)
        
        # Standardize common location names
        location_mapping = {
            'Lisboa': 'Lisbon',
            'Porto': 'Oporto',
            'Faro': 'Faro',
            'Coimbra': 'Coimbra'
        }
        
        df_clean[location_column] = df_clean[location_column].replace(location_mapping)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'clean_location_data',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add derived columns for analysis."""
        
        df_clean = df.copy()
        
        # Add car age
        if 'year' in df_clean.columns:
            current_year = datetime.now().year
            df_clean['car_age'] = current_year - df_clean['year']
        
        # Add mileage per year
        if 'mileage' in df_clean.columns and 'car_age' in df_clean.columns:
            df_clean['mileage_per_year'] = df_clean['mileage'] / (df_clean['car_age'] + 1)
        
        # Add price per kilometer
        if 'price' in df_clean.columns and 'mileage' in df_clean.columns:
            df_clean['price_per_km'] = df_clean['price'] / (df_clean['mileage'] + 1)
        
        # Add engine size category
        if 'engine_size' in df_clean.columns:
            df_clean['engine_category'] = pd.cut(
                df_clean['engine_size'],
                bins=[0, 1.0, 1.6, 2.0, 3.0, float('inf')],
                labels=['Small', 'Compact', 'Medium', 'Large', 'Extra Large']
            )
        
        # Add mileage category
        if 'mileage' in df_clean.columns:
            df_clean['mileage_category'] = pd.cut(
                df_clean['mileage'],
                bins=[0, 20000, 50000, 100000, 150000, float('inf')],
                labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
            )
        
        # Add age category
        if 'car_age' in df_clean.columns:
            df_clean['age_category'] = pd.cut(
                df_clean['car_age'],
                bins=[0, 2, 5, 10, 15, float('inf')],
                labels=['New', 'Nearly New', 'Used', 'Old', 'Very Old']
            )
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'add_derived_columns',
            'timestamp': datetime.now().isoformat(),
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def remove_duplicates(self, df: pd.DataFrame, subset: List[str] = None) -> pd.DataFrame:
        """Remove duplicate records."""
        
        if subset is None:
            subset = ['make', 'model', 'year', 'price', 'mileage']
        
        # Filter available columns
        available_subset = [col for col in subset if col in df.columns]
        
        if not available_subset:
            logger.warning("No valid columns for duplicate removal")
            return df
        
        initial_count = len(df)
        df_clean = df.drop_duplicates(subset=available_subset, keep='first')
        final_count = len(df_clean)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'remove_duplicates',
            'timestamp': datetime.now().isoformat(),
            'records_before': initial_count,
            'records_after': final_count,
            'duplicates_removed': initial_count - final_count
        })
        
        return df_clean
    
    def handle_missing_values(self, df: pd.DataFrame, strategy: str = 'median') -> pd.DataFrame:
        """Handle missing values in the dataset."""
        
        df_clean = df.copy()
        
        # Separate numeric and categorical columns
        numeric_columns = df_clean.select_dtypes(include=[np.number]).columns
        categorical_columns = df_clean.select_dtypes(include=['object', 'category']).columns
        
        # Handle numeric missing values
        for col in numeric_columns:
            if df_clean[col].isnull().sum() > 0:
                if strategy == 'median':
                    fill_value = df_clean[col].median()
                elif strategy == 'mean':
                    fill_value = df_clean[col].mean()
                elif strategy == 'mode':
                    fill_value = df_clean[col].mode()[0] if not df_clean[col].mode().empty else 0
                else:
                    fill_value = 0
                
                df_clean[col].fillna(fill_value, inplace=True)
        
        # Handle categorical missing values
        for col in categorical_columns:
            if df_clean[col].isnull().sum() > 0:
                df_clean[col].fillna('Unknown', inplace=True)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'handle_missing_values',
            'timestamp': datetime.now().isoformat(),
            'strategy': strategy,
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def transform_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all transformations to the dataset."""
        
        df_transformed = df.copy()
        
        # Apply all cleaning steps
        transformations = [
            ('clean_price_data', 'price'),
            ('clean_mileage_data', 'mileage'),
            ('clean_year_data', 'year'),
            ('clean_make_model_data', ['make', 'model']),
            ('standardize_fuel_type', 'fuel_type'),
            ('standardize_transmission', 'transmission'),
            ('clean_engine_size', 'engine_size'),
            ('clean_location_data', 'location'),
            ('add_derived_columns', None),
            ('remove_duplicates', None),
            ('handle_missing_values', 'median')
        ]
        
        for transform_name, param in transformations:
            try:
                if param is None:
                    df_transformed = getattr(self, transform_name)(df_transformed)
                elif isinstance(param, list):
                    df_transformed = getattr(self, transform_name)(df_transformed, *param)
                else:
                    df_transformed = getattr(self, transform_name)(df_transformed, param)
                
                logger.info(f"Applied transformation: {transform_name}")
                
            except Exception as e:
                logger.error(f"Error in transformation {transform_name}: {e}")
                continue
        
        return df_transformed
    
    def get_transformation_summary(self) -> Dict[str, Any]:
        """Get summary of all transformations applied."""
        
        return {
            'total_transformations': len(self.transformation_history),
            'transformations': self.transformation_history,
            'last_updated': datetime.now().isoformat()
        }
    
    def validate_transformed_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate the transformed data."""
        
        validation_results = {
            'total_records': len(df),
            'missing_values': {},
            'data_types': {},
            'value_ranges': {},
            'validation_passed': True
        }
        
        # Check missing values
        for col in df.columns:
            missing_count = df[col].isnull().sum()
            if missing_count > 0:
                validation_results['missing_values'][col] = missing_count
                validation_results['validation_passed'] = False
        
        # Check data types
        for col in df.columns:
            validation_results['data_types'][col] = str(df[col].dtype)
        
        # Check value ranges for key columns
        key_columns = {
            'price': (0, 1000000),
            'mileage': (0, 500000),
            'year': (1900, datetime.now().year + 1),
            'engine_size': (0.5, 10.0)
        }
        
        for col, (min_val, max_val) in key_columns.items():
            if col in df.columns:
                col_min = df[col].min()
                col_max = df[col].max()
                
                if col_min < min_val or col_max > max_val:
                    validation_results['value_ranges'][col] = {
                        'actual_range': (col_min, col_max),
                        'expected_range': (min_val, max_val),
                        'out_of_range': True
                    }
                    validation_results['validation_passed'] = False
                else:
                    validation_results['value_ranges'][col] = {
                        'actual_range': (col_min, col_max),
                        'expected_range': (min_val, max_val),
                        'out_of_range': False
                    }
        
        return validation_results
