"""
Subscription manager for monetization system.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SubscriptionStatus(Enum):
    """Subscription status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class BillingCycle(Enum):
    """Billing cycles."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class PlanType(Enum):
    """Subscription plan types."""
    BASIC = "basic"
    FEATURED = "featured"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class Subscription:
    """Subscription data."""
    subscription_id: str
    user_id: str
    plan_type: PlanType
    billing_cycle: BillingCycle
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime]
    trial_end_date: Optional[datetime]
    next_billing_date: datetime
    amount: float
    currency: str = "EUR"
    auto_renew: bool = True
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SubscriptionPlan:
    """Subscription plan configuration."""
    plan_type: PlanType
    name: str
    description: str
    monthly_price: float
    annual_price: float
    features: List[str]
    trial_days: int
    limits: Dict[str, Any]


class SubscriptionManager:
    """Subscription manager for VER PRECOS monetization."""
    
    def __init__(self):
        """Initialize subscription manager."""
        
        # Subscription plans configuration
        self.plans = {
            PlanType.BASIC: SubscriptionPlan(
                plan_type=PlanType.BASIC,
                name="Basic Plan",
                description="Free plan for individual sellers",
                monthly_price=0.0,
                annual_price=0.0,
                features=[
                    "Basic listing management",
                    "Up to 5 active listings",
                    "Basic analytics",
                    "Community support"
                ],
                trial_days=0,
                limits={
                    "listings": 5,
                    "api_calls": 0,
                    "analytics_reports": 1
                }
            ),
            PlanType.FEATURED: SubscriptionPlan(
                plan_type=PlanType.FEATURED,
                name="Featured Plan",
                description="Enhanced visibility for serious sellers",
                monthly_price=9.99,
                annual_price=99.99,
                features=[
                    "All Basic features",
                    "Up to 25 active listings",
                    "Featured listings",
                    "Advanced analytics",
                    "Priority support",
                    "Lead generation (5/month)"
                ],
                trial_days=14,
                limits={
                    "listings": 25,
                    "api_calls": 1000,
                    "analytics_reports": 10,
                    "leads": 5
                }
            ),
            PlanType.PREMIUM: SubscriptionPlan(
                plan_type=PlanType.PREMIUM,
                name="Premium Plan",
                description="Professional selling tools",
                monthly_price=19.99,
                annual_price=199.99,
                features=[
                    "All Featured features",
                    "Unlimited listings",
                    "Premium visibility",
                    "Real-time analytics",
                    "API access",
                    "Lead generation (25/month)",
                    "Dedicated support"
                ],
                trial_days=30,
                limits={
                    "listings": float('inf'),
                    "api_calls": 10000,
                    "analytics_reports": 50,
                    "leads": 25
                }
            ),
            PlanType.ENTERPRISE: SubscriptionPlan(
                plan_type=PlanType.ENTERPRISE,
                name="Enterprise Plan",
                description="Complete solution for large dealers",
                monthly_price=99.99,
                annual_price=999.99,
                features=[
                    "All Premium features",
                    "White-label options",
                    "Custom integrations",
                    "Unlimited API calls",
                    "Unlimited leads",
                    "Advanced analytics",
                    "Priority support",
                    "Dedicated account manager"
                ],
                trial_days=30,
                limits={
                    "listings": float('inf'),
                    "api_calls": float('inf'),
                    "analytics_reports": float('inf'),
                    "leads": float('inf')
                }
            )
        }
        
        # Discounts and promotions
        self.discounts = {
            'annual_discount': 0.2,  # 20% discount for annual plans
            'volume_discount': 0.1,  # 10% discount for 5+ users
            'loyalty_discount': 0.15, # 15% discount after 12 months
            'promotional_discount': 0.25  # 25% discount for promotions
        }
        
        logger.info("Subscription manager initialized")
    
    def create_subscription(self, 
                           user_id: str,
                           plan_type: PlanType,
                           billing_cycle: BillingCycle = BillingCycle.MONTHLY,
                           trial_days: Optional[int] = None,
                           promo_code: Optional[str] = None) -> Subscription:
        """Create a new subscription."""
        
        try:
            plan = self.plans[plan_type]
            
            # Calculate pricing
            if billing_cycle == BillingCycle.ANNUAL:
                amount = plan.annual_price
            else:
                amount = plan.monthly_price
            
            # Apply discounts
            discount = self._calculate_discount(user_id, plan_type, billing_cycle, promo_code)
            amount *= (1 - discount)
            
            # Calculate dates
            start_date = datetime.now()
            
            # Handle trial period
            trial_end_date = None
            if trial_days:
                trial_end_date = start_date + timedelta(days=trial_days)
            elif plan.trial_days > 0:
                trial_end_date = start_date + timedelta(days=plan.trial_days)
            
            # Calculate end date and next billing
            if trial_end_date:
                end_date = trial_end_date
                next_billing_date = trial_end_date
            else:
                if billing_cycle == BillingCycle.MONTHLY:
                    end_date = start_date + timedelta(days=30)
                    next_billing_date = end_date
                elif billing_cycle == BillingCycle.QUARTERLY:
                    end_date = start_date + timedelta(days=90)
                    next_billing_date = end_date
                else:  # ANNUAL
                    end_date = start_date + timedelta(days=365)
                    next_billing_date = end_date
            
            # Create subscription
            subscription = Subscription(
                subscription_id=f"sub_{user_id}_{datetime.now().timestamp()}",
                user_id=user_id,
                plan_type=plan_type,
                billing_cycle=billing_cycle,
                status=SubscriptionStatus.TRIAL if trial_end_date else SubscriptionStatus.ACTIVE,
                start_date=start_date,
                end_date=end_date,
                trial_end_date=trial_end_date,
                next_billing_date=next_billing_date,
                amount=amount,
                auto_renew=True,
                metadata={
                    'discount': discount,
                    'promo_code': promo_code,
                    'original_amount': plan.monthly_price if billing_cycle == BillingCycle.MONTHLY else plan.annual_price
                }
            )
            
            logger.info(f"Created subscription {subscription.subscription_id} for user {user_id}")
            return subscription
            
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            raise
    
    def upgrade_subscription(self, 
                             user_id: str,
                             new_plan_type: PlanType,
                             prorate: bool = True) -> Subscription:
        """Upgrade user subscription."""
        
        try:
            # Get current subscription
            current_sub = self.get_user_subscription(user_id)
            if not current_sub:
                raise ValueError(f"No active subscription found for user {user_id}")
            
            # Check if upgrade
            if not self._is_upgrade(current_sub.plan_type, new_plan_type):
                raise ValueError(f"Plan {new_plan_type} is not an upgrade from {current_sub.plan_type}")
            
            # Calculate prorated amount
            if prorate:
                remaining_days = (current_sub.end_date - datetime.now()).days
                current_plan = self.plans[current_sub.plan_type]
                new_plan = self.plans[new_plan_type]
                
                # Calculate refund for current plan
                refund_amount = (current_plan.monthly_price / 30) * remaining_days
                
                # Calculate charge for new plan
                charge_amount = (new_plan.monthly_price / 30) * remaining_days
                net_amount = charge_amount - refund_amount
            else:
                net_amount = new_plan.monthly_price
            
            # Create new subscription
            new_subscription = self.create_subscription(
                user_id=user_id,
                plan_type=new_plan_type,
                billing_cycle=current_sub.billing_cycle
            )
            
            # Cancel old subscription
            self.cancel_subscription(current_sub.subscription_id)
            
            logger.info(f"Upgraded subscription for user {user_id} to {new_plan_type}")
            return new_subscription
            
        except Exception as e:
            logger.error(f"Error upgrading subscription: {e}")
            raise
    
    def downgrade_subscription(self, 
                               user_id: str,
                               new_plan_type: PlanType) -> Subscription:
        """Downgrade user subscription."""
        
        try:
            # Get current subscription
            current_sub = self.get_user_subscription(user_id)
            if not current_sub:
                raise ValueError(f"No active subscription found for user {user_id}")
            
            # Check if downgrade
            if not self._is_downgrade(current_sub.plan_type, new_plan_type):
                raise ValueError(f"Plan {new_plan_type} is not a downgrade from {current_sub.plan_type}")
            
            # Schedule downgrade for next billing cycle
            new_subscription = self.create_subscription(
                user_id=user_id,
                plan_type=new_plan_type,
                billing_cycle=current_sub.billing_cycle
            )
            
            # Update current subscription to cancel at end of period
            current_sub.auto_renew = False
            current_sub.metadata = current_sub.metadata or {}
            current_sub.metadata['downgrade_to'] = new_plan_type.value
            
            logger.info(f"Scheduled downgrade for user {user_id} to {new_plan_type}")
            return new_subscription
            
        except Exception as e:
            logger.error(f"Error downgrading subscription: {e}")
            raise
    
    def cancel_subscription(self, subscription_id: str, reason: Optional[str] = None) -> bool:
        """Cancel subscription."""
        
        try:
            # This would typically update the database
            # For now, simulate cancellation
            
            subscription = self.get_subscription(subscription_id)
            if not subscription:
                return False
            
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.auto_renew = False
            
            if reason:
                subscription.metadata = subscription.metadata or {}
                subscription.metadata['cancellation_reason'] = reason
            
            logger.info(f"Cancelled subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            return False
    
    def pause_subscription(self, subscription_id: str, pause_days: int = 30) -> bool:
        """Pause subscription."""
        
        try:
            subscription = self.get_subscription(subscription_id)
            if not subscription:
                return False
            
            if subscription.status != SubscriptionStatus.ACTIVE:
                return False
            
            subscription.status = SubscriptionStatus.SUSPENDED
            subscription.metadata = subscription.metadata or {}
            subscription.metadata['pause_end_date'] = (datetime.now() + timedelta(days=pause_days)).isoformat()
            
            logger.info(f"Paused subscription {subscription_id} for {pause_days} days")
            return True
            
        except Exception as e:
            logger.error(f"Error pausing subscription: {e}")
            return False
    
    def resume_subscription(self, subscription_id: str) -> bool:
        """Resume paused subscription."""
        
        try:
            subscription = self.get_subscription(subscription_id)
            if not subscription:
                return False
            
            if subscription.status != SubscriptionStatus.SUSPENDED:
                return False
            
            subscription.status = SubscriptionStatus.ACTIVE
            if subscription.metadata and 'pause_end_date' in subscription.metadata:
                del subscription.metadata['pause_end_date']
            
            logger.info(f"Resumed subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resuming subscription: {e}")
            return False
    
    def get_user_subscription(self, user_id: str) -> Optional[Subscription]:
        """Get user's active subscription."""
        
        try:
            # This would typically query the database
            # For now, simulate finding subscription
            
            # Simulate subscription check
            subscriptions = self._get_all_subscriptions()
            for sub in subscriptions:
                if sub.user_id == user_id and sub.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
                    return sub
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user subscription: {e}")
            return None
    
    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get subscription by ID."""
        
        try:
            subscriptions = self._get_all_subscriptions()
            for sub in subscriptions:
                if sub.subscription_id == subscription_id:
                    return sub
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            return None
    
    def _get_all_subscriptions(self) -> List[Subscription]:
        """Get all subscriptions (simulated)."""
        
        # This would typically query the database
        # For now, return empty list
        return []
    
    def update_subscription(self, subscription_id: str, updates: Dict[str, Any]) -> bool:
        """Update subscription details."""
        
        try:
            subscription = self.get_subscription(subscription_id)
            if not subscription:
                return False
            
            # Update fields
            for key, value in updates.items():
                if hasattr(subscription, key):
                    setattr(subscription, key, value)
            
            logger.info(f"Updated subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            return False
    
    def process_renewal(self, subscription_id: str) -> bool:
        """Process subscription renewal."""
        
        try:
            subscription = self.get_subscription(subscription_id)
            if not subscription:
                return False
            
            if not subscription.auto_renew:
                subscription.status = SubscriptionStatus.EXPIRED
                logger.info(f"Subscription {subscription_id} expired - auto-renew disabled")
                return False
            
            # Check payment method
            # This would typically process payment
            payment_successful = True  # Simulate successful payment
            
            if payment_successful:
                # Extend subscription
                if subscription.billing_cycle == BillingCycle.MONTHLY:
                    new_end_date = subscription.end_date + timedelta(days=30)
                elif subscription.billing_cycle == BillingCycle.QUARTERLY:
                    new_end_date = subscription.end_date + timedelta(days=90)
                else:  # ANNUAL
                    new_end_date = subscription.end_date + timedelta(days=365)
                
                subscription.end_date = new_end_date
                subscription.next_billing_date = new_end_date
                subscription.status = SubscriptionStatus.ACTIVE
                
                logger.info(f"Renewed subscription {subscription_id}")
                return True
            else:
                subscription.status = SubscriptionStatus.EXPIRED
                logger.warning(f"Payment failed for subscription {subscription_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing renewal: {e}")
            return False
    
    def check_trial_expiration(self) -> List[Subscription]:
        """Check for expiring trials."""
        
        try:
            expiring_trials = []
            subscriptions = self._get_all_subscriptions()
            
            for sub in subscriptions:
                if (sub.status == SubscriptionStatus.TRIAL and 
                    sub.trial_end_date and 
                    sub.trial_end_date <= datetime.now()):
                    
                    # Convert trial to active or expired
                    if sub.amount > 0:
                        sub.status = SubscriptionStatus.ACTIVE
                    else:
                        sub.status = SubscriptionStatus.EXPIRED
                    
                    expiring_trials.append(sub)
            
            return expiring_trials
            
        except Exception as e:
            logger.error(f"Error checking trial expiration: {e}")
            return []
    
    def get_usage_limits(self, user_id: str) -> Dict[str, Any]:
        """Get user's usage limits based on subscription."""
        
        try:
            subscription = self.get_user_subscription(user_id)
            
            if not subscription:
                # Default to basic plan limits
                plan = self.plans[PlanType.BASIC]
            else:
                plan = self.plans[subscription.plan_type]
            
            return {
                'plan_type': subscription.plan_type.value if subscription else 'basic',
                'limits': plan.limits,
                'features': plan.features,
                'status': subscription.status.value if subscription else 'inactive'
            }
            
        except Exception as e:
            logger.error(f"Error getting usage limits: {e}")
            return {}
    
    def check_usage_limit(self, user_id: str, resource: str, usage_amount: int = 1) -> bool:
        """Check if user has exceeded usage limits."""
        
        try:
            limits = self.get_usage_limits(user_id)
            
            if resource in limits['limits']:
                limit = limits['limits'][resource]
                
                if limit == float('inf'):
                    return True
                
                # Get current usage (would typically query database)
                current_usage = self._get_current_usage(user_id, resource)
                
                return current_usage + usage_amount <= limit
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking usage limit: {e}")
            return True
    
    def _get_current_usage(self, user_id: str, resource: str) -> int:
        """Get current usage for a resource."""
        
        # This would typically query the database
        # For now, return simulated usage
        usage_map = {
            'listings': 5,
            'api_calls': 100,
            'analytics_reports': 2,
            'leads': 3
        }
        
        return usage_map.get(resource, 0)
    
    def _is_upgrade(self, current_plan: PlanType, new_plan: PlanType) -> bool:
        """Check if new plan is an upgrade."""
        
        plan_hierarchy = {
            PlanType.BASIC: 0,
            PlanType.FEATURED: 1,
            PlanType.PREMIUM: 2,
            PlanType.ENTERPRISE: 3
        }
        
        return plan_hierarchy[new_plan] > plan_hierarchy[current_plan]
    
    def _is_downgrade(self, current_plan: PlanType, new_plan: PlanType) -> bool:
        """Check if new plan is a downgrade."""
        
        plan_hierarchy = {
            PlanType.BASIC: 0,
            PlanType.FEATURED: 1,
            PlanType.PREMIUM: 2,
            PlanType.ENTERPRISE: 3
        }
        
        return plan_hierarchy[new_plan] < plan_hierarchy[current_plan]
    
    def _calculate_discount(self, 
                          user_id: str,
                          plan_type: PlanType,
                          billing_cycle: BillingCycle,
                          promo_code: Optional[str] = None) -> float:
        """Calculate discount for subscription."""
        
        total_discount = 0.0
        
        # Annual billing discount
        if billing_cycle == BillingCycle.ANNUAL:
            total_discount += self.discounts['annual_discount']
        
        # Promotional discount
        if promo_code and promo_code in self.discounts:
            total_discount += self.discounts[promo_code]
        
        # Volume discount (would check user's organization size)
        # For now, simulate
        if plan_type in [PlanType.ENTERPRISE]:
            total_discount += self.discounts['volume_discount']
        
        # Loyalty discount (would check subscription history)
        # For now, simulate
        total_discount += self.discounts['loyalty_discount'] * 0.5  # 50% chance
        
        return min(total_discount, 0.5)  # Cap at 50%
    
    def get_subscription_analytics(self, period: str = 'month') -> Dict[str, Any]:
        """Get subscription analytics."""
        
        try:
            # This would typically query the database
            # For now, return simulated analytics
            
            analytics = {
                'period': period,
                'total_subscriptions': 150,
                'active_subscriptions': 120,
                'trial_subscriptions': 15,
                'cancelled_subscriptions': 15,
                'mrr': 2500.0,
                'arr': 30000.0,
                'churn_rate': 0.05,
                'trial_conversion_rate': 0.6,
                'plan_distribution': {
                    'basic': 50,
                    'featured': 60,
                    'premium': 30,
                    'enterprise': 10
                },
                'billing_cycle_distribution': {
                    'monthly': 120,
                    'quarterly': 20,
                    'annual': 10
                },
                'revenue_by_plan': {
                    'basic': 0.0,
                    'featured': 599.4,
                    'premium': 599.7,
                    'enterprise': 999.0
                }
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting subscription analytics: {e}")
            return {}
    
    def get_plan_comparison(self) -> Dict[str, Any]:
        """Get comparison of all subscription plans."""
        
        try:
            comparison = {
                'plans': []
            }
            
            for plan_type, plan in self.plans.items():
                plan_info = {
                    'type': plan_type.value,
                    'name': plan.name,
                    'description': plan.description,
                    'monthly_price': plan.monthly_price,
                    'annual_price': plan.annual_price,
                    'annual_savings': ((plan.monthly_price * 12 - plan.annual_price) / (plan.monthly_price * 12)) * 100 if plan.monthly_price > 0 else 0,
                    'features': plan.features,
                    'trial_days': plan.trial_days,
                    'limits': plan.limits
                }
                comparison['plans'].append(plan_info)
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error getting plan comparison: {e}")
            return {}
    
    def generate_subscription_report(self, user_id: str) -> Dict[str, Any]:
        """Generate subscription report for a user."""
        
        try:
            subscription = self.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    'user_id': user_id,
                    'status': 'no_subscription',
                    'recommendations': ['Consider starting with our Featured plan']
                }
            
            plan = self.plans[subscription.plan_type]
            
            report = {
                'user_id': user_id,
                'subscription_id': subscription.subscription_id,
                'plan': {
                    'type': subscription.plan_type.value,
                    'name': plan.name,
                    'billing_cycle': subscription.billing_cycle.value,
                    'amount': subscription.amount,
                    'status': subscription.status.value
                },
                'dates': {
                    'start_date': subscription.start_date.isoformat(),
                    'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                    'next_billing': subscription.next_billing_date.isoformat(),
                    'trial_end': subscription.trial_end_date.isoformat() if subscription.trial_end_date else None
                },
                'usage': self.get_usage_limits(user_id),
                'recommendations': self._get_subscription_recommendations(subscription)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating subscription report: {e}")
            return {'error': str(e)}
    
    def _get_subscription_recommendations(self, subscription: Subscription) -> List[str]:
        """Get recommendations based on subscription."""
        
        recommendations = []
        
        if subscription.plan_type == PlanType.BASIC:
            recommendations.append("Upgrade to Featured plan for better visibility")
            recommendations.append("Consider Premium plan for unlimited listings")
        elif subscription.plan_type == PlanType.FEATURED:
            recommendations.append("Upgrade to Premium for API access")
            recommendations.append("Consider annual billing for 20% savings")
        elif subscription.plan_type == PlanType.PREMIUM:
            recommendations.append("Upgrade to Enterprise for unlimited leads")
            recommendations.append("Add more users to your organization")
        
        if subscription.billing_cycle == BillingCycle.MONTHLY:
            recommendations.append("Switch to annual billing for 20% savings")
        
        return recommendations
