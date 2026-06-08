"""
Deal analyzer for AI-powered deal identification.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DealAnalyzer:
    """Deal analyzer for identifying good deals in car listings."""
    
    def __init__(self):
        """Initialize deal analyzer."""
        self.deal_criteria = {}
        self.market_benchmarks = {}
        self._initialize_criteria()
    
    def _initialize_criteria(self):
        """Initialize deal analysis criteria."""
        
        self.deal_criteria = {
            'price_discount': {
                'excellent': 0.20,  # 20% below market price
                'good': 0.15,        # 15% below market price
                'fair': 0.10,        # 10% below market price
                'poor': 0.05         # 5% below market price
            },
            'mileage': {
                'excellent': 0.5,   # 50% below average for age
                'good': 0.7,        # 70% below average for age
                'fair': 0.9,        # 90% below average for age
                'poor': 1.1         # 10% above average for age
            },
            'condition': {
                'excellent': 'excellent',
                'good': 'good',
                'fair': 'fair',
                'poor': 'poor'
            },
            'age': {
                'excellent': 3,     # 3 years or newer
                'good': 5,          # 5 years or newer
                'fair': 8,          # 8 years or newer
                'poor': 10          # 10+ years
            }
        }
    
    def calculate_market_price_estimate(self, 
                                      listing: Dict[str, Any], 
                                      market_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate estimated market price for a specific listing."""
        
        try:
            # Filter similar cars in market
            similar_cars = market_data[
                (market_data['make'] == listing.get('make')) &
                (market_data['model'] == listing.get('model')) &
                (market_data['year'] >= listing.get('year', 0) - 2) &
                (market_data['year'] <= listing.get('year', 0) + 2)
            ]
            
            if similar_cars.empty:
                return {
                    'estimated_price': listing.get('price', 0),
                    'confidence': 0.0,
                    'sample_size': 0,
                    'method': 'fallback'
                }
            
            # Calculate market statistics
            market_stats = similar_cars['price'].describe()
            
            # Adjust for mileage
            listing_mileage = listing.get('mileage', 0)
            avg_mileage = similar_cars['mileage'].mean() if 'mileage' in similar_cars.columns else 0
            
            mileage_adjustment = 1.0
            if avg_mileage > 0:
                if listing_mileage < avg_mileage * 0.5:
                    mileage_adjustment = 1.1  # 10% premium for low mileage
                elif listing_mileage > avg_mileage * 1.5:
                    mileage_adjustment = 0.9  # 10% discount for high mileage
            
            # Calculate estimated price
            estimated_price = market_stats['mean'] * mileage_adjustment
            
            return {
                'estimated_price': estimated_price,
                'confidence': min(len(similar_cars) / 10, 1.0),
                'sample_size': len(similar_cars),
                'method': 'market_comparable',
                'market_stats': market_stats.to_dict(),
                'mileage_adjustment': mileage_adjustment
            }
            
        except Exception as e:
            logger.error(f"Error calculating market price: {e}")
            return {
                'estimated_price': listing.get('price', 0),
                'confidence': 0.0,
                'sample_size': 0,
                'method': 'error'
            }
    
    def calculate_deal_score(self, 
                           listing: Dict[str, Any], 
                           market_estimate: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall deal score for a listing."""
        
        listing_price = listing.get('price', 0)
        estimated_price = market_estimate.get('estimated_price', listing_price)
        
        if estimated_price <= 0:
            return {
                'deal_score': 0.0,
                'deal_grade': 'unknown',
                'price_discount': 0.0,
                'factors': {}
            }
        
        # Calculate price discount
        price_discount = (estimated_price - listing_price) / estimated_price
        
        # Determine deal grade based on discount
        deal_grade = 'poor'
        for grade, threshold in self.deal_criteria['price_discount'].items():
            if price_discount >= threshold:
                deal_grade = grade
                break
        
        # Calculate individual factor scores
        factors = {
            'price_score': min(price_discount / 0.20, 1.0) * 100,  # Normalize to 0-100
            'confidence_score': market_estimate.get('confidence', 0.0) * 100,
            'sample_size_score': min(market_estimate.get('sample_size', 0) / 5, 1.0) * 100
        }
        
        # Calculate overall deal score
        overall_score = (
            factors['price_score'] * 0.5 +
            factors['confidence_score'] * 0.3 +
            factors['sample_size_score'] * 0.2
        )
        
        return {
            'deal_score': overall_score,
            'deal_grade': deal_grade,
            'price_discount': price_discount,
            'estimated_savings': estimated_price - listing_price,
            'factors': factors
        }
    
    def analyze_mileage_factor(self, 
                              listing: Dict[str, Any], 
                              market_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze mileage as a deal factor."""
        
        listing_mileage = listing.get('mileage', 0)
        listing_year = listing.get('year', 2024)
        car_age = 2024 - listing_year
        
        if car_age <= 0:
            return {'mileage_score': 0.0, 'mileage_grade': 'unknown'}
        
        # Calculate expected mileage for age
        expected_mileage = car_age * 15000  # 15,000 km per year average
        
        # Calculate mileage ratio
        mileage_ratio = listing_mileage / expected_mileage
        
        # Determine mileage grade
        if mileage_ratio <= 0.5:
            mileage_grade = 'excellent'
            mileage_score = 100
        elif mileage_ratio <= 0.7:
            mileage_grade = 'good'
            mileage_score = 80
        elif mileage_ratio <= 0.9:
            mileage_grade = 'fair'
            mileage_score = 60
        elif mileage_ratio <= 1.1:
            mileage_grade = 'average'
            mileage_score = 40
        else:
            mileage_grade = 'poor'
            mileage_score = 20
        
        return {
            'mileage_score': mileage_score,
            'mileage_grade': mileage_grade,
            'mileage_ratio': mileage_ratio,
            'expected_mileage': expected_mileage,
            'actual_mileage': listing_mileage
        }
    
    def analyze_condition_factor(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze condition as a deal factor."""
        
        condition = listing.get('condition', 'unknown')
        condition_score = 50  # Default score
        
        condition_scores = {
            'excellent': 100,
            'good': 80,
            'fair': 60,
            'poor': 20,
            'unknown': 50
        }
        
        condition_score = condition_scores.get(condition, 50)
        
        return {
            'condition_score': condition_score,
            'condition_grade': condition
        }
    
    def analyze_age_factor(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze car age as a deal factor."""
        
        year = listing.get('year', 2024)
        car_age = 2024 - year
        
        if car_age <= 0:
            return {'age_score': 100, 'age_grade': 'excellent'}
        
        # Determine age grade
        age_grade = 'poor'
        age_score = 20
        
        for grade, max_age in self.deal_criteria['age'].items():
            if car_age <= max_age:
                age_grade = grade
                age_score = 100 - (car_age / max_age) * 50  # Scale score
                break
        
        return {
            'age_score': age_score,
            'age_grade': age_grade,
            'car_age': car_age
        }
    
    def identify_deal_opportunities(self, 
                                  listings: List[Dict[str, Any]], 
                                  market_data: pd.DataFrame,
                                  min_score: float = 70.0) -> List[Dict[str, Any]]:
        """Identify deal opportunities from multiple listings."""
        
        opportunities = []
        
        for listing in listings:
            try:
                # Calculate market estimate
                market_estimate = self.calculate_market_price_estimate(listing, market_data)
                
                # Calculate deal score
                deal_analysis = self.calculate_deal_score(listing, market_estimate)
                
                # Analyze additional factors
                mileage_analysis = self.analyze_mileage_factor(listing, market_data)
                condition_analysis = self.analyze_condition_factor(listing)
                age_analysis = self.analyze_age_factor(listing)
                
                # Combine all analyses
                full_analysis = {
                    'listing': listing,
                    'market_estimate': market_estimate,
                    'deal_analysis': deal_analysis,
                    'mileage_analysis': mileage_analysis,
                    'condition_analysis': condition_analysis,
                    'age_analysis': age_analysis
                }
                
                # Add to opportunities if meets criteria
                if deal_analysis['deal_score'] >= min_score:
                    opportunities.append(full_analysis)
                    
            except Exception as e:
                logger.error(f"Error analyzing listing: {e}")
                continue
        
        # Sort by deal score
        opportunities.sort(key=lambda x: x['deal_analysis']['deal_score'], reverse=True)
        
        return opportunities
    
    def generate_deal_report(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive deal analysis report."""
        
        deal_analysis = analysis.get('deal_analysis', {})
        market_estimate = analysis.get('market_estimate', {})
        listing = analysis.get('listing', {})
        
        report = {
            'summary': {
                'deal_score': deal_analysis.get('deal_score', 0),
                'deal_grade': deal_analysis.get('deal_grade', 'unknown'),
                'estimated_savings': deal_analysis.get('estimated_savings', 0),
                'confidence': market_estimate.get('confidence', 0)
            },
            'price_analysis': {
                'listing_price': listing.get('price', 0),
                'estimated_market_price': market_estimate.get('estimated_price', 0),
                'price_discount': deal_analysis.get('price_discount', 0),
                'sample_size': market_estimate.get('sample_size', 0)
            },
            'factor_analysis': {
                'mileage': analysis.get('mileage_analysis', {}),
                'condition': analysis.get('condition_analysis', {}),
                'age': analysis.get('age_analysis', {})
            },
            'recommendations': self._generate_recommendations(analysis),
            'risk_factors': self._identify_risk_factors(analysis),
            'generated_at': datetime.now().isoformat()
        }
        
        return report
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on deal analysis."""
        
        recommendations = []
        deal_score = analysis.get('deal_analysis', {}).get('deal_score', 0)
        deal_grade = analysis.get('deal_analysis', {}).get('deal_grade', 'unknown')
        
        if deal_score >= 80:
            recommendations.append('Excellent deal - Act quickly!')
        elif deal_score >= 70:
            recommendations.append('Good deal - Consider purchasing')
        elif deal_score >= 60:
            recommendations.append('Fair deal - Negotiate if possible')
        else:
            recommendations.append('Poor deal - Look for better options')
        
        # Mileage recommendations
        mileage_grade = analysis.get('mileage_analysis', {}).get('mileage_grade', 'unknown')
        if mileage_grade == 'excellent':
            recommendations.append('Low mileage - Great value')
        elif mileage_grade == 'poor':
            recommendations.append('High mileage - Consider maintenance costs')
        
        # Condition recommendations
        condition_grade = analysis.get('condition_analysis', {}).get('condition_grade', 'unknown')
        if condition_grade == 'excellent':
            recommendations.append('Excellent condition - Less risk')
        elif condition_grade == 'poor':
            recommendations.append('Poor condition - Budget for repairs')
        
        # Confidence recommendations
        confidence = analysis.get('market_estimate', {}).get('confidence', 0)
        if confidence < 0.3:
            recommendations.append('Low market confidence - Verify pricing independently')
        
        return recommendations
    
    def _identify_risk_factors(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify potential risk factors."""
        
        risk_factors = []
        
        # Low confidence risk
        confidence = analysis.get('market_estimate', {}).get('confidence', 0)
        if confidence < 0.3:
            risk_factors.append('Low market data confidence')
        
        # High mileage risk
        mileage_ratio = analysis.get('mileage_analysis', {}).get('mileage_ratio', 0)
        if mileage_ratio > 1.5:
            risk_factors.append('High mileage - potential maintenance issues')
        
        # Poor condition risk
        condition_grade = analysis.get('condition_analysis', {}).get('condition_grade', 'unknown')
        if condition_grade == 'poor':
            risk_factors.append('Poor condition - repair costs likely')
        
        # Old age risk
        car_age = analysis.get('age_analysis', {}).get('car_age', 0)
        if car_age > 10:
            risk_factors.append('Old vehicle - higher failure risk')
        
        # Small sample size risk
        sample_size = analysis.get('market_estimate', {}).get('sample_size', 0)
        if sample_size < 3:
            risk_factors.append('Limited market comparables')
        
        return risk_factors
    
    def batch_analyze_deals(self, 
                           listings: List[Dict[str, Any]], 
                           market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Analyze multiple listings for deal opportunities."""
        
        results = []
        
        for i, listing in enumerate(listings):
            try:
                # Full analysis
                market_estimate = self.calculate_market_price_estimate(listing, market_data)
                deal_analysis = self.calculate_deal_score(listing, market_estimate)
                mileage_analysis = self.analyze_mileage_factor(listing, market_data)
                condition_analysis = self.analyze_condition_factor(listing)
                age_analysis = self.analyze_age_factor(listing)
                
                full_analysis = {
                    'listing_index': i,
                    'listing': listing,
                    'market_estimate': market_estimate,
                    'deal_analysis': deal_analysis,
                    'mileage_analysis': mileage_analysis,
                    'condition_analysis': condition_analysis,
                    'age_analysis': age_analysis
                }
                
                results.append(full_analysis)
                
            except Exception as e:
                logger.error(f"Error analyzing listing {i}: {e}")
                results.append({
                    'listing_index': i,
                    'error': str(e)
                })
        
        return results
