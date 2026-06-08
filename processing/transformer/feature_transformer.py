"""
Feature transformer for creating and transforming features.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FeatureTransformer:
    """Feature transformer for creating and transforming features."""
    
    def __init__(self):
        """Initialize feature transformer."""
        self.feature_mappings = {}
        self.transformation_history = []
        
    def create_price_features(self, df: pd.DataFrame, price_column: str = 'price') -> pd.DataFrame:
        """Create price-related features."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Price per mileage
        if 'mileage' in df_transformed.columns:
            df_transformed['price_per_mileage'] = df_transformed[price_column] / (df_transformed['mileage'] + 1)
        
        # Price per year
        if 'car_age' in df_transformed.columns:
            df_transformed['price_per_year'] = df_transformed[price_column] / (df_transformed['car_age'] + 1)
        
        # Price log transformation
        df_transformed['price_log'] = np.log1p(df_transformed[price_column])
        
        # Price categories
        price_quantiles = df_transformed[price_column].quantile([0, 0.25, 0.5, 0.75, 1.0])
        df_transformed['price_category'] = pd.cut(
            df_transformed[price_column],
            bins=price_quantiles,
            labels=['Budget', 'Economy', 'Standard', 'Premium'],
            include_lowest=True
        )
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_price_features',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['price_per_mileage', 'price_per_year', 'price_log', 'price_category']
        })
        
        return df_transformed
    
    def create_mileage_features(self, df: pd.DataFrame, mileage_column: str = 'mileage') -> pd.DataFrame:
        """Create mileage-related features."""
        
        if mileage_column not in df.columns:
            logger.warning(f"Mileage column '{mileage_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Mileage log transformation
        df_transformed['mileage_log'] = np.log1p(df_transformed[mileage_column])
        
        # Mileage categories
        mileage_bins = [0, 20000, 50000, 100000, 150000, 200000, float('inf')]
        mileage_labels = ['0-20k', '20k-50k', '50k-100k', '100k-150k', '150k-200k', '200k+']
        
        df_transformed['mileage_category'] = pd.cut(
            df_transformed[mileage_column],
            bins=mileage_bins,
            labels=mileage_labels,
            include_lowest=True
        )
        
        # High mileage indicator
        df_transformed['is_high_mileage'] = (df_transformed[mileage_column] > 150000).astype(int)
        
        # Low mileage indicator
        df_transformed['is_low_mileage'] = (df_transformed[mileage_column] < 50000).astype(int)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_mileage_features',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['mileage_log', 'mileage_category', 'is_high_mileage', 'is_low_mileage']
        })
        
        return df_transformed
    
    def create_age_features(self, df: pd.DataFrame, year_column: str = 'year') -> pd.DataFrame:
        """Create age-related features."""
        
        if year_column not in df.columns:
            logger.warning(f"Year column '{year_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Calculate car age
        current_year = datetime.now().year
        df_transformed['car_age'] = current_year - df_transformed[year_column]
        
        # Age categories
        age_bins = [0, 2, 5, 10, 15, 20, float('inf')]
        age_labels = ['0-2', '3-5', '6-10', '11-15', '16-20', '20+']
        
        df_transformed['age_category'] = pd.cut(
            df_transformed['car_age'],
            bins=age_bins,
            labels=age_labels,
            include_lowest=True
        )
        
        # Age indicators
        df_transformed['is_new'] = (df_transformed['car_age'] <= 2).astype(int)
        df_transformed['is_old'] = (df_transformed['car_age'] >= 10).astype(int)
        
        # Age squared (for non-linear relationships)
        df_transformed['car_age_squared'] = df_transformed['car_age'] ** 2
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_age_features',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['car_age', 'age_category', 'is_new', 'is_old', 'car_age_squared']
        })
        
        return df_transformed
    
    def create_engine_features(self, df: pd.DataFrame, engine_column: str = 'engine_size') -> pd.DataFrame:
        """Create engine-related features."""
        
        if engine_column not in df.columns:
            logger.warning(f"Engine column '{engine_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Engine size categories
        engine_bins = [0, 1.0, 1.6, 2.0, 3.0, 4.0, float('inf')]
        engine_labels = ['<1.0L', '1.0-1.6L', '1.6-2.0L', '2.0-3.0L', '3.0-4.0L', '>4.0L']
        
        df_transformed['engine_category'] = pd.cut(
            df_transformed[engine_column],
            bins=engine_bins,
            labels=engine_labels,
            include_lowest=True
        )
        
        # Engine size indicators
        df_transformed['is_small_engine'] = (df_transformed[engine_column] < 1.5).astype(int)
        df_transformed['is_large_engine'] = (df_transformed[engine_column] > 2.5).astype(int)
        
        # Power-to-weight ratio proxy (engine size / car age)
        if 'car_age' in df_transformed.columns:
            df_transformed['power_age_ratio'] = df_transformed[engine_column] / (df_transformed['car_age'] + 1)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_engine_features',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['engine_category', 'is_small_engine', 'is_large_engine', 'power_age_ratio']
        })
        
        return df_transformed
    
    def create_location_features(self, df: pd.DataFrame, location_column: str = 'location') -> pd.DataFrame:
        """Create location-related features."""
        
        if location_column not in df.columns:
            logger.warning(f"Location column '{location_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Location frequency (how common is this location)
        location_counts = df_transformed[location_column].value_counts()
        df_transformed['location_frequency'] = df_transformed[location_column].map(location_counts)
        
        # Location rarity (inverse of frequency)
        max_count = location_counts.max()
        df_transformed['location_rarity'] = 1 - (df_transformed['location_frequency'] / max_count)
        
        # Major location indicators
        major_locations = location_counts.head(10).index.tolist()
        df_transformed['is_major_location'] = df_transformed[location_column].isin(major_locations).astype(int)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_location_features',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['location_frequency', 'location_rarity', 'is_major_location']
        })
        
        return df_transformed
    
    def create_make_model_features(self, df: pd.DataFrame, make_column: str = 'make', model_column: str = 'model') -> pd.DataFrame:
        """Create make and model related features."""
        
        if make_column not in df.columns or model_column not in df.columns:
            logger.warning(f"Make or model columns not found")
            return df
        
        df_transformed = df.copy()
        
        # Make popularity
        make_counts = df_transformed[make_column].value_counts()
        df_transformed['make_popularity'] = df_transformed[make_column].map(make_counts)
        
        # Model popularity
        model_counts = df_transformed[model_column].value_counts()
        df_transformed['model_popularity'] = df_transformed[model_column].map(model_counts)
        
        # Make-model combination
        df_transformed['make_model'] = df_transformed[make_column] + '_' + df_transformed[model_column]
        
        # Make-model popularity
        make_model_counts = df_transformed['make_model'].value_counts()
        df_transformed['make_model_popularity'] = df_transformed['make_model'].map(make_model_counts)
        
        # Popular make indicators
        popular_makes = make_counts.head(10).index.tolist()
        df_transformed['is_popular_make'] = df_transformed[make_column].isin(popular_makes).astype(int)
        
        # Luxury make indicators
        luxury_makes = ['Mercedes-Benz', 'BMW', 'Audi', 'Lexus', 'Jaguar', 'Porsche']
        df_transformed['is_luxury_make'] = df_transformed[make_column].isin(luxury_makes).astype(int)
        
        # Economy make indicators
        economy_makes = ['Dacia', 'Renault', 'Fiat', 'Seat', 'Skoda']
        df_transformed['is_economy_make'] = df_transformed[make_column].isin(economy_makes).astype(int)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_make_model_features',
            'timestamp': datetime.now().isoformat(),
            'features_created': [
                'make_popularity', 'model_popularity', 'make_model', 'make_model_popularity',
                'is_popular_make', 'is_luxury_make', 'is_economy_make'
            ]
        })
        
        return df_transformed
    
    def create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features between variables."""
        
        df_transformed = df.copy()
        
        # Price-mileage interaction
        if 'price' in df_transformed.columns and 'mileage' in df_transformed.columns:
            df_transformed['price_mileage_interaction'] = df_transformed['price'] * df_transformed['mileage']
            df_transformed['price_mileage_ratio'] = df_transformed['price'] / (df_transformed['mileage'] + 1)
        
        # Price-age interaction
        if 'price' in df_transformed.columns and 'car_age' in df_transformed.columns:
            df_transformed['price_age_interaction'] = df_transformed['price'] * df_transformed['car_age']
            df_transformed['price_age_ratio'] = df_transformed['price'] / (df_transformed['car_age'] + 1)
        
        # Engine-mileage interaction
        if 'engine_size' in df_transformed.columns and 'mileage' in df_transformed.columns:
            df_transformed['engine_mileage_ratio'] = df_transformed['engine_size'] / (df_transformed['mileage'] + 1)
        
        # Engine-age interaction
        if 'engine_size' in df_transformed.columns and 'car_age' in df_transformed.columns:
            df_transformed['engine_age_ratio'] = df_transformed['engine_size'] / (df_transformed['car_age'] + 1)
        
        # Age-mileage interaction
        if 'car_age' in df_transformed.columns and 'mileage' in df_transformed.columns:
            df_transformed['age_mileage_ratio'] = df_transformed['car_age'] / (df_transformed['mileage'] + 1)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_interaction_features',
            'timestamp': datetime.now().isoformat(),
            'features_created': [
                'price_mileage_interaction', 'price_mileage_ratio',
                'price_age_interaction', 'price_age_ratio',
                'engine_mileage_ratio', 'engine_age_ratio',
                'age_mileage_ratio'
            ]
        })
        
        return df_transformed
    
    def create_polynomial_features(self, df: pd.DataFrame, columns: List[str], degree: int = 2) -> pd.DataFrame:
        """Create polynomial features."""
        
        df_transformed = df.copy()
        
        # Filter available columns
        available_columns = [col for col in columns if col in df_transformed.columns]
        
        if not available_columns:
            logger.warning("No valid columns for polynomial features")
            return df_transformed
        
        # Create polynomial features
        for col in available_columns:
            if degree >= 2:
                df_transformed[f'{col}_squared'] = df_transformed[col] ** 2
            
            if degree >= 3:
                df_transformed[f'{col}_cubed'] = df_transformed[col] ** 3
        
        # Create cross-product features
        if len(available_columns) >= 2:
            for i, col1 in enumerate(available_columns):
                for col2 in available_columns[i+1:]:
                    df_transformed[f'{col1}_{col2}_product'] = df_transformed[col1] * df_transformed[col2]
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_polynomial_features',
            'timestamp': datetime.now().isoformat(),
            'columns_used': available_columns,
            'degree': degree
        })
        
        return df_transformed
    
    def encode_categorical_features(self, df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
        """Encode categorical features."""
        
        df_transformed = df.copy()
        
        if columns is None:
            columns = df_transformed.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Filter available columns
        available_columns = [col for col in columns if col in df_transformed.columns]
        
        for col in available_columns:
            # Label encoding for high cardinality
            if df_transformed[col].nunique() > 10:
                df_transformed[f'{col}_encoded'] = df_transformed[col].astype('category').cat.codes
            else:
                # One-hot encoding for low cardinality
                dummies = pd.get_dummies(df_transformed[col], prefix=col, drop_first=True)
                df_transformed = pd.concat([df_transformed, dummies], axis=1)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'encode_categorical_features',
            'timestamp': datetime.now().isoformat(),
            'columns_encoded': available_columns
        })
        
        return df_transformed
    
    def scale_features(self, df: pd.DataFrame, columns: List[str] = None, method: str = 'standard') -> pd.DataFrame:
        """Scale numerical features."""
        
        df_transformed = df.copy()
        
        if columns is None:
            columns = df_transformed.select_dtypes(include=[np.number]).columns.tolist()
        
        # Filter available columns
        available_columns = [col for col in columns if col in df_transformed.columns]
        
        for col in available_columns:
            if method == 'standard':
                # Z-score normalization
                mean_val = df_transformed[col].mean()
                std_val = df_transformed[col].std()
                df_transformed[f'{col}_scaled'] = (df_transformed[col] - mean_val) / (std_val + 1e-8)
            
            elif method == 'minmax':
                # Min-max normalization
                min_val = df_transformed[col].min()
                max_val = df_transformed[col].max()
                df_transformed[f'{col}_scaled'] = (df_transformed[col] - min_val) / (max_val - min_val + 1e-8)
            
            elif method == 'robust':
                # Robust scaling (using median and IQR)
                median_val = df_transformed[col].median()
                q75 = df_transformed[col].quantile(0.75)
                q25 = df_transformed[col].quantile(0.25)
                iqr = q75 - q25
                df_transformed[f'{col}_scaled'] = (df_transformed[col] - median_val) / (iqr + 1e-8)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'scale_features',
            'timestamp': datetime.now().isoformat(),
            'columns_scaled': available_columns,
            'method': method
        })
        
        return df_transformed
    
    def transform_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all feature transformations."""
        
        df_transformed = df.copy()
        
        # Apply all feature transformations
        transformations = [
            ('create_price_features', 'price'),
            ('create_mileage_features', 'mileage'),
            ('create_age_features', 'year'),
            ('create_engine_features', 'engine_size'),
            ('create_location_features', 'location'),
            ('create_make_model_features', ['make', 'model']),
            ('create_interaction_features', None),
            ('encode_categorical_features', None),
            ('scale_features', None)
        ]
        
        for transform_name, param in transformations:
            try:
                if param is None:
                    df_transformed = getattr(self, transform_name)(df_transformed)
                elif isinstance(param, list):
                    df_transformed = getattr(self, transform_name)(df_transformed, *param)
                else:
                    df_transformed = getattr(self, transform_name)(df_transformed, param)
                
                logger.info(f"Applied feature transformation: {transform_name}")
                
            except Exception as e:
                logger.error(f"Error in feature transformation {transform_name}: {e}")
                continue
        
        return df_transformed
    
    def get_feature_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get summary of created features."""
        
        summary = {
            'total_features': len(df.columns),
            'numerical_features': len(df.select_dtypes(include=[np.number]).columns),
            'categorical_features': len(df.select_dtypes(include=['object', 'category']).columns),
            'feature_list': list(df.columns),
            'transformation_history': self.transformation_history
        }
        
        return summary
    
    def get_feature_importance_ranking(self, df: pd.DataFrame, target_column: str) -> pd.DataFrame:
        """Rank features by importance using correlation with target."""
        
        if target_column not in df.columns:
            logger.warning(f"Target column '{target_column}' not found")
            return pd.DataFrame()
        
        # Get numerical columns
        numerical_columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if target_column in numerical_columns:
            numerical_columns.remove(target_column)
        
        # Calculate correlations
        correlations = []
        for col in numerical_columns:
            corr = df[col].corr(df[target_column])
            correlations.append({
                'feature': col,
                'correlation': corr,
                'abs_correlation': abs(corr)
            })
        
        # Create DataFrame and sort
        correlation_df = pd.DataFrame(correlations)
        correlation_df = correlation_df.sort_values('abs_correlation', ascending=False)
        
        return correlation_df
