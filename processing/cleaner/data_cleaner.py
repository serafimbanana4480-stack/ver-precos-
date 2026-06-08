"""
Data cleaner for comprehensive data cleaning.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataCleaner:
    """Data cleaner for comprehensive data cleaning operations."""
    
    def __init__(self):
        """Initialize data cleaner."""
        self.cleaning_rules = {}
        self.cleaning_history = []
        self.cleaned_data = None
        
    def clean_numeric_data(self, df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
        """Clean numeric data columns."""
        
        df_clean = df.copy()
        
        if columns is None:
            columns = df_clean.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df_clean.columns:
                continue
                
            # Remove non-numeric characters
            df_clean[col] = df_clean[col].astype(str).str.replace(r'[^\d.-]', '', regex=True)
            
            # Convert to numeric
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            
            # Handle negative values where inappropriate
            if col in ['price', 'mileage', 'year', 'engine_size']:
                df_clean[col] = df_clean[col].abs()
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'clean_numeric_data',
            'timestamp': datetime.now().isoformat(),
            'columns_cleaned': columns
        })
        
        return df_clean
    
    def clean_text_data(self, df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
        """Clean text data columns."""
        
        df_clean = df.copy()
        
        if columns is None:
            columns = df_clean.select_dtypes(include=['object']).columns.tolist()
        
        for col in columns:
            if col not in df_clean.columns:
                continue
                
            # Convert to string
            df_clean[col] = df_clean[col].astype(str)
            
            # Remove extra whitespace
            df_clean[col] = df_clean[col].str.strip()
            df_clean[col] = df_clean[col].str.replace(r'\s+', ' ', regex=True)
            
            # Remove special characters but keep important ones
            df_clean[col] = df_clean[col].str.replace(r'[^\w\s\-\.]', ' ', regex=True)
            
            # Title case for proper nouns
            if col in ['make', 'model', 'location']:
                df_clean[col] = df_clean[col].str.title()
            else:
                df_clean[col] = df_clean[col].str.lower()
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'clean_text_data',
            'timestamp': datetime.now().isoformat(),
            'columns_cleaned': columns
        })
        
        return df_clean
    
    def remove_invalid_records(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove invalid records based on business rules."""
        
        df_clean = df.copy()
        initial_count = len(df_clean)
        
        # Remove records with invalid prices
        if 'price' in df_clean.columns:
            df_clean = df_clean[
                (df_clean['price'] > 0) & 
                (df_clean['price'] < 1000000)
            ]
        
        # Remove records with invalid mileage
        if 'mileage' in df_clean.columns:
            df_clean = df_clean[
                (df_clean['mileage'] >= 0) & 
                (df_clean['mileage'] < 1000000)
            ]
        
        # Remove records with invalid years
        if 'year' in df_clean.columns:
            current_year = datetime.now().year
            df_clean = df_clean[
                (df_clean['year'] >= 1900) & 
                (df_clean['year'] <= current_year + 1)
            ]
        
        # Remove records with invalid engine sizes
        if 'engine_size' in df_clean.columns:
            df_clean = df_clean[
                (df_clean['engine_size'] >= 0.5) & 
                (df_clean['engine_size'] <= 10.0)
            ]
        
        # Remove records with empty critical fields
        critical_fields = ['make', 'model', 'price']
        available_critical = [field for field in critical_fields if field in df_clean.columns]
        
        if available_critical:
            df_clean = df_clean.dropna(subset=available_critical)
        
        final_count = len(df_clean)
        records_removed = initial_count - final_count
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'remove_invalid_records',
            'timestamp': datetime.now().isoformat(),
            'records_before': initial_count,
            'records_after': final_count,
            'records_removed': records_removed
        })
        
        return df_clean
    
    def handle_missing_values(self, df: pd.DataFrame, strategy: str = 'smart') -> pd.DataFrame:
        """Handle missing values with various strategies."""
        
        df_clean = df.copy()
        
        numeric_columns = df_clean.select_dtypes(include=[np.number]).columns
        categorical_columns = df_clean.select_dtypes(include=['object']).columns
        
        if strategy == 'smart':
            # Smart strategy based on column type and data distribution
            for col in numeric_columns:
                if df_clean[col].isnull().sum() > 0:
                    # Use median for skewed data, mean for normal distribution
                    skewness = df_clean[col].skew()
                    if abs(skewness) > 1:
                        fill_value = df_clean[col].median()
                    else:
                        fill_value = df_clean[col].mean()
                    
                    df_clean[col].fillna(fill_value, inplace=True)
            
            for col in categorical_columns:
                if df_clean[col].isnull().sum() > 0:
                    # Use mode for categorical data
                    mode_value = df_clean[col].mode()[0] if not df_clean[col].mode().empty else 'Unknown'
                    df_clean[col].fillna(mode_value, inplace=True)
        
        elif strategy == 'drop':
            # Drop rows with missing values
            df_clean = df_clean.dropna()
        
        elif strategy == 'fill_zero':
            # Fill missing values with zero
            for col in numeric_columns:
                df_clean[col].fillna(0, inplace=True)
            
            for col in categorical_columns:
                df_clean[col].fillna('Unknown', inplace=True)
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'handle_missing_values',
            'timestamp': datetime.now().isoformat(),
            'strategy': strategy,
            'records_before': len(df),
            'records_after': len(df_clean)
        })
        
        return df_clean
    
    def standardize_categorical_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize categorical data values."""
        
        df_clean = df.copy()
        
        # Standardize fuel types
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
        
        if 'fuel_type' in df_clean.columns:
            df_clean['fuel_type'] = df_clean['fuel_type'].astype(str).str.lower().str.strip()
            df_clean['fuel_type'] = df_clean['fuel_type'].map(fuel_mapping).fillna('Unknown')
        
        # Standardize transmission
        transmission_mapping = {
            'automático': 'Automatic',
            'automatic': 'Automatic',
            'manual': 'Manual',
            'manual': 'Manual',
            'cvt': 'CVT',
            'tiptronic': 'Tiptronic',
            'dsg': 'DSG'
        }
        
        if 'transmission' in df_clean.columns:
            df_clean['transmission'] = df_clean['transmission'].astype(str).str.lower().str.strip()
            df_clean['transmission'] = df_clean['transmission'].map(transmission_mapping).fillna('Unknown')
        
        # Standardize condition
        condition_mapping = {
            'excelente': 'Excellent',
            'perfeito': 'Excellent',
            'ótimo': 'Good',
            'bom': 'Good',
            'regular': 'Fair',
            'aceitável': 'Fair',
            'ruim': 'Poor',
            'mau': 'Poor'
        }
        
        if 'condition' in df_clean.columns:
            df_clean['condition'] = df_clean['condition'].astype(str).str.lower().str.strip()
            df_clean['condition'] = df_clean['condition'].map(condition_mapping).fillna('Unknown')
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'standardize_categorical_data',
            'timestamp': datetime.now().isoformat(),
            'standardized_columns': ['fuel_type', 'transmission', 'condition']
        })
        
        return df_clean
    
    def remove_outliers(self, df: pd.DataFrame, method: str = 'iqr', columns: List[str] = None) -> pd.DataFrame:
        """Remove outliers from the dataset."""
        
        df_clean = df.copy()
        initial_count = len(df_clean)
        
        if columns is None:
            columns = ['price', 'mileage']
        
        # Filter available columns
        available_columns = [col for col in columns if col in df_clean.columns]
        
        for col in available_columns:
            if method == 'iqr':
                Q1 = df_clean[col].quantile(0.25)
                Q3 = df_clean[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                df_clean = df_clean[(df_clean[col] >= lower_bound) & (df_clean[col] <= upper_bound)]
            
            elif method == 'zscore':
                z_scores = np.abs((df_clean[col] - df_clean[col].mean()) / df_clean[col].std())
                df_clean = df_clean[z_scores < 3]
            
            elif method == 'modified_zscore':
                median = df_clean[col].median()
                mad = np.median(np.abs(df_clean[col] - median))
                modified_z_scores = 0.6745 * (df_clean[col] - median) / (mad + 1e-8)
                df_clean = df_clean[np.abs(modified_z_scores) < 3.5]
        
        final_count = len(df_clean)
        outliers_removed = initial_count - final_count
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'remove_outliers',
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'columns_processed': available_columns,
            'records_before': initial_count,
            'records_after': final_count,
            'outliers_removed': outliers_removed
        })
        
        return df_clean
    
    def validate_data_consistency(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate data consistency and fix inconsistencies."""
        
        df_clean = df.copy()
        
        # Validate year vs car age
        if 'year' in df_clean.columns:
            current_year = datetime.now().year
            df_clean['car_age'] = current_year - df_clean['year']
            
            # Fix impossible ages
            df_clean.loc[df_clean['car_age'] < 0, 'year'] = current_year
            df_clean.loc[df_clean['car_age'] > 50, 'year'] = current_year - 50
        
        # Validate mileage vs age
        if 'mileage' in df_clean.columns and 'car_age' in df_clean.columns:
            # Assume maximum 30,000 km per year
            max_reasonable_mileage = df_clean['car_age'] * 30000
            
            # Fix unreasonable mileage
            df_clean.loc[df_clean['mileage'] > max_reasonable_mileage, 'mileage'] = max_reasonable_mileage
        
        # Validate price vs age
        if 'price' in df_clean.columns and 'car_age' in df_clean.columns:
            # Very old cars shouldn't be too expensive
            max_reasonable_price_old = 50000  # Maximum price for cars > 20 years
            df_clean.loc[(df_clean['car_age'] > 20) & (df_clean['price'] > max_reasonable_price_old), 'price'] = max_reasonable_price_old
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'validate_data_consistency',
            'timestamp': datetime.now().isoformat(),
            'validations_performed': ['year_age', 'mileage_age', 'price_age']
        })
        
        return df_clean
    
    def deduplicate_data(self, df: pd.DataFrame, subset: List[str] = None) -> pd.DataFrame:
        """Remove duplicate records."""
        
        df_clean = df.copy()
        initial_count = len(df_clean)
        
        if subset is None:
            subset = ['make', 'model', 'year', 'price', 'mileage']
        
        # Filter available columns
        available_subset = [col for col in subset if col in df_clean.columns]
        
        if available_subset:
            df_clean = df_clean.drop_duplicates(subset=available_subset, keep='first')
        
        final_count = len(df_clean)
        duplicates_removed = initial_count - final_count
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'deduplicate_data',
            'timestamp': datetime.now().isoformat(),
            'subset_used': available_subset,
            'records_before': initial_count,
            'records_after': final_count,
            'duplicates_removed': duplicates_removed
        })
        
        return df_clean
    
    def clean_all(self, df: pd.DataFrame, aggressive: bool = False) -> pd.DataFrame:
        """Apply all cleaning operations."""
        
        df_clean = df.copy()
        
        # Apply all cleaning steps
        cleaning_steps = [
            ('clean_numeric_data', None),
            ('clean_text_data', None),
            ('remove_invalid_records', None),
            ('standardize_categorical_data', None),
            ('validate_data_consistency', None),
            ('deduplicate_data', None),
            ('handle_missing_values', 'smart'),
            ('remove_outliers', 'iqr' if not aggressive else 'zscore')
        ]
        
        for step_name, params in cleaning_steps:
            try:
                if params is None:
                    df_clean = getattr(self, step_name)(df_clean)
                elif isinstance(params, list):
                    df_clean = getattr(self, step_name)(df_clean, *params)
                else:
                    df_clean = getattr(self, step_name)(df_clean, params)
                
                logger.info(f"Applied cleaning step: {step_name}")
                
            except Exception as e:
                logger.error(f"Error in cleaning step {step_name}: {e}")
                continue
        
        self.cleaned_data = df_clean
        return df_clean
    
    def get_cleaning_report(self) -> Dict[str, Any]:
        """Get comprehensive cleaning report."""
        
        if self.cleaned_data is None:
            return {'error': 'No data has been cleaned yet'}
        
        report = {
            'cleaning_summary': {
                'total_operations': len(self.cleaning_history),
                'final_record_count': len(self.cleaned_data),
                'cleaning_history': self.cleaning_history
            },
            'data_quality': {
                'missing_values': self.cleaned_data.isnull().sum().to_dict(),
                'data_types': self.cleaned_data.dtypes.to_dict(),
                'duplicate_rows': self.cleaned_data.duplicated().sum()
            },
            'data_statistics': {
                'numeric_summary': self.cleaned_data.describe().to_dict(),
                'categorical_summary': {}
            }
        }
        
        # Add categorical summary
        categorical_columns = self.cleaned_data.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            report['data_statistics']['categorical_summary'][col] = {
                'unique_values': self.cleaned_data[col].nunique(),
                'most_common': self.cleaned_data[col].mode()[0] if not self.cleaned_data[col].mode().empty else None
            }
        
        return report
    
    def export_cleaned_data(self, filepath: str, format: str = 'csv') -> bool:
        """Export cleaned data to file."""
        
        if self.cleaned_data is None:
            logger.error("No cleaned data to export")
            return False
        
        try:
            if format.lower() == 'csv':
                self.cleaned_data.to_csv(filepath, index=False)
            elif format.lower() == 'json':
                self.cleaned_data.to_json(filepath, orient='records', indent=2)
            elif format.lower() == 'excel':
                self.cleaned_data.to_excel(filepath, index=False)
            else:
                logger.error(f"Unsupported format: {format}")
                return False
            
            logger.info(f"Cleaned data exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return False
