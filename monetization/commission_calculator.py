"""
Commission calculator for monetization system.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SellerType(Enum):
    """Seller types for commission calculation."""
    PRIVATE = "private"
    PROFESSIONAL = "professional"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class TransactionType(Enum):
    """Transaction types."""
    LISTING_SALE = "listing_sale"
    API_USAGE = "api_usage"
    SUBSCRIPTION = "subscription"
    LEAD_PURCHASE = "lead_purchase"
    ANALYTICS_REPORT = "analytics_report"


class CommissionTier(Enum):
    """Commission tiers based on volume."""
    BRONZE = "bronze"      # 0-10 transactions/month
    SILVER = "silver"      # 11-50 transactions/month
    GOLD = "gold"          # 51-200 transactions/month
    PLATINUM = "platinum"  # 200+ transactions/month


@dataclass
class CommissionRule:
    """Commission rule configuration."""
    seller_type: SellerType
    transaction_type: TransactionType
    base_rate: float
    volume_discount: float
    minimum_commission: float
    maximum_commission: Optional[float] = None


@dataclass
class CommissionCalculation:
    """Commission calculation result."""
    transaction_amount: float
    commission_rate: float
    commission_amount: float
    net_amount: float
    seller_type: SellerType
    transaction_type: TransactionType
    tier: CommissionTier
    volume_discount: float
    effective_rate: float


class CommissionCalculator:
    """Commission calculator for VER PRECOS monetization."""
    
    def __init__(self):
        """Initialize commission calculator."""
        
        # Commission rates by seller type and transaction type
        self.commission_rules = {
            # Listing sales
            CommissionRule(SellerType.PRIVATE, TransactionType.LISTING_SALE, 0.025, 0.0, 5.0),
            CommissionRule(SellerType.PROFESSIONAL, TransactionType.LISTING_SALE, 0.02, 0.1, 10.0),
            CommissionRule(SellerType.PREMIUM, TransactionType.LISTING_SALE, 0.015, 0.15, 15.0),
            CommissionRule(SellerType.ENTERPRISE, TransactionType.LISTING_SALE, 0.01, 0.2, 25.0),
            
            # API usage
            CommissionRule(SellerType.PRIVATE, TransactionType.API_USAGE, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PROFESSIONAL, TransactionType.API_USAGE, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PREMIUM, TransactionType.API_USAGE, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.ENTERPRISE, TransactionType.API_USAGE, 0.0, 0.0, 0.0),
            
            # Subscriptions
            CommissionRule(SellerType.PRIVATE, TransactionType.SUBSCRIPTION, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PROFESSIONAL, TransactionType.SUBSCRIPTION, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PREMIUM, TransactionType.SUBSCRIPTION, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.ENTERPRISE, TransactionType.SUBSCRIPTION, 0.0, 0.0, 0.0),
            
            # Lead purchases
            CommissionRule(SellerType.PRIVATE, TransactionType.LEAD_PURCHASE, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PROFESSIONAL, TransactionType.LEAD_PURCHASE, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PREMIUM, TransactionType.LEAD_PURCHASE, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.ENTERPRISE, TransactionType.LEAD_PURCHASE, 0.0, 0.0, 0.0),
            
            # Analytics reports
            CommissionRule(SellerType.PRIVATE, TransactionType.ANALYTICS_REPORT, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PROFESSIONAL, TransactionType.ANALYTICS_REPORT, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.PREMIUM, TransactionType.ANALYTICS_REPORT, 0.0, 0.0, 0.0),
            CommissionRule(SellerType.ENTERPRISE, TransactionType.ANALYTICS_REPORT, 0.0, 0.0, 0.0),
        }
        
        # Volume thresholds for tiers
        self.tier_thresholds = {
            CommissionTier.BRONZE: (0, 10),
            CommissionTier.SILVER: (11, 50),
            CommissionTier.GOLD: (51, 200),
            CommissionTier.PLATINUM: (201, float('inf'))
        }
        
        # Special promotions and discounts
        self.promotions = {
            'new_seller_discount': 0.5,  # 50% discount for first 30 days
            'bulk_listing_discount': 0.1,  # 10% discount for 10+ listings
            'annual_subscription_discount': 0.2,  # 20% discount for annual plans
        }
        
        logger.info("Commission calculator initialized")
    
    def calculate_commission(self, 
                           transaction_amount: float,
                           seller_type: SellerType,
                           transaction_type: TransactionType,
                           monthly_volume: int = 0,
                           promotions: Optional[List[str]] = None) -> CommissionCalculation:
        """Calculate commission for a transaction."""
        
        try:
            # Get commission rule
            rule = self._get_commission_rule(seller_type, transaction_type)
            
            # Determine tier based on volume
            tier = self._determine_tier(monthly_volume)
            
            # Calculate base commission
            commission_amount = transaction_amount * rule.base_rate
            
            # Apply minimum commission
            commission_amount = max(commission_amount, rule.minimum_commission)
            
            # Apply maximum commission if set
            if rule.maximum_commission:
                commission_amount = min(commission_amount, rule.maximum_commission)
            
            # Apply volume discount
            volume_discount = self._calculate_volume_discount(tier, rule.volume_discount)
            commission_amount *= (1 - volume_discount)
            
            # Apply promotions
            promotion_discount = self._calculate_promotion_discount(promotions)
            commission_amount *= (1 - promotion_discount)
            
            # Calculate effective rate
            effective_rate = commission_amount / transaction_amount if transaction_amount > 0 else 0
            
            # Calculate net amount
            net_amount = transaction_amount - commission_amount
            
            return CommissionCalculation(
                transaction_amount=transaction_amount,
                commission_rate=rule.base_rate,
                commission_amount=commission_amount,
                net_amount=net_amount,
                seller_type=seller_type,
                transaction_type=transaction_type,
                tier=tier,
                volume_discount=volume_discount,
                effective_rate=effective_rate
            )
            
        except Exception as e:
            logger.error(f"Error calculating commission: {e}")
            raise
    
    def calculate_api_cost(self, 
                          api_calls: int,
                          seller_type: SellerType,
                          plan_type: str = 'starter') -> Dict[str, Any]:
        """Calculate API usage cost."""
        
        try:
            # Base pricing for API plans
            plan_prices = {
                'starter': 29.99,
                'growth': 199.99,
                'enterprise': 999.99
            }
            
            included_calls = {
                'starter': 1000,
                'growth': 10000,
                'enterprise': 100000
            }
            
            cost_per_additional_call = 0.05  # €0.05 per additional call
            
            if plan_type not in plan_prices:
                return {'error': f'Unknown plan type: {plan_type}'}
            
            base_price = plan_prices[plan_type]
            included = included_calls.get(plan_type, 0)
            
            if api_calls <= included:
                total_cost = base_price
                additional_calls = 0
                additional_cost = 0
            else:
                additional_calls = api_calls - included
                additional_cost = additional_calls * cost_per_additional_call
                total_cost = base_price + additional_cost
            
            return {
                'plan_type': plan_type,
                'api_calls': api_calls,
                'included_calls': included,
                'additional_calls': additional_calls,
                'base_price': base_price,
                'additional_cost': additional_cost,
                'total_cost': total_cost,
                'cost_per_call': total_cost / api_calls if api_calls > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating API cost: {e}")
            return {'error': str(e)}
    
    def calculate_subscription_cost(self, 
                                  plan_type: str,
                                  billing_cycle: str = 'monthly',
                                  seller_type: SellerType = SellerType.PRIVATE) -> Dict[str, Any]:
        """Calculate subscription cost."""
        
        try:
            # Base pricing for subscriptions
            subscription_prices = {
                'basic': {'monthly': 0.0, 'annual': 0.0},
                'featured': {'monthly': 9.99, 'annual': 99.99},
                'premium': {'monthly': 19.99, 'annual': 199.99},
                'enterprise': {'monthly': 99.99, 'annual': 999.99}
            }
            
            if plan_type not in subscription_prices:
                return {'error': f'Unknown plan type: {plan_type}'}
            
            monthly_price = subscription_prices[plan_type]['monthly']
            annual_price = subscription_prices[plan_type]['annual']
            
            # Apply seller type discounts
            seller_discounts = {
                SellerType.PRIVATE: 0.0,
                SellerType.PROFESSIONAL: 0.1,
                SellerType.PREMIUM: 0.15,
                SellerType.ENTERPRISE: 0.25
            }
            
            discount = seller_discounts.get(seller_type, 0.0)
            
            if billing_cycle == 'monthly':
                price = monthly_price * (1 - discount)
            elif billing_cycle == 'annual':
                price = annual_price * (1 - discount)
            else:
                return {'error': f'Unknown billing cycle: {billing_cycle}'}
            
            return {
                'plan_type': plan_type,
                'billing_cycle': billing_cycle,
                'seller_type': seller_type.value,
                'base_price': annual_price if billing_cycle == 'annual' else monthly_price,
                'discount': discount,
                'final_price': price,
                'monthly_equivalent': price / 12 if billing_cycle == 'annual' else price
            }
            
        except Exception as e:
            logger.error(f"Error calculating subscription cost: {e}")
            return {'error': str(e)}
    
    def calculate_lead_cost(self, 
                          lead_type: str,
                          quantity: int,
                          seller_type: SellerType = SellerType.PRIVATE) -> Dict[str, Any]:
        """Calculate lead purchase cost."""
        
        try:
            # Lead pricing
            lead_prices = {
                'basic': 5.00,
                'premium': 15.00,
                'exclusive': 50.00
            }
            
            if lead_type not in lead_prices:
                return {'error': f'Unknown lead type: {lead_type}'}
            
            price_per_lead = lead_prices[lead_type]
            
            # Apply volume discounts
            volume_discounts = {
                (1, 10): 0.0,      # No discount for 1-10 leads
                (11, 50): 0.1,     # 10% discount for 11-50 leads
                (51, 200): 0.15,   # 15% discount for 51-200 leads
                (201, 1000): 0.2   # 20% discount for 201+ leads
            }
            
            discount = 0.0
            for (min_qty, max_qty), disc in volume_discounts.items():
                if min_qty <= quantity <= max_qty:
                    discount = disc
                    break
            
            # Apply seller type discounts
            seller_discounts = {
                SellerType.PRIVATE: 0.0,
                SellerType.PROFESSIONAL: 0.05,
                SellerType.PREMIUM: 0.1,
                SellerType.ENTERPRISE: 0.15
            }
            
            total_discount = discount + seller_discounts.get(seller_type, 0.0)
            
            total_cost = quantity * price_per_lead * (1 - total_discount)
            
            return {
                'lead_type': lead_type,
                'quantity': quantity,
                'seller_type': seller_type.value,
                'price_per_lead': price_per_lead,
                'volume_discount': discount,
                'seller_discount': seller_discounts.get(seller_type, 0.0),
                'total_discount': total_discount,
                'total_cost': total_cost,
                'cost_per_lead': total_cost / quantity if quantity > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating lead cost: {e}")
            return {'error': str(e)}
    
    def calculate_monthly_revenue_projection(self, 
                                             user_count: int,
                                             avg_transaction_value: float,
                                             conversion_rate: float = 0.03) -> Dict[str, Any]:
        """Calculate monthly revenue projection."""
        
        try:
            # Calculate expected transactions
            expected_transactions = user_count * conversion_rate
            
            # Calculate revenue from transactions
            transaction_revenue = expected_transactions * avg_transaction_value * 0.02  # 2% avg commission
            
            # Calculate revenue from subscriptions (assuming 20% subscribe to premium)
            premium_users = int(user_count * 0.2)
            subscription_revenue = premium_users * 19.99  # Average premium price
            
            # Calculate revenue from API usage
            api_users = int(user_count * 0.1)  # 10% use API
            avg_api_calls = 1000
            api_revenue = api_users * 29.99  # Starter plan
            
            # Calculate revenue from leads
            lead_buyers = int(user_count * 0.05)  # 5% buy leads
            avg_leads_per_buyer = 10
            lead_revenue = lead_buyers * avg_leads_per_buyer * 10.00  # Average lead price
            
            total_revenue = transaction_revenue + subscription_revenue + api_revenue + lead_revenue
            
            return {
                'user_count': user_count,
                'conversion_rate': conversion_rate,
                'expected_transactions': expected_transactions,
                'transaction_revenue': transaction_revenue,
                'subscription_revenue': subscription_revenue,
                'api_revenue': api_revenue,
                'lead_revenue': lead_revenue,
                'total_revenue': total_revenue,
                'revenue_per_user': total_revenue / user_count if user_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating revenue projection: {e}")
            return {'error': str(e)}
    
    def get_commission_schedule(self, seller_type: SellerType) -> Dict[str, Any]:
        """Get commission schedule for a seller type."""
        
        try:
            schedule = {}
            
            for transaction_type in TransactionType:
                rule = self._get_commission_rule(seller_type, transaction_type)
                
                schedule[transaction_type.value] = {
                    'base_rate': rule.base_rate,
                    'minimum_commission': rule.minimum_commission,
                    'maximum_commission': rule.maximum_commission,
                    'volume_discount': rule.volume_discount
                }
            
            return schedule
            
        except Exception as e:
            logger.error(f"Error getting commission schedule: {e}")
            return {}
    
    def _get_commission_rule(self, seller_type: SellerType, transaction_type: TransactionType) -> CommissionRule:
        """Get commission rule for seller type and transaction type."""
        
        for rule in self.commission_rules:
            if rule.seller_type == seller_type and rule.transaction_type == transaction_type:
                return rule
        
        # Default rule if not found
        return CommissionRule(seller_type, transaction_type, 0.02, 0.0, 5.0)
    
    def _determine_tier(self, monthly_volume: int) -> CommissionTier:
        """Determine commission tier based on monthly volume."""
        
        for tier, (min_volume, max_volume) in self.tier_thresholds.items():
            if min_volume <= monthly_volume <= max_volume:
                return tier
        
        return CommissionTier.BRONZE
    
    def _calculate_volume_discount(self, tier: CommissionTier, base_discount: float) -> float:
        """Calculate volume discount based on tier."""
        
        tier_multipliers = {
            CommissionTier.BRONZE: 0.0,
            CommissionTier.SILVER: base_discount,
            CommissionTier.GOLD: base_discount * 1.5,
            CommissionTier.PLATINUM: base_discount * 2.0
        }
        
        return tier_multipliers.get(tier, 0.0)
    
    def _calculate_promotion_discount(self, promotions: Optional[List[str]]) -> float:
        """Calculate promotion discount."""
        
        if not promotions:
            return 0.0
        
        total_discount = 0.0
        
        for promotion in promotions:
            if promotion in self.promotions:
                total_discount += self.promotions[promotion]
        
        # Cap discount at 50%
        return min(total_discount, 0.5)
    
    def generate_commission_report(self, 
                                  seller_id: str,
                                  period_start: datetime,
                                  period_end: datetime) -> Dict[str, Any]:
        """Generate commission report for a seller."""
        
        try:
            # This would typically query the database for actual transactions
            # For now, return a template report
            
            report = {
                'seller_id': seller_id,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_transactions': 0,
                'total_revenue': 0.0,
                'total_commission': 0.0,
                'net_revenue': 0.0,
                'average_commission_rate': 0.0,
                'transactions_by_type': {},
                'commission_by_type': {},
                'monthly_breakdown': []
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating commission report: {e}")
            return {'error': str(e)}
    
    def validate_commission_calculation(self, 
                                       calculation: CommissionCalculation) -> Dict[str, Any]:
        """Validate commission calculation for errors."""
        
        try:
            validation_errors = []
            validation_warnings = []
            
            # Check if commission amount is reasonable
            if calculation.commission_amount > calculation.transaction_amount:
                validation_errors.append("Commission amount cannot exceed transaction amount")
            
            # Check if effective rate is reasonable
            if calculation.effective_rate > 0.3:  # 30% commission seems too high
                validation_warnings.append("Commission rate seems unusually high")
            
            # Check if net amount is negative
            if calculation.net_amount < 0:
                validation_errors.append("Net amount cannot be negative")
            
            # Check if commission is below minimum
            rule = self._get_commission_rule(calculation.seller_type, calculation.transaction_type)
            if calculation.commission_amount < rule.minimum_commission:
                validation_warnings.append("Commission below minimum threshold")
            
            return {
                'valid': len(validation_errors) == 0,
                'errors': validation_errors,
                'warnings': validation_warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating commission calculation: {e}")
            return {'valid': False, 'errors': [str(e)], 'warnings': []}
    
    def get_commission_optimization_suggestions(self, 
                                              seller_type: SellerType,
                                              monthly_volume: int) -> List[str]:
        """Get suggestions for commission optimization."""
        
        try:
            suggestions = []
            
            # Analyze current tier
            current_tier = self._determine_tier(monthly_volume)
            
            # Suggest tier improvements
            if current_tier == CommissionTier.BRONZE:
                suggestions.append("Increase monthly volume to 11+ transactions to unlock Silver tier discounts")
            elif current_tier == CommissionTier.SILVER:
                suggestions.append("Increase monthly volume to 51+ transactions to unlock Gold tier discounts")
            elif current_tier == CommissionTier.GOLD:
                suggestions.append("Increase monthly volume to 201+ transactions to unlock Platinum tier discounts")
            
            # Suggest seller type upgrades
            if seller_type == SellerType.PRIVATE:
                suggestions.append("Upgrade to Professional seller type for lower commission rates")
            elif seller_type == SellerType.PROFESSIONAL:
                suggestions.append("Upgrade to Premium seller type for even lower commission rates")
            
            # Suggest bulk operations
            if monthly_volume < 10:
                suggestions.append("Consider bulk listing operations to reduce per-transaction costs")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting optimization suggestions: {e}")
            return []
