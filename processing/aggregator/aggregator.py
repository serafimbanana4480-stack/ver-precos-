"""
Data aggregator for processing listings.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataAggregator:
    """Data aggregator for processing and combining listings."""
    
    def __init__(self):
        """Initialize data aggregator."""
        self.aggregated_data = None
        self.aggregation_rules = {}
        
    def aggregate_listings(self, 
                          listings: List[Dict[str, Any]], 
                          group_by: List[str] = None,
                          agg_functions: Dict[str, str] = None) -> pd.DataFrame:
        """Aggregate listings by specified columns."""
        
        if not listings:
            return pd.DataFrame()
        
        df = pd.DataFrame(listings)
        
        # Default grouping columns
        if group_by is None:
            group_by = ['make', 'model', 'year', 'fuel_type', 'transmission']
        
        # Default aggregation functions
        if agg_functions is None:
            agg_functions = {
                'price': ['mean', 'median', 'min', 'max', 'count'],
                'mileage': ['mean', 'median'],
                'engine_size': ['mean', 'median']
            }
        
        # Filter available columns
        available_group_by = [col for col in group_by if col in df.columns]
        available_agg = {col: funcs for col, funcs in agg_functions.items() if col in df.columns}
        
        if not available_group_by:
            logger.warning("No valid grouping columns found")
            return df
        
        # Perform aggregation
        try:
            aggregated = df.groupby(available_group_by).agg(available_agg)
            
            # Flatten column names
            aggregated.columns = ['_'.join(col).strip() for col in aggregated.columns.values]
            aggregated = aggregated.reset_index()
            
            self.aggregated_data = aggregated
            return aggregated
            
        except Exception as e:
            logger.error(f"Error aggregating data: {e}")
            return df
    
    def calculate_market_trends(self, 
                               df: pd.DataFrame, 
                               time_column: str = 'date_scraped') -> pd.DataFrame:
        """Calculate market trends over time."""
        
        if time_column not in df.columns:
            logger.warning(f"Time column '{time_column}' not found")
            return df
        
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            df[time_column] = pd.to_datetime(df[time_column])
        
        # Extract time periods
        df['year_month'] = df[time_column].dt.to_period('M')
        df['year_week'] = df[time_column].dt.to_period('W')
        
        # Calculate trends
        trends = []
        
        # Monthly trends
        monthly_trends = df.groupby('year_month').agg({
            'price': ['mean', 'median', 'count'],
            'mileage': ['mean', 'median']
        }).reset_index()
        
        monthly_trends.columns = ['period', 'price_mean', 'price_median', 'listings_count', 'mileage_mean', 'mileage_median']
        monthly_trends['period_type'] = 'monthly'
        trends.append(monthly_trends)
        
        # Weekly trends
        weekly_trends = df.groupby('year_week').agg({
            'price': ['mean', 'median', 'count'],
            'mileage': ['mean', 'median']
        }).reset_index()
        
        weekly_trends.columns = ['period', 'price_mean', 'price_median', 'listings_count', 'mileage_mean', 'mileage_median']
        weekly_trends['period_type'] = 'weekly'
        trends.append(weekly_trends)
        
        # Combine trends
        all_trends = pd.concat(trends, ignore_index=True)
        
        return all_trends
    
    def detect_price_anomalies(self, 
                              df: pd.DataFrame, 
                              price_column: str = 'price',
                              group_columns: List[str] = None) -> pd.DataFrame:
        """Detect price anomalies in the data."""
        
        if group_columns is None:
            group_columns = ['make', 'model', 'year']
        
        # Filter available columns
        available_groups = [col for col in group_columns if col in df.columns]
        
        if not available_groups:
            logger.warning("No valid grouping columns for anomaly detection")
            return df
        
        # Calculate price statistics per group
        price_stats = df.groupby(available_groups)[price_column].agg(['mean', 'std']).reset_index()
        price_stats.columns = available_groups + ['price_mean', 'price_std']
        
        # Merge back to original data
        df_with_stats = df.merge(price_stats, on=available_groups, how='left')
        
        # Calculate z-scores
        df_with_stats['price_zscore'] = (df_with_stats[price_column] - df_with_stats['price_mean']) / df_with_stats['price_std']
        
        # Flag anomalies (z-score > 3 or < -3)
        df_with_stats['is_price_anomaly'] = np.abs(df_with_stats['price_zscore']) > 3
        
        return df_with_stats
    
    def create_price_distribution(self, 
                                df: pd.DataFrame, 
                                price_column: str = 'price',
                                group_columns: List[str] = None) -> Dict[str, Any]:
        """Create price distribution statistics."""
        
        if group_columns is None:
            group_columns = ['make', 'model']
        
        # Filter available columns
        available_groups = [col for col in group_columns if col in df.columns]
        
        distribution_stats = {}
        
        if available_groups:
            # Group-based distributions
            grouped = df.groupby(available_groups)[price_column].describe()
            distribution_stats['grouped'] = grouped.to_dict()
        else:
            # Overall distribution
            overall_stats = df[price_column].describe()
            distribution_stats['overall'] = overall_stats.to_dict()
        
        # Price percentiles
        percentiles = [10, 25, 50, 75, 90, 95, 99]
        percentile_values = np.percentile(df[price_column], percentiles)
        
        distribution_stats['percentiles'] = dict(zip(percentiles, percentile_values))
        
        # Price ranges
        distribution_stats['price_ranges'] = {
            'budget': (df[price_column].quantile(0), df[price_column].quantile(0.33)),
            'mid_range': (df[price_column].quantile(0.33), df[price_column].quantile(0.66)),
            'premium': (df[price_column].quantile(0.66), df[price_column].max())
        }
        
        return distribution_stats
    
    def aggregate_by_location(self, 
                            df: pd.DataFrame, 
                            location_column: str = 'location') -> pd.DataFrame:
        """Aggregate data by location."""
        
        if location_column not in df.columns:
            logger.warning(f"Location column '{location_column}' not found")
            return df
        
        location_stats = df.groupby(location_column).agg({
            'price': ['mean', 'median', 'min', 'max', 'count'],
            'mileage': ['mean', 'median'],
            'year': ['mean', 'min', 'max']
        }).reset_index()
        
        # Flatten column names
        location_stats.columns = ['location', 'price_mean', 'price_median', 'price_min', 'price_max', 'listings_count', 
                               'mileage_mean', 'mileage_median', 'year_mean', 'year_min', 'year_max']
        
        # Calculate price per location rank
        location_stats = location_stats.sort_values('price_mean', ascending=False)
        location_stats['price_rank'] = range(1, len(location_stats) + 1)
        
        return location_stats
    
    def create_summary_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create comprehensive summary report."""
        
        report = {
            'dataset_info': {
                'total_listings': len(df),
                'date_range': {
                    'start': df['date_scraped'].min() if 'date_scraped' in df.columns else None,
                    'end': df['date_scraped'].max() if 'date_scraped' in df.columns else None
                },
                'columns': list(df.columns)
            },
            'price_summary': {
                'mean_price': df['price'].mean() if 'price' in df.columns else None,
                'median_price': df['price'].median() if 'price' in df.columns else None,
                'price_range': {
                    'min': df['price'].min() if 'price' in df.columns else None,
                    'max': df['price'].max() if 'price' in df.columns else None
                }
            },
            'top_makes': df['make'].value_counts().head(10).to_dict() if 'make' in df.columns else {},
            'top_models': df['model'].value_counts().head(10).to_dict() if 'model' in df.columns else {},
            'fuel_types': df['fuel_type'].value_counts().to_dict() if 'fuel_type' in df.columns else {},
            'transmissions': df['transmission'].value_counts().to_dict() if 'transmission' in df.columns else {}
        }
        
        return report
    
    def export_aggregated_data(self, 
                              output_path: str, 
                              format: str = 'csv') -> bool:
        """Export aggregated data to file."""
        
        if self.aggregated_data is None:
            logger.warning("No aggregated data to export")
            return False
        
        try:
            if format.lower() == 'csv':
                self.aggregated_data.to_csv(output_path, index=False)
            elif format.lower() == 'json':
                self.aggregated_data.to_json(output_path, orient='records', indent=2)
            elif format.lower() == 'excel':
                self.aggregated_data.to_excel(output_path, index=False)
            else:
                logger.error(f"Unsupported format: {format}")
                return False
            
            logger.info(f"Data exported to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return False
