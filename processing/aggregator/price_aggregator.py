"""
Price aggregator for car price analysis.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PriceAggregator:
    """Price aggregator for car price analysis and statistics."""
    
    def __init__(self):
        """Initialize price aggregator."""
        self.price_data = None
        self.price_statistics = {}
        
    def calculate_price_statistics(self, 
                                 df: pd.DataFrame, 
                                 price_column: str = 'price',
                                 group_by: List[str] = None) -> Dict[str, Any]:
        """Calculate comprehensive price statistics."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return {}
        
        stats = {
            'overall': self._calculate_basic_stats(df[price_column]),
            'by_group': {}
        }
        
        if group_by:
            # Filter available grouping columns
            available_groups = [col for col in group_by if col in df.columns]
            
            for group_col in available_groups:
                group_stats = df.groupby(group_col)[price_column].describe()
                stats['by_group'][group_col] = group_stats.to_dict()
        
        self.price_statistics = stats
        return stats
    
    def _calculate_basic_stats(self, price_series: pd.Series) -> Dict[str, float]:
        """Calculate basic statistics for price series."""
        
        return {
            'count': len(price_series),
            'mean': price_series.mean(),
            'median': price_series.median(),
            'std': price_series.std(),
            'min': price_series.min(),
            'max': price_series.max(),
            'q25': price_series.quantile(0.25),
            'q75': price_series.quantile(0.75),
            'iqr': price_series.quantile(0.75) - price_series.quantile(0.25),
            'skewness': price_series.skew(),
            'kurtosis': price_series.kurtosis()
        }
    
    def calculate_price_depreciation(self, 
                                   df: pd.DataFrame, 
                                   price_column: str = 'price',
                                   year_column: str = 'year') -> pd.DataFrame:
        """Calculate price depreciation by year."""
        
        if price_column not in df.columns or year_column not in df.columns:
            logger.warning("Required columns not found for depreciation analysis")
            return df
        
        # Calculate average price by year
        yearly_prices = df.groupby(year_column)[price_column].agg(['mean', 'count']).reset_index()
        yearly_prices.columns = ['year', 'avg_price', 'count']
        
        # Sort by year
        yearly_prices = yearly_prices.sort_values('year')
        
        # Calculate depreciation rates
        yearly_prices['depreciation_rate'] = yearly_prices['avg_price'].pct_change() * 100
        yearly_prices['cumulative_depreciation'] = ((yearly_prices['avg_price'] / yearly_prices['avg_price'].iloc[0]) - 1) * 100
        
        return yearly_prices
    
    def calculate_price_per_mileage(self, 
                                  df: pd.DataFrame, 
                                  price_column: str = 'price',
                                  mileage_column: str = 'mileage') -> pd.DataFrame:
        """Calculate price per mileage ratio."""
        
        if price_column not in df.columns or mileage_column not in df.columns:
            logger.warning("Required columns not found for price per mileage analysis")
            return df
        
        # Calculate price per mileage
        df_copy = df.copy()
        df_copy['price_per_mileage'] = df_copy[price_column] / (df_copy[mileage_column] + 1)
        
        # Create mileage brackets
        mileage_bins = [0, 20000, 50000, 100000, 150000, 200000, float('inf')]
        mileage_labels = ['0-20k', '20k-50k', '50k-100k', '100k-150k', '150k-200k', '200k+']
        
        df_copy['mileage_bracket'] = pd.cut(df_copy[mileage_column], bins=mileage_bins, labels=mileage_labels)
        
        # Calculate average price per mileage bracket
        bracket_stats = df_copy.groupby('mileage_bracket').agg({
            price_column: ['mean', 'median', 'count'],
            'price_per_mileage': ['mean', 'median']
        }).reset_index()
        
        bracket_stats.columns = ['mileage_bracket', 'price_mean', 'price_median', 'count', 'price_per_mileage_mean', 'price_per_mileage_median']
        
        return bracket_stats
    
    def calculate_market_price_index(self, 
                                   df: pd.DataFrame, 
                                   base_year: int = 2020,
                                   price_column: str = 'price') -> pd.DataFrame:
        """Calculate market price index over time."""
        
        if 'date_scraped' not in df.columns:
            logger.warning("Date column not found for price index calculation")
            return df
        
        # Convert to datetime
        df_copy = df.copy()
        df_copy['date_scraped'] = pd.to_datetime(df_copy['date_scraped'])
        
        # Extract year and month
        df_copy['year_month'] = df_copy['date_scraped'].dt.to_period('M')
        
        # Calculate monthly average prices
        monthly_prices = df_copy.groupby('year_month')[price_column].mean().reset_index()
        monthly_prices.columns = ['period', 'avg_price']
        
        # Convert period to datetime for easier handling
        monthly_prices['period'] = monthly_prices['period'].dt.to_timestamp()
        
        # Calculate price index (base year = 100)
        base_price = monthly_prices[monthly_prices['period'].dt.year == base_year]['avg_price'].mean()
        
        if base_price > 0:
            monthly_prices['price_index'] = (monthly_prices['avg_price'] / base_price) * 100
        else:
            monthly_prices['price_index'] = 100
        
        return monthly_prices
    
    def identify_price_outliers(self, 
                              df: pd.DataFrame, 
                              price_column: str = 'price',
                              method: str = 'iqr',
                              group_columns: List[str] = None) -> pd.DataFrame:
        """Identify price outliers using various methods."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_copy = df.copy()
        
        if group_columns:
            # Group-based outlier detection
            available_groups = [col for col in group_columns if col in df.columns]
            
            if available_groups:
                # Calculate group statistics
                group_stats = df_copy.groupby(available_groups)[price_column].agg(['mean', 'std']).reset_index()
                group_stats.columns = available_groups + ['group_mean', 'group_std']
                
                # Merge back to original data
                df_copy = df_copy.merge(group_stats, on=available_groups, how='left')
                
                # Calculate z-scores
                df_copy['price_zscore'] = (df_copy[price_column] - df_copy['group_mean']) / (df_copy['group_std'] + 1e-8)
                
                # Flag outliers
                df_copy['is_outlier'] = np.abs(df_copy['price_zscore']) > 3
            else:
                # Global outlier detection
                df_copy = self._detect_global_outliers(df_copy, price_column, method)
        else:
            # Global outlier detection
            df_copy = self._detect_global_outliers(df_copy, price_column, method)
        
        return df_copy
    
    def _detect_global_outliers(self, 
                               df: pd.DataFrame, 
                               price_column: str, 
                               method: str) -> pd.DataFrame:
        """Detect outliers using global statistics."""
        
        if method == 'iqr':
            Q1 = df[price_column].quantile(0.25)
            Q3 = df[price_column].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            df['is_outlier'] = (df[price_column] < lower_bound) | (df[price_column] > upper_bound)
            
        elif method == 'zscore':
            z_scores = np.abs((df[price_column] - df[price_column].mean()) / df[price_column].std())
            df['is_outlier'] = z_scores > 3
            
        elif method == 'modified_zscore':
            median = df[price_column].median()
            mad = np.median(np.abs(df[price_column] - median))
            modified_z_scores = 0.6745 * (df[price_column] - median) / (mad + 1e-8)
            df['is_outlier'] = np.abs(modified_z_scores) > 3.5
        
        return df
    
    def calculate_price_trends(self, 
                              df: pd.DataFrame, 
                              price_column: str = 'price',
                              time_column: str = 'date_scraped',
                              period: str = 'monthly') -> pd.DataFrame:
        """Calculate price trends over time."""
        
        if price_column not in df.columns or time_column not in df.columns:
            logger.warning("Required columns not found for trend analysis")
            return df
        
        df_copy = df.copy()
        df_copy[time_column] = pd.to_datetime(df_copy[time_column])
        
        # Create time periods
        if period == 'monthly':
            df_copy['period'] = df_copy[time_column].dt.to_period('M')
        elif period == 'weekly':
            df_copy['period'] = df_copy[time_column].dt.to_period('W')
        elif period == 'daily':
            df_copy['period'] = df_copy[time_column].dt.date
        
        # Calculate trend statistics
        trends = df_copy.groupby('period')[price_column].agg(['mean', 'median', 'count', 'std']).reset_index()
        trends.columns = ['period', 'price_mean', 'price_median', 'listings_count', 'price_std']
        
        # Calculate trend indicators
        trends['price_change'] = trends['price_mean'].pct_change() * 100
        trends['price_trend'] = np.where(trends['price_change'] > 0, 'increasing', 
                                         np.where(trends['price_change'] < 0, 'decreasing', 'stable'))
        
        return trends
    
    def create_price_segments(self, 
                            df: pd.DataFrame, 
                            price_column: str = 'price',
                            n_segments: int = 5) -> pd.DataFrame:
        """Create price segments for analysis."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return df
        
        df_copy = df.copy()
        
        # Calculate quantile-based segments
        quantiles = np.linspace(0, 1, n_segments + 1)
        segment_boundaries = df_copy[price_column].quantile(quantiles)
        
        # Create segment labels
        segment_labels = [f'Segment_{i+1}' for i in range(n_segments)]
        
        # Assign segments
        df_copy['price_segment'] = pd.cut(df_copy[price_column], 
                                         bins=segment_boundaries, 
                                         labels=segment_labels, 
                                         include_lowest=True)
        
        # Calculate segment statistics
        segment_stats = df_copy.groupby('price_segment')[price_column].agg(['count', 'mean', 'median', 'min', 'max']).reset_index()
        segment_stats.columns = ['segment', 'count', 'mean_price', 'median_price', 'min_price', 'max_price']
        
        return segment_stats
    
    def calculate_price_elasticity(self, 
                                  df: pd.DataFrame, 
                                  price_column: str = 'price',
                                  quantity_column: str = 'listings_count') -> float:
        """Calculate price elasticity of demand."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return 0.0
        
        # Calculate price elasticity (simplified)
        # This is a basic implementation - real elasticity analysis would require more sophisticated methods
        
        # Group by price ranges and calculate average quantity
        price_bins = pd.qcut(df[price_column], q=10, duplicates='drop')
        elasticity_data = df.groupby(price_bins).size().reset_index()
        elasticity_data.columns = ['price_range', 'quantity']
        
        # Calculate midpoint of each price range
        elasticity_data['price_midpoint'] = elasticity_data['price_range'].apply(lambda x: x.mid)
        
        # Calculate percentage changes
        elasticity_data['price_pct_change'] = elasticity_data['price_midpoint'].pct_change()
        elasticity_data['quantity_pct_change'] = elasticity_data['quantity'].pct_change()
        
        # Calculate elasticity (avoid division by zero)
        elasticity = (elasticity_data['quantity_pct_change'] / elasticity_data['price_pct_change']).mean()
        
        return elasticity if not np.isnan(elasticity) else 0.0
    
    def generate_price_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive price analysis report."""
        
        report = {
            'summary': self.calculate_price_statistics(df),
            'depreciation': self.calculate_price_depreciation(df),
            'price_per_mileage': self.calculate_price_per_mileage(df),
            'market_index': self.calculate_market_price_index(df),
            'outliers': self.identify_price_outliers(df),
            'trends': self.calculate_price_trends(df),
            'segments': self.create_price_segments(df),
            'elasticity': self.calculate_price_elasticity(df),
            'generated_at': datetime.now().isoformat()
        }
        
        return report
