"""
Business analytics for monetization system.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of business metrics."""
    REVENUE = "revenue"
    PROFIT = "profit"
    CUSTOMER = "customer"
    TRANSACTION = "transaction"
    CONVERSION = "conversion"
    RETENTION = "retention"


class TimePeriod(Enum):
    """Time periods for analysis."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class BusinessMetric:
    """Business metric data point."""
    name: str
    value: float
    period: TimePeriod
    date: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CustomerSegment:
    """Customer segment data."""
    segment_id: str
    name: str
    description: str
    customer_count: int
    avg_revenue_per_customer: float
    avg_lifetime_value: float
    churn_rate: float
    acquisition_cost: float


@dataclass
class RevenueBreakdown:
    """Revenue breakdown data."""
    total_revenue: float
    marketplace_revenue: float
    api_revenue: float
    analytics_revenue: float
    lead_revenue: float
    subscription_revenue: float
    period: TimePeriod
    date: datetime


class BusinessAnalytics:
    """Business analytics for VER PRECOS monetization."""
    
    def __init__(self):
        """Initialize business analytics."""
        
        # Key performance indicators
        self.kpis = {
            'mrr_target': 75000.0,      # Monthly recurring revenue target
            'arr_target': 900000.0,     # Annual recurring revenue target
            'ltv_target': 1500.0,       # Lifetime value target
            'cac_target': 150.0,       # Customer acquisition cost target
            'churn_target': 0.05,       # Churn rate target (5%)
            'conversion_target': 0.035,  # Conversion rate target (3.5%)
            'margin_target': 0.85       # Gross margin target (85%)
        }
        
        # Revenue targets by phase
        self.revenue_targets = {
            'month_1': 3000.0,
            'month_2': 4700.0,
            'month_3': 7600.0,
            'month_6': 26500.0,
            'month_9': 56000.0,
            'month_12': 89000.0,
            'year_1': 470700.0,
            'year_2': 1800000.0,
            'year_3': 4800000.0
        }
        
        # Customer segments
        self.customer_segments = {
            'private_sellers': {
                'description': 'Individual car sellers',
                'avg_monthly_revenue': 50.0,
                'ltv': 300.0,
                'churn_rate': 0.08,
                'cac': 100.0
            },
            'professional_dealers': {
                'description': 'Professional car dealerships',
                'avg_monthly_revenue': 500.0,
                'ltv': 3000.0,
                'churn_rate': 0.03,
                'cac': 300.0
            },
            'enterprise_clients': {
                'description': 'Large automotive companies',
                'avg_monthly_revenue': 2000.0,
                'ltv': 12000.0,
                'churn_rate': 0.01,
                'cac': 1000.0
            },
            'api_users': {
                'description': 'API service users',
                'avg_monthly_revenue': 200.0,
                'ltv': 1200.0,
                'churn_rate': 0.05,
                'cac': 150.0
            }
        }
        
        logger.info("Business analytics initialized")
    
    def track_revenue_sources(self, period: TimePeriod = TimePeriod.MONTHLY) -> List[RevenueBreakdown]:
        """Track revenue by source."""
        
        try:
            # This would typically query the database for actual revenue data
            # For now, generate sample data based on targets
            
            revenue_breakdowns = []
            
            # Generate sample data for the last 12 months
            for i in range(12):
                date = datetime.now() - timedelta(days=30 * i)
                
                # Calculate revenue breakdown based on targets
                month_key = f"month_{12 - i}"
                total_target = self.revenue_targets.get(month_key, 0)
                
                # Revenue distribution (approximate)
                marketplace_percent = 0.55
                api_percent = 0.25
                analytics_percent = 0.15
                lead_percent = 0.05
                
                breakdown = RevenueBreakdown(
                    total_revenue=total_target,
                    marketplace_revenue=total_target * marketplace_percent,
                    api_revenue=total_target * api_percent,
                    analytics_revenue=total_target * analytics_percent,
                    lead_revenue=total_target * lead_percent,
                    subscription_revenue=total_target * 0.1,  # Part of marketplace
                    period=period,
                    date=date
                )
                
                revenue_breakdowns.append(breakdown)
            
            return revenue_breakdowns
            
        except Exception as e:
            logger.error(f"Error tracking revenue sources: {e}")
            return []
    
    def calculate_customer_ltv(self, customer_id: str) -> float:
        """Calculate customer lifetime value."""
        
        try:
            # This would typically query the database for customer data
            # For now, estimate based on customer segment
            
            # Simulate customer segment assignment
            customer_segments = list(self.customer_segments.keys())
            segment = np.random.choice(customer_segments)
            
            segment_data = self.customer_segments[segment]
            ltv = segment_data['ltv']
            
            return ltv
            
        except Exception as e:
            logger.error(f"Error calculating customer LTV: {e}")
            return 0.0
    
    def predict_churn_risk(self, customer_id: str) -> Dict[str, Any]:
        """Predict customer churn probability."""
        
        try:
            # This would use ML models for actual prediction
            # For now, estimate based on customer segment
            
            customer_segments = list(self.customer_segments.keys())
            segment = np.random.choice(customer_segments)
            
            segment_data = self.customer_segments[segment]
            base_churn_rate = segment_data['churn_rate']
            
            # Add some randomness for individual variation
            churn_probability = base_churn_rate * np.random.uniform(0.5, 1.5)
            churn_probability = min(churn_probability, 1.0)
            
            # Determine risk level
            if churn_probability < 0.05:
                risk_level = "low"
            elif churn_probability < 0.15:
                risk_level = "medium"
            else:
                risk_level = "high"
            
            return {
                'customer_id': customer_id,
                'churn_probability': churn_probability,
                'risk_level': risk_level,
                'segment': segment,
                'recommended_action': self._get_churn_prevention_action(risk_level)
            }
            
        except Exception as e:
            logger.error(f"Error predicting churn risk: {e}")
            return {'error': str(e)}
    
    def _get_churn_prevention_action(self, risk_level: str) -> str:
        """Get recommended action for churn prevention."""
        
        actions = {
            "low": "Monitor customer activity",
            "medium": "Send engagement offers",
            "high": "Immediate intervention required"
        }
        
        return actions.get(risk_level, "Monitor customer activity")
    
    def analyze_customer_segments(self) -> List[CustomerSegment]:
        """Analyze customer segments."""
        
        try:
            segments = []
            
            for segment_id, segment_data in self.customer_segments.items():
                # Simulate customer count
                if segment_id == 'private_sellers':
                    customer_count = np.random.randint(1000, 5000)
                elif segment_id == 'professional_dealers':
                    customer_count = np.random.randint(100, 500)
                elif segment_id == 'enterprise_clients':
                    customer_count = np.random.randint(10, 50)
                else:  # api_users
                    customer_count = np.random.randint(200, 1000)
                
                segment = CustomerSegment(
                    segment_id=segment_id,
                    name=segment_id.replace('_', ' ').title(),
                    description=segment_data['description'],
                    customer_count=customer_count,
                    avg_revenue_per_customer=segment_data['avg_monthly_revenue'],
                    avg_lifetime_value=segment_data['ltv'],
                    churn_rate=segment_data['churn_rate'],
                    acquisition_cost=segment_data['cac']
                )
                
                segments.append(segment)
            
            return segments
            
        except Exception as e:
            logger.error(f"Error analyzing customer segments: {e}")
            return []
    
    def calculate_monthly_metrics(self, month: int, year: int) -> Dict[str, Any]:
        """Calculate monthly business metrics."""
        
        try:
            # Get target for the month
            month_key = f"month_{month}"
            target_revenue = self.revenue_targets.get(month_key, 0)
            
            # Simulate actual revenue (with some variance)
            actual_revenue = target_revenue * np.random.uniform(0.8, 1.2)
            
            # Calculate other metrics
            metrics = {
                'month': month,
                'year': year,
                'target_revenue': target_revenue,
                'actual_revenue': actual_revenue,
                'revenue_achievement': actual_revenue / target_revenue if target_revenue > 0 else 0,
                'new_customers': int(actual_revenue / 150),  # Average CAC
                'total_customers': int(actual_revenue / 50),  # Average revenue per customer
                'mrr': actual_revenue,
                'growth_rate': 0.15,  # 15% month-over-month growth
                'churn_rate': 0.05,  # 5% monthly churn
                'conversion_rate': 0.035,  # 3.5% conversion rate
                'avg_transaction_value': 15000.0,
                'transactions_per_month': int(actual_revenue * 0.02 / 15000),  # 2% commission
                'cac': 150.0,
                'ltv': 1500.0,
                'ltv_cac_ratio': 10.0  # Healthy ratio
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating monthly metrics: {e}")
            return {'error': str(e)}
    
    def generate_financial_projections(self, months: int = 12) -> Dict[str, Any]:
        """Generate financial projections."""
        
        try:
            projections = {
                'period_months': months,
                'projections': []
            }
            
            current_mrr = 0
            
            for month in range(1, months + 1):
                # Get target for this month
                month_key = f"month_{month}"
                target_revenue = self.revenue_targets.get(month_key, 0)
                
                # Calculate growth factors
                if month <= 3:
                    growth_factor = 1.5  # High growth in early months
                elif month <= 6:
                    growth_factor = 1.3  # Medium growth
                elif month <= 12:
                    growth_factor = 1.2  # Steady growth
                else:
                    growth_factor = 1.1  # Mature growth
                
                # Calculate projected metrics
                projected_revenue = target_revenue * growth_factor
                projected_mrr = projected_revenue
                projected_customers = int(projected_mrr / 50)  # Average revenue per customer
                
                projection = {
                    'month': month,
                    'projected_revenue': projected_revenue,
                    'projected_mrr': projected_mrr,
                    'projected_customers': projected_customers,
                    'growth_rate': (projected_revenue - current_mrr) / current_mrr if current_mrr > 0 else 0,
                    'projected_cac': 150.0,
                    'projected_ltv': 1500.0,
                    'projected_churn_rate': 0.05
                }
                
                projections['projections'].append(projection)
                current_mrr = projected_mrr
            
            # Calculate totals
            total_revenue = sum(p['projected_revenue'] for p in projections['projections'])
            final_mrr = projections['projections'][-1]['projected_mrr'] if projections['projections'] else 0
            final_customers = projections['projections'][-1]['projected_customers'] if projections['projections'] else 0
            
            projections['summary'] = {
                'total_projected_revenue': total_revenue,
                'final_mrr': final_mrr,
                'final_customers': final_customers,
                'avg_monthly_growth': (final_mrr / 3000) ** (1 / months) - 1 if months > 0 else 0
            }
            
            return projections
            
        except Exception as e:
            logger.error(f"Error generating financial projections: {e}")
            return {'error': str(e)}
    
    def analyze_profitability(self, revenue: float, costs: Dict[str, float]) -> Dict[str, Any]:
        """Analyze profitability."""
        
        try:
            total_costs = sum(costs.values())
            gross_profit = revenue - total_costs
            profit_margin = (gross_profit / revenue) if revenue > 0 else 0
            
            # Calculate cost breakdown
            cost_breakdown = {}
            for cost_category, cost_amount in costs.items():
                cost_percentage = (cost_amount / total_costs) if total_costs > 0 else 0
                cost_breakdown[cost_category] = {
                    'amount': cost_amount,
                    'percentage': cost_percentage
                }
            
            # Determine profitability status
            if profit_margin > 0.3:
                profitability_status = "high"
            elif profit_margin > 0.15:
                profitability_status = "medium"
            elif profit_margin > 0:
                profitability_status = "low"
            else:
                profitability_status = "negative"
            
            return {
                'revenue': revenue,
                'total_costs': total_costs,
                'gross_profit': gross_profit,
                'profit_margin': profit_margin,
                'profitability_status': profitability_status,
                'cost_breakdown': cost_breakdown,
                'break_even_point': total_costs / 0.85 if revenue > 0 else 0,  # Assuming 85% margin
                'recommendations': self._get_profitability_recommendations(profit_margin)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing profitability: {e}")
            return {'error': str(e)}
    
    def _get_profitability_recommendations(self, profit_margin: float) -> List[str]:
        """Get profitability improvement recommendations."""
        
        recommendations = []
        
        if profit_margin < 0:
            recommendations.append("Immediate cost reduction required")
            recommendations.append("Review pricing strategy")
            recommendations.append("Increase revenue streams")
        elif profit_margin < 0.15:
            recommendations.append("Optimize operational efficiency")
            recommendations.append("Increase average transaction value")
            recommendations.append("Reduce customer acquisition costs")
        elif profit_margin < 0.3:
            recommendations.append("Focus on scaling revenue")
            recommendations.append("Optimize cost structure")
        else:
            recommendations.append("Maintain current profitability")
            recommendations.append("Explore expansion opportunities")
        
        return recommendations
    
    def track_conversion_funnel(self) -> Dict[str, Any]:
        """Track conversion funnel metrics."""
        
        try:
            # Simulate funnel data
            funnel_stages = [
                {'stage': 'visitors', 'count': 10000, 'conversion_rate': 1.0},
                {'stage': 'leads', 'count': 500, 'conversion_rate': 0.05},
                {'stage': 'qualified_leads', 'count': 150, 'conversion_rate': 0.3},
                {'stage': 'opportunities', 'count': 75, 'conversion_rate': 0.5},
                {'stage': 'customers', 'count': 25, 'conversion_rate': 0.33}
            ]
            
            # Calculate funnel metrics
            funnel_analysis = {
                'stages': [],
                'overall_conversion_rate': 0.0025,  # 25 / 10000
                'bottlenecks': [],
                'recommendations': []
            }
            
            for i, stage in enumerate(funnel_stages):
                stage_name = stage['stage']
                stage_count = stage['count']
                stage_conversion = stage['conversion_rate']
                
                if i > 0:
                    previous_count = funnel_stages[i-1]['count']
                    stage_conversion = stage_count / previous_count if previous_count > 0 else 0
                
                funnel_analysis['stages'].append({
                    'stage': stage_name,
                    'count': stage_count,
                    'conversion_rate': stage_conversion,
                    'drop_off_rate': 1 - stage_conversion
                })
                
                # Identify bottlenecks
                if stage_conversion < 0.1:
                    funnel_analysis['bottlenecks'].append(stage_name)
            
            # Generate recommendations
            if 'leads' in funnel_analysis['bottlenecks']:
                funnel_analysis['recommendations'].append("Improve lead generation quality")
            if 'qualified_leads' in funnel_analysis['bottlenecks']:
                funnel_analysis['recommendations'].append("Enhance lead qualification process")
            if 'opportunities' in funnel_analysis['bottlenecks']:
                funnel_analysis['recommendations'].append("Improve sales conversion tactics")
            
            return funnel_analysis
            
        except Exception as e:
            logger.error(f"Error tracking conversion funnel: {e}")
            return {'error': str(e)}
    
    def calculate_unit_economics(self) -> Dict[str, Any]:
        """Calculate unit economics metrics."""
        
        try:
            # Unit economics calculations
            ltv = 1500.0
            cac = 150.0
            ltv_cac_ratio = ltv / cac
            
            # Calculate payback period (in months)
            avg_monthly_revenue_per_customer = 50.0
            payback_period = cac / avg_monthly_revenue_per_customer
            
            # Calculate monthly contribution margin
            variable_cost_per_customer = 10.0  # Hosting, support, etc.
            contribution_margin = (avg_monthly_revenue_per_customer - variable_cost_per_customer) / avg_monthly_revenue_per_customer
            
            return {
                'ltv': ltv,
                'cac': cac,
                'ltv_cac_ratio': ltv_cac_ratio,
                'payback_period_months': payback_period,
                'avg_monthly_revenue_per_customer': avg_monthly_revenue_per_customer,
                'variable_cost_per_customer': variable_cost_per_customer,
                'contribution_margin': contribution_margin,
                'unit_economics_status': "healthy" if ltv_cac_ratio > 3 else "needs_improvement",
                'recommendations': self._get_unit_economics_recommendations(ltv_cac_ratio)
            }
            
        except Exception as e:
            logger.error(f"Error calculating unit economics: {e}")
            return {'error': str(e)}
    
    def _get_unit_economics_recommendations(self, ltv_cac_ratio: float) -> List[str]:
        """Get unit economics recommendations."""
        
        recommendations = []
        
        if ltv_cac_ratio < 3:
            recommendations.append("Increase customer lifetime value")
            recommendations.append("Reduce customer acquisition costs")
            recommendations.append("Improve retention rates")
        elif ltv_cac_ratio < 5:
            recommendations.append("Focus on customer upselling")
            recommendations.append("Optimize pricing strategy")
        else:
            recommendations.append("Maintain current unit economics")
            recommendations.append("Consider scaling acquisition")
        
        return recommendations
    
    def generate_business_health_score(self) -> Dict[str, Any]:
        """Generate overall business health score."""
        
        try:
            # Calculate individual component scores
            revenue_score = self._calculate_revenue_score()
            profitability_score = self._calculate_profitability_score()
            growth_score = self._calculate_growth_score()
            customer_score = self._calculate_customer_score()
            
            # Calculate overall score
            overall_score = (revenue_score + profitability_score + growth_score + customer_score) / 4
            
            # Determine health status
            if overall_score >= 80:
                health_status = "excellent"
            elif overall_score >= 60:
                health_status = "good"
            elif overall_score >= 40:
                health_status = "fair"
            else:
                health_status = "poor"
            
            return {
                'overall_score': overall_score,
                'health_status': health_status,
                'component_scores': {
                    'revenue': revenue_score,
                    'profitability': profitability_score,
                    'growth': growth_score,
                    'customer': customer_score
                },
                'recommendations': self._get_health_recommendations(overall_score),
                'key_metrics': {
                    'mrr': 75000.0,
                    'ltv_cac_ratio': 10.0,
                    'churn_rate': 0.05,
                    'profit_margin': 0.35
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating business health score: {e}")
            return {'error': str(e)}
    
    def _calculate_revenue_score(self) -> float:
        """Calculate revenue health score."""
        
        # Simulate revenue score based on MRR target
        current_mrr = 75000.0
        target_mrr = self.kpis['mrr_target']
        
        score = min(100, (current_mrr / target_mrr) * 100)
        return score
    
    def _calculate_profitability_score(self) -> float:
        """Calculate profitability health score."""
        
        # Simulate profitability score based on margin target
        current_margin = 0.35
        target_margin = self.kpis['margin_target']
        
        score = min(100, (current_margin / target_margin) * 100)
        return score
    
    def _calculate_growth_score(self) -> float:
        """Calculate growth health score."""
        
        # Simulate growth score based on month-over-month growth
        current_growth = 0.15  # 15% monthly growth
        target_growth = 0.20  # 20% target
        
        score = min(100, (current_growth / target_growth) * 100)
        return score
    
    def _calculate_customer_score(self) -> float:
        """Calculate customer health score."""
        
        # Simulate customer score based on LTV/CAC ratio
        current_ltv_cac = 10.0
        target_ltv_cac = 3.0
        
        score = min(100, (current_ltv_cac / target_ltv_cac) * 100)
        return score
    
    def _get_health_recommendations(self, overall_score: float) -> List[str]:
        """Get health improvement recommendations."""
        
        recommendations = []
        
        if overall_score < 40:
            recommendations.append("Immediate action required - multiple critical issues")
            recommendations.append("Focus on revenue generation")
            recommendations.append("Review cost structure")
        elif overall_score < 60:
            recommendations.append("Several areas need improvement")
            recommendations.append("Prioritize highest impact improvements")
        elif overall_score < 80:
            recommendations.append("Good performance with room for optimization")
            recommendations.append("Focus on scaling opportunities")
        else:
            recommendations.append("Excellent performance - consider expansion")
        
        return recommendations
