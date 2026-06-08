"""
Market aggregator for market analysis and insights.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MarketAggregator:
    """Market aggregator for comprehensive market analysis."""
    
    def __init__(self):
        """Initialize market aggregator."""
        self.market_data = None
        self.market_insights = {}
        
    def analyze_market_competition(self, 
                                 df: pd.DataFrame, 
                                 make_column: str = 'make',
                                 model_column: str = 'model',
                                 price_column: str = 'price') -> pd.DataFrame:
        """Analyze market competition between makes and models."""
        
        required_columns = [make_column, model_column, price_column]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.warning(f"Missing columns: {missing_columns}")
            return df
        
        # Calculate competition metrics
        competition = df.groupby([make_column, model_column]).agg({
            price_column: ['mean', 'median', 'min', 'max', 'count'],
        }).reset_index()
        
        # Flatten column names
        competition.columns = ['make', 'model', 'price_mean', 'price_median', 'price_min', 'price_max', 'listings_count']
        
        # Calculate market share
        total_listings = competition['listings_count'].sum()
        competition['market_share'] = (competition['listings_count'] / total_listings) * 100
        
        # Calculate price competitiveness (lower is better)
        overall_avg_price = df[price_column].mean()
        competition['price_competitiveness'] = (competition['price_mean'] / overall_avg_price) * 100
        
        # Rank by market share
        competition = competition.sort_values('market_share', ascending=False)
        competition['market_rank'] = range(1, len(competition) + 1)
        
        return competition
    
    def calculate_market_concentration(self, 
                                    df: pd.DataFrame, 
                                    make_column: str = 'make') -> Dict[str, Any]:
        """Calculate market concentration metrics."""
        
        if make_column not in df.columns:
            logger.warning(f"Make column '{make_column}' not found")
            return {}
        
        # Calculate make market shares
        make_counts = df[make_column].value_counts()
        total_listings = len(df)
        market_shares = make_counts / total_listings
        
        # Calculate Herfindahl-Hirschman Index (HHI)
        hhi = (market_shares * 100).pow(2).sum()
        
        # Calculate concentration ratio (CR4 - top 4 makes)
        cr4 = market_shares.head(4).sum() * 100
        
        # Interpret concentration
        if hhi < 1000:
            concentration_level = "Low (Competitive)"
        elif hhi < 1800:
            concentration_level = "Medium (Moderately concentrated)"
        else:
            concentration_level = "High (Concentrated)"
        
        concentration_metrics = {
            'hhi': hhi,
            'cr4': cr4,
            'concentration_level': concentration_level,
            'top_make_share': market_shares.iloc[0] * 100,
            'top_4_shares': (market_shares.head(4) * 100).to_dict(),
            'market_shares': (market_shares * 100).to_dict()
        }
        
        return concentration_metrics
    
    def analyze_price_segments_by_make(self, 
                                     df: pd.DataFrame, 
                                     make_column: str = 'make',
                                     price_column: str = 'price') -> pd.DataFrame:
        """Analyze price segments by make."""
        
        if make_column not in df.columns or price_column not in df.columns:
            logger.warning("Required columns not found")
            return df
        
        # Create price segments
        price_quantiles = df[price_column].quantile([0, 0.33, 0.66, 1.0])
        df_copy = df.copy()
        
        df_copy['price_segment'] = pd.cut(df_copy[price_column], 
                                         bins=price_quantiles, 
                                         labels=['Budget', 'Mid-range', 'Premium'],
                                         include_lowest=True)
        
        # Analyze by make and segment
        segment_analysis = df_copy.groupby([make_column, 'price_segment']).agg({
            price_column: ['mean', 'count']
        }).reset_index()
        
        segment_analysis.columns = ['make', 'price_segment', 'avg_price', 'listings_count']
        
        # Calculate segment market share by make
        total_by_make = segment_analysis.groupby('make')['listings_count'].transform('sum')
        segment_analysis['segment_share'] = (segment_analysis['listings_count'] / total_by_make) * 100
        
        return segment_analysis
    
    def calculate_geographic_market_analysis(self, 
                                          df: pd.DataFrame, 
                                          location_column: str = 'location',
                                          price_column: str = 'price') -> pd.DataFrame:
        """Analyze market by geographic location."""
        
        if location_column not in df.columns or price_column not in df.columns:
            logger.warning("Required columns not found")
            return df
        
        # Geographic analysis
        geo_analysis = df.groupby(location_column).agg({
            price_column: ['mean', 'median', 'min', 'max', 'count'],
        }).reset_index()
        
        geo_analysis.columns = ['location', 'price_mean', 'price_median', 'price_min', 'price_max', 'listings_count']
        
        # Calculate market size ranking
        geo_analysis = geo_analysis.sort_values('listings_count', ascending=False)
        geo_analysis['market_rank'] = range(1, len(geo_analysis) + 1)
        
        # Calculate price premium (compared to overall average)
        overall_avg_price = df[price_column].mean()
        geo_analysis['price_premium'] = ((geo_analysis['price_mean'] / overall_avg_price) - 1) * 100
        
        return geo_analysis
    
    def analyze_seasonal_patterns(self, 
                                 df: pd.DataFrame, 
                                 date_column: str = 'date_scraped',
                                 price_column: str = 'price') -> Dict[str, Any]:
        """Analyze seasonal market patterns."""
        
        if date_column not in df.columns or price_column not in df.columns:
            logger.warning("Required columns not found")
            return {}
        
        df_copy = df.copy()
        df_copy[date_column] = pd.to_datetime(df_copy[date_column])
        
        # Extract time components
        df_copy['month'] = df_copy[date_column].dt.month
        df_copy['quarter'] = df_copy[date_column].dt.quarter
        df_copy['day_of_week'] = df_copy[date_column].dt.dayofweek
        
        # Monthly analysis
        monthly_stats = df_copy.groupby('month')[price_column].agg(['mean', 'count']).reset_index()
        monthly_stats.columns = ['month', 'avg_price', 'listings_count']
        
        # Quarterly analysis
        quarterly_stats = df_copy.groupby('quarter')[price_column].agg(['mean', 'count']).reset_index()
        quarterly_stats.columns = ['quarter', 'avg_price', 'listings_count']
        
        # Day of week analysis
        dow_stats = df_copy.groupby('day_of_week')[price_column].agg(['mean', 'count']).reset_index()
        dow_stats.columns = ['day_of_week', 'avg_price', 'listings_count']
        
        seasonal_patterns = {
            'monthly_patterns': monthly_stats.to_dict('records'),
            'quarterly_patterns': quarterly_stats.to_dict('records'),
            'day_of_week_patterns': dow_stats.to_dict('records'),
            'peak_month': monthly_stats.loc[monthly_stats['listings_count'].idxmax(), 'month'],
            'peak_quarter': quarterly_stats.loc[quarterly_stats['listings_count'].idxmax(), 'quarter'],
            'price_trend_by_month': monthly_stats.sort_values('month')['avg_price'].tolist()
        }
        
        return seasonal_patterns
    
    def calculate_market_sufficiency(self, 
                                    df: pd.DataFrame, 
                                    location_column: str = 'location',
                                    make_column: str = 'make') -> pd.DataFrame:
        """Calculate market sufficiency by location and make."""
        
        if location_column not in df.columns or make_column not in df.columns:
            logger.warning("Required columns not found")
            return df
        
        # Market sufficiency analysis
        sufficiency = df.groupby([location_column, make_column]).size().reset_index()
        sufficiency.columns = ['location', 'make', 'listings_count']
        
        # Calculate sufficiency metrics
        total_by_location = sufficiency.groupby('location')['listings_count'].transform('sum')
        sufficiency['market_share_location'] = (sufficiency['listings_count'] / total_by_location) * 100
        
        # Classify sufficiency levels
        sufficiency['sufficiency_level'] = pd.cut(sufficiency['listings_count'], 
                                                bins=[0, 5, 20, 50, float('inf')], 
                                                labels=['Very Low', 'Low', 'Medium', 'High'])
        
        return sufficiency
    
    def analyze_price_momentum(self, 
                             df: pd.DataFrame, 
                             date_column: str = 'date_scraped',
                             price_column: str = 'price',
                             period: str = 'weekly') -> pd.DataFrame:
        """Analyze price momentum trends."""
        
        if date_column not in df.columns or price_column not in df.columns:
            logger.warning("Required columns not found")
            return df
        
        df_copy = df.copy()
        df_copy[date_column] = pd.to_datetime(df_copy[date_column])
        
        # Create time periods
        if period == 'weekly':
            df_copy['period'] = df_copy[date_column].dt.to_period('W')
        elif period == 'monthly':
            df_copy['period'] = df_copy[date_column].dt.to_period('M')
        
        # Calculate period statistics
        momentum = df_copy.groupby('period')[price_column].agg(['mean', 'count']).reset_index()
        momentum.columns = ['period', 'avg_price', 'listings_count']
        
        # Calculate momentum indicators
        momentum['price_change'] = momentum['avg_price'].pct_change() * 100
        momentum['volume_change'] = momentum['listings_count'].pct_change() * 100
        
        # Calculate momentum score (price change + volume change)
        momentum['momentum_score'] = (momentum['price_change'] + momentum['volume_change']) / 2
        
        # Classify momentum
        momentum['momentum_direction'] = pd.cut(momentum['momentum_score'], 
                                              bins=[-float('inf'), -2, 2, float('inf')], 
                                              labels=['Bearish', 'Neutral', 'Bullish'])
        
        return momentum
    
    def generate_market_opportunities(self, 
                                    df: pd.DataFrame, 
                                    make_column: str = 'make',
                                    location_column: str = 'location',
                                    price_column: str = 'price') -> List[Dict[str, Any]]:
        """Identify market opportunities."""
        
        opportunities = []
        
        # High demand, low supply locations
        if location_column in df.columns:
            location_stats = df.groupby(location_column).size().reset_index()
            location_stats.columns = ['location', 'listings_count']
            
            low_supply_locations = location_stats[location_stats['listings_count'] < 10]
            
            for _, row in low_supply_locations.iterrows():
                opportunities.append({
                    'type': 'Low Supply Location',
                    'location': row['location'],
                    'current_listings': row['listings_count'],
                    'recommendation': 'Increase listings in this location'
                })
        
        # Underserved makes in specific locations
        if make_column in df.columns and location_column in df.columns:
            make_location = df.groupby([location_column, make_column]).size().reset_index()
            make_location.columns = ['location', 'make', 'listings_count']
            
            underserved = make_location[make_location['listings_count'] < 5]
            
            for _, row in underserved.iterrows():
                opportunities.append({
                    'type': 'Underserved Make',
                    'location': row['location'],
                    'make': row['make'],
                    'current_listings': row['listings_count'],
                    'recommendation': f'Increase {row["make"]} listings in {row["location"]}'
                })
        
        # Price arbitrage opportunities
        if location_column in df.columns and price_column in df.columns:
            location_prices = df.groupby(location_column)[price_column].mean().reset_index()
            location_prices.columns = ['location', 'avg_price']
            
            # Find locations with significantly different prices
            overall_avg = df[price_column].mean()
            location_prices['price_diff'] = location_prices['avg_price'] - overall_avg
            
            # High price locations (good for sellers)
            high_price_locations = location_prices[location_prices['price_diff'] > overall_avg * 0.2]
            
            for _, row in high_price_locations.iterrows():
                opportunities.append({
                    'type': 'High Price Location',
                    'location': row['location'],
                    'avg_price': row['avg_price'],
                    'price_premium': row['price_diff'],
                    'recommendation': 'Target this location for higher margins'
                })
        
        return opportunities
    
    def generate_comprehensive_market_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive market analysis report."""
        
        report = {
            'competition_analysis': self.analyze_market_competition(df),
            'market_concentration': self.calculate_market_concentration(df),
            'price_segments_by_make': self.analyze_price_segments_by_make(df),
            'geographic_analysis': self.calculate_geographic_market_analysis(df),
            'seasonal_patterns': self.analyze_seasonal_patterns(df),
            'market_sufficiency': self.calculate_market_sufficiency(df),
            'price_momentum': self.analyze_price_momentum(df),
            'market_opportunities': self.generate_market_opportunities(df),
            'generated_at': datetime.now().isoformat()
        }
        
        return report
