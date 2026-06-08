"""
Price transformer for price analysis and transformation.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceTransformer:
    """Price transformer for price analysis and transformation."""
    
    def __init__(self):
        """Initialize price transformer."""
        self.price_benchmarks = {}
        self.transformation_history = []
        
    def normalize_prices(self, df: pd.DataFrame, price_column: str = 'price') -> pd.DataFrame:
        """Normalize prices for analysis."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Log transformation
        df_transformed['price_log'] = np.log1p(df_transformed[price_column])
        
        # Square root transformation
        df_transformed['price_sqrt'] = np.sqrt(df_transformed[price_column])
        
        # Box-Cox transformation (simplified)
        df_transformed['price_boxcox'] = np.log(df_transformed[price_column])
        
        # Standardized price (z-score)
        price_mean = df_transformed[price_column].mean()
        price_std = df_transformed[price_column].std()
        df_transformed['price_zscore'] = (df_transformed[price_column] - price_mean) / price_std
        
        # Min-max normalized price
        price_min = df_transformed[price_column].min()
        price_max = df_transformed[price_column].max()
        df_transformed['price_minmax'] = (df_transformed[price_column] - price_min) / (price_max - price_min)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'normalize_prices',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['price_log', 'price_sqrt', 'price_boxcox', 'price_zscore', 'price_minmax']
        })
        
        return df_transformed
    
    def calculate_price_indices(self, df: pd.DataFrame, price_column: str = 'price') -> pd.DataFrame:
        """Calculate various price indices."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Price-to-milage index
        if 'mileage' in df_transformed.columns:
            df_transformed['price_mileage_index'] = df_transformed[price_column] / (df_transformed['mileage'] + 1)
        
        # Price-to-age index
        if 'car_age' in df_transformed.columns:
            df_transformed['price_age_index'] = df_transformed[price_column] / (df_transformed['car_age'] + 1)
        
        # Price-to-engineer index
        if 'engine_size' in df_transformed.columns:
            df_transformed['price_engine_index'] = df_transformed[price_column] / df_transformed['engine_size']
        
        # Price-to-year index
        if 'year' in df_transformed.columns:
            df_transformed['price_year_index'] = df_transformed[price_column] / df_transformed['year']
        
        # Composite price index (average of all available indices)
        index_columns = [col for col in ['price_mileage_index', 'price_age_index', 'price_engine_index', 'price_year_index'] 
                        if col in df_transformed.columns]
        
        if index_columns:
            df_transformed['composite_price_index'] = df_transformed[index_columns].mean(axis=1)
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'calculate_price_indices',
            'timestamp': datetime.now().isoformat(),
            'indices_created': index_columns + ['composite_price_index']
        })
        
        return df_transformed
    
    def create_price_bands(self, df: pd.DataFrame, price_column: str = 'price', n_bands: int = 5) -> pd.DataFrame:
        """Create price bands for analysis."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Equal-width bands
        price_min = df_transformed[price_column].min()
        price_max = df_transformed[price_column].max()
        band_width = (price_max - price_min) / n_bands
        
        equal_width_bins = [price_min + i * band_width for i in range(n_bands + 1)]
        df_transformed['price_band_equal_width'] = pd.cut(
            df_transformed[price_column],
            bins=equal_width_bins,
            labels=[f'Band_{i+1}' for i in range(n_bands)],
            include_lowest=True
        )
        
        # Equal-frequency bands (quantiles)
        quantiles = np.linspace(0, 1, n_bands + 1)
        quantile_bins = df_transformed[price_column].quantile(quantiles)
        df_transformed['price_band_equal_freq'] = pd.cut(
            df_transformed[price_column],
            bins=quantile_bins,
            labels=[f'Quantile_{i+1}' for i in range(n_bands)],
            include_lowest=True
        )
        
        # Custom bands based on common price ranges
        custom_bins = [0, 5000, 10000, 20000, 35000, 50000, 75000, 100000, float('inf')]
        custom_labels = ['<5k', '5k-10k', '10k-20k', '20k-35k', '35k-50k', '50k-75k', '75k-100k', '>100k']
        df_transformed['price_band_custom'] = pd.cut(
            df_transformed[price_column],
            bins=custom_bins,
            labels=custom_labels,
            include_lowest=True
        )
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_price_bands',
            'timestamp': datetime.now().isoformat(),
            'bands_created': ['price_band_equal_width', 'price_band_equal_freq', 'price_band_custom']
        })
        
        return df_transformed
    
    def calculate_price_volatility(self, df: pd.DataFrame, price_column: str = 'price', 
                                  group_columns: List[str] = None) -> pd.DataFrame:
        """Calculate price volatility by groups."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        if group_columns is None:
            group_columns = ['make', 'model']
        
        # Filter available columns
        available_groups = [col for col in group_columns if col in df.columns]
        
        if not available_groups:
            logger.warning("No valid grouping columns for volatility calculation")
            return df
        
        df_transformed = df.copy()
        
        # Calculate price statistics by groups
        price_stats = df_transformed.groupby(available_groups)[price_column].agg(['mean', 'std', 'count']).reset_index()
        price_stats.columns = available_groups + ['price_mean', 'price_std', 'price_count']
        
        # Calculate coefficient of variation (volatility)
        price_stats['price_volatility'] = price_stats['price_std'] / price_stats['price_mean']
        
        # Merge back to original data
        df_transformed = df_transformed.merge(
            price_stats[available_groups + ['price_volatility']],
            on=available_groups,
            how='left'
        )
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'calculate_price_volatility',
            'timestamp': datetime.now().isoformat(),
            'group_columns': available_groups
        })
        
        return df_transformed
    
    def calculate_price_momentum(self, df: pd.DataFrame, price_column: str = 'price', 
                               time_column: str = 'date_scraped') -> pd.DataFrame:
        """Calculate price momentum over time."""
        
        if price_column not in df.columns or time_column not in df.columns:
            logger.warning("Required columns not found for momentum calculation")
            return df
        
        df_transformed = df.copy()
        df_transformed[time_column] = pd.to_datetime(df_transformed[time_column])
        
        # Sort by date
        df_transformed = df_transformed.sort_values(time_column)
        
        # Calculate price changes
        df_transformed['price_change'] = df_transformed[price_column].pct_change()
        
        # Calculate price momentum (moving average of price changes)
        df_transformed['price_momentum_7d'] = df_transformed['price_change'].rolling(window=7).mean()
        df_transformed['price_momentum_30d'] = df_transformed['price_change'].rolling(window=30).mean()
        
        # Calculate price trend
        df_transformed['price_trend'] = np.where(df_transformed['price_momentum_7d'] > 0, 'up', 
                                              np.where(df_transformed['price_momentum_7d'] < 0, 'down', 'stable'))
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'calculate_price_momentum',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['price_change', 'price_momentum_7d', 'price_momentum_30d', 'price_trend']
        })
        
        return df_transformed
    
    def calculate_price_relative_value(self, df: pd.DataFrame, price_column: str = 'price') -> pd.DataFrame:
        """Calculate relative value scores."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Calculate percentiles
        df_transformed['price_percentile'] = df_transformed[price_column].rank(pct=True)
        
        # Calculate deciles
        df_transformed['price_decile'] = pd.cut(
            df_transformed['price_percentile'],
            bins=np.linspace(0, 1, 11),
            labels=[f'Decile_{i}' for i in range(1, 11)],
            include_lowest=True
        )
        
        # Calculate relative value score (lower is better value)
        df_transformed['relative_value_score'] = (1 - df_transformed['price_percentile']) * 100
        
        # Value categories
        df_transformed['value_category'] = pd.cut(
            df_transformed['relative_value_score'],
            bins=[0, 20, 40, 60, 80, 100],
            labels=['Poor', 'Fair', 'Good', 'Very Good', 'Excellent'],
            include_lowest=True
        )
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'calculate_price_relative_value',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['price_percentile', 'price_decile', 'relative_value_score', 'value_category']
        })
        
        return df_transformed
    
    def adjust_prices_for_inflation(self, df: pd.DataFrame, price_column: str = 'price',
                                  inflation_rate: float = 0.03, base_year: int = 2020) -> pd.DataFrame:
        """Adjust prices for inflation."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Calculate year adjustment factor
        if 'year' in df_transformed.columns:
            years_diff = base_year - df_transformed['year']
            adjustment_factor = (1 + inflation_rate) ** years_diff
            df_transformed['price_inflation_adjusted'] = df_transformed[price_column] * adjustment_factor
        else:
            # Use current year if year column not available
            current_year = datetime.now().year
            years_diff = base_year - current_year
            adjustment_factor = (1 + inflation_rate) ** years_diff
            df_transformed['price_inflation_adjusted'] = df_transformed[price_column] * adjustment_factor
        
        # Calculate inflation impact
        df_transformed['inflation_impact'] = df_transformed['price_inflation_adjusted'] - df_transformed[price_column]
        df_transformed['inflation_impact_pct'] = (df_transformed['inflation_impact'] / df_transformed[price_column]) * 100
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'adjust_prices_for_inflation',
            'timestamp': datetime.now().isoformat(),
            'inflation_rate': inflation_rate,
            'base_year': base_year
        })
        
        return df_transformed
    
    def calculate_price_predictions(self, df: pd.DataFrame, price_column: str = 'price') -> pd.DataFrame:
        """Calculate simple price predictions based on trends."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Calculate moving averages
        df_transformed['price_ma_7'] = df_transformed[price_column].rolling(window=7, min_periods=1).mean()
        df_transformed['price_ma_30'] = df_transformed[price_column].rolling(window=30, min_periods=1).mean()
        
        # Calculate price trend direction
        df_transformed['price_trend_direction'] = np.where(
            df_transformed['price_ma_7'] > df_transformed['price_ma_30'], 'increasing', 'decreasing'
        )
        
        # Simple price prediction (using moving average)
        df_transformed['price_prediction'] = df_transformed['price_ma_7']
        
        # Prediction confidence based on volatility
        if 'price_volatility' in df_transformed.columns:
            df_transformed['prediction_confidence'] = 1 - df_transformed['price_volatility']
        else:
            df_transformed['prediction_confidence'] = 0.5  # Default confidence
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'calculate_price_predictions',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['price_ma_7', 'price_ma_30', 'price_trend_direction', 'price_prediction', 'prediction_confidence']
        })
        
        return df_transformed
    
    def create_price_anomaly_flags(self, df: pd.DataFrame, price_column: str = 'price') -> pd.DataFrame:
        """Create flags for price anomalies."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_transformed = df.copy()
        
        # Z-score based anomaly detection
        price_mean = df_transformed[price_column].mean()
        price_std = df_transformed[price_column].std()
        df_transformed['price_zscore'] = (df_transformed[price_column] - price_mean) / price_std
        
        # Flag anomalies (z-score > 3 or < -3)
        df_transformed['is_price_anomaly'] = np.abs(df_transformed['price_zscore']) > 3
        
        # IQR based anomaly detection
        Q1 = df_transformed[price_column].quantile(0.25)
        Q3 = df_transformed[price_column].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        df_transformed['is_price_outlier'] = (df_transformed[price_column] < lower_bound) | (df_transformed[price_column] > upper_bound)
        
        # Combined anomaly flag
        df_transformed['is_price_suspicious'] = df_transformed['is_price_anomaly'] | df_transformed['is_price_outlier']
        
        # Log transformation
        self.transformation_history.append({
            'transformation': 'create_price_anomaly_flags',
            'timestamp': datetime.now().isoformat(),
            'features_created': ['price_zscore', 'is_price_anomaly', 'is_price_outlier', 'is_price_suspicious']
        })
        
        return df_transformed
    
    def transform_all_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all price transformations."""
        
        df_transformed = df.copy()
        
        # Apply all price transformations
        transformations = [
            ('normalize_prices', 'price'),
            ('calculate_price_indices', 'price'),
            ('create_price_bands', 'price'),
            ('calculate_price_volatility', 'price'),
            ('calculate_price_momentum', 'price'),
            ('calculate_price_relative_value', 'price'),
            ('adjust_prices_for_inflation', 'price'),
            ('calculate_price_predictions', 'price'),
            ('create_price_anomaly_flags', 'price')
        ]
        
        for transform_name, param in transformations:
            try:
                df_transformed = getattr(self, transform_name)(df_transformed, param)
                logger.info(f"Applied price transformation: {transform_name}")
                
            except Exception as e:
                logger.error(f"Error in price transformation {transform_name}: {e}")
                continue
        
        return df_transformed
    
    def get_price_summary(self, df: pd.DataFrame, price_column: str = 'price') -> Dict[str, Any]:
        """Get comprehensive price summary."""
        
        if price_column not in df.columns:
            return {'error': f"Price column '{price_column}' not found"}
        
        summary = {
            'basic_stats': df[price_column].describe().to_dict(),
            'price_distribution': {
                'skewness': df[price_column].skew(),
                'kurtosis': df[price_column].kurtosis()
            },
            'price_ranges': {
                'budget_range': (df[price_column].quantile(0), df[price_column].quantile(0.25)),
                'mid_range': (df[price_column].quantile(0.25), df[price_column].quantile(0.75)),
                'premium_range': (df[price_column].quantile(0.75), df[price_column].max())
            },
            'transformation_history': self.transformation_history
        }
        
        return summary
