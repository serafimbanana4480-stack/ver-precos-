"""
Payment processor for monetization system.
"""
import stripe
import paypal
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PaymentMethod(Enum):
    """Payment methods available."""
    STRIPE = "stripe"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    MBWAY = "mbway"


class PaymentStatus(Enum):
    """Payment status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PlanType(Enum):
    """Subscription plan types."""
    BASIC = "basic"
    FEATURED = "featured"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class PaymentRequest:
    """Payment request data."""
    user_id: str
    amount: float
    currency: str = "EUR"
    payment_method: PaymentMethod = PaymentMethod.STRIPE
    description: str = ""
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SubscriptionRequest:
    """Subscription request data."""
    user_id: str
    plan_type: PlanType
    payment_method: PaymentMethod = PaymentMethod.STRIPE
    trial_days: int = 0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PaymentResult:
    """Payment result data."""
    success: bool
    payment_id: Optional[str] = None
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    status: PaymentStatus = PaymentStatus.PENDING
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentProcessor:
    """Payment processor for VER PRECOS monetization."""
    
    def __init__(self, stripe_secret_key: str, paypal_client_id: str, paypal_client_secret: str):
        """Initialize payment processor."""
        self.stripe_secret_key = stripe_secret_key
        self.paypal_client_id = paypal_client_id
        self.paypal_client_secret = paypal_client_secret
        
        # Initialize Stripe
        stripe.api_key = stripe_secret_key
        
        # Pricing configuration
        self.listing_prices = {
            PlanType.BASIC: 0.0,
            PlanType.FEATURED: 9.99,
            PlanType.PREMIUM: 19.99,
            PlanType.ENTERPRISE: 99.99
        }
        
        self.api_prices = {
            'starter': 29.99,
            'growth': 199.99,
            'enterprise': 999.99
        }
        
        self.analytics_prices = {
            PlanType.BASIC: 49.99,
            PlanType.PROFESSIONAL: 149.99,
            PlanType.ENTERPRISE: 499.99
        }
        
        self.lead_prices = {
            'basic': 5.00,
            'premium': 15.00,
            'exclusive': 50.00
        }
        
        logger.info("Payment processor initialized")
    
    async def process_listing_payment(self, request: PaymentRequest) -> PaymentResult:
        """Process payment for premium listing."""
        
        try:
            if request.payment_method == PaymentMethod.STRIPE:
                return await self._process_stripe_payment(request)
            elif request.payment_method == PaymentMethod.PAYPAL:
                return await self._process_paypal_payment(request)
            else:
                return PaymentResult(
                    success=False,
                    error_message=f"Unsupported payment method: {request.payment_method}"
                )
                
        except Exception as e:
            logger.error(f"Error processing listing payment: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def process_api_payment(self, user_id: str, api_credits: int, payment_method: PaymentMethod) -> PaymentResult:
        """Process payment for API credits."""
        
        try:
            # Calculate price based on credits
            price_per_credit = 0.10  # €0.10 per API call
            amount = api_credits * price_per_credit
            
            request = PaymentRequest(
                user_id=user_id,
                amount=amount,
                payment_method=payment_method,
                description=f"{api_credits} API credits",
                metadata={'credits': api_credits, 'type': 'api_payment'}
            )
            
            return await self.process_listing_payment(request)
            
        except Exception as e:
            logger.error(f"Error processing API payment: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def process_subscription(self, request: SubscriptionRequest) -> PaymentResult:
        """Process recurring subscription."""
        
        try:
            # Get plan price
            if request.plan_type in self.listing_prices:
                amount = self.listing_prices[request.plan_type]
            elif request.plan_type in self.analytics_prices:
                amount = self.analytics_prices[request.plan_type]
            else:
                return PaymentResult(
                    success=False,
                    error_message=f"Unknown plan type: {request.plan_type}"
                )
            
            if amount == 0:
                # Free plan - no payment needed
                return PaymentResult(
                    success=True,
                    status=PaymentStatus.COMPLETED,
                    amount=0.0,
                    metadata={'plan_type': request.plan_type.value, 'trial_days': request.trial_days}
                )
            
            if request.payment_method == PaymentMethod.STRIPE:
                return await self._create_stripe_subscription(request, amount)
            elif request.payment_method == PaymentMethod.PAYPAL:
                return await self._create_paypal_subscription(request, amount)
            else:
                return PaymentResult(
                    success=False,
                    error_message=f"Subscription not supported for {request.payment_method}"
                )
                
        except Exception as e:
            logger.error(f"Error processing subscription: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def process_lead_payment(self, user_id: str, lead_type: str, quantity: int, payment_method: PaymentMethod) -> PaymentResult:
        """Process payment for qualified leads."""
        
        try:
            if lead_type not in self.lead_prices:
                return PaymentResult(
                    success=False,
                    error_message=f"Unknown lead type: {lead_type}"
                )
            
            price_per_lead = self.lead_prices[lead_type]
            amount = price_per_lead * quantity
            
            request = PaymentRequest(
                user_id=user_id,
                amount=amount,
                payment_method=payment_method,
                description=f"{quantity} {lead_type} leads",
                metadata={'lead_type': lead_type, 'quantity': quantity}
            )
            
            return await self.process_listing_payment(request)
            
        except Exception as e:
            logger.error(f"Error processing lead payment: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def _process_stripe_payment(self, request: PaymentRequest) -> PaymentResult:
        """Process payment via Stripe."""
        
        try:
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(request.amount * 100),  # Convert to cents
                currency=request.currency,
                description=request.description,
                metadata=request.metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            
            return PaymentResult(
                success=True,
                payment_id=intent.id,
                amount=request.amount,
                status=PaymentStatus.PENDING,
                metadata={'client_secret': intent.client_secret}
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def _process_paypal_payment(self, request: PaymentRequest) -> PaymentResult:
        """Process payment via PayPal."""
        
        try:
            # Create PayPal payment
            # This is a simplified implementation
            payment_data = {
                'intent': 'sale',
                'payer': {
                    'payment_method': 'paypal'
                },
                'transactions': [{
                    'amount': {
                        'total': str(request.amount),
                        'currency': request.currency
                    },
                    'description': request.description
                }]
            }
            
            # In production, use PayPal SDK
            payment_id = f"paypal_{datetime.now().timestamp()}"
            
            return PaymentResult(
                success=True,
                payment_id=payment_id,
                amount=request.amount,
                status=PaymentStatus.PENDING,
                metadata={'paypal_redirect_url': f"https://paypal.com/pay/{payment_id}"}
            )
            
        except Exception as e:
            logger.error(f"PayPal error: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def _create_stripe_subscription(self, request: SubscriptionRequest, amount: float) -> PaymentResult:
        """Create Stripe subscription."""
        
        try:
            # Create product if not exists
            product_name = f"VER PRECOS {request.plan_type.value.title()} Plan"
            
            # Create price
            price = stripe.Price.create(
                unit_amount=int(amount * 100),
                currency='eur',
                recurring={'interval': 'month'},
                product_data={'name': product_name}
            )
            
            # Create customer
            customer = stripe.Customer.create(
                metadata={'user_id': request.user_id}
            )
            
            # Create subscription
            subscription_data = {
                'customer': customer.id,
                'items': [{'price': price.id}],
                'metadata': {'user_id': request.user_id, 'plan_type': request.plan_type.value}
            }
            
            if request.trial_days > 0:
                subscription_data['trial_period_days'] = request.trial_days
            
            subscription = stripe.Subscription.create(**subscription_data)
            
            return PaymentResult(
                success=True,
                payment_id=subscription.id,
                amount=amount,
                status=PaymentStatus.COMPLETED,
                metadata={
                    'subscription_id': subscription.id,
                    'customer_id': customer.id,
                    'plan_type': request.plan_type.value
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription error: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def _create_paypal_subscription(self, request: SubscriptionRequest, amount: float) -> PaymentResult:
        """Create PayPal subscription."""
        
        try:
            # Create PayPal subscription
            subscription_id = f"paypal_sub_{datetime.now().timestamp()}"
            
            return PaymentResult(
                success=True,
                payment_id=subscription_id,
                amount=amount,
                status=PaymentStatus.PENDING,
                metadata={
                    'subscription_id': subscription_id,
                    'plan_type': request.plan_type.value,
                    'paypal_redirect_url': f"https://paypal.com/subscribe/{subscription_id}"
                }
            )
            
        except Exception as e:
            logger.error(f"PayPal subscription error: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> PaymentResult:
        """Refund a payment."""
        
        try:
            if payment_id.startswith('pi_'):  # Stripe payment intent
                refund = stripe.Refund.create(
                    payment_intent=payment_id,
                    amount=int(amount * 100) if amount else None
                )
                
                return PaymentResult(
                    success=True,
                    payment_id=refund.id,
                    amount=amount,
                    status=PaymentStatus.REFUNDED,
                    metadata={'refund_id': refund.id}
                )
            else:
                return PaymentResult(
                    success=False,
                    error_message="Refund not supported for this payment method"
                )
                
        except stripe.error.StripeError as e:
            logger.error(f"Refund error: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def cancel_subscription(self, subscription_id: str) -> PaymentResult:
        """Cancel a subscription."""
        
        try:
            if subscription_id.startswith('sub_'):  # Stripe subscription
                subscription = stripe.Subscription.delete(subscription_id)
                
                return PaymentResult(
                    success=True,
                    payment_id=subscription_id,
                    status=PaymentStatus.CANCELLED,
                    metadata={'subscription_status': subscription.status}
                )
            else:
                return PaymentResult(
                    success=False,
                    error_message="Cancellation not supported for this subscription type"
                )
                
        except stripe.error.StripeError as e:
            logger.error(f"Subscription cancellation error: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def get_payment_status(self, payment_id: str) -> PaymentResult:
        """Get payment status."""
        
        try:
            if payment_id.startswith('pi_'):  # Stripe payment intent
                intent = stripe.PaymentIntent.retrieve(payment_id)
                
                status_map = {
                    'requires_payment_method': PaymentStatus.PENDING,
                    'requires_confirmation': PaymentStatus.PENDING,
                    'requires_action': PaymentStatus.PENDING,
                    'processing': PaymentStatus.PROCESSING,
                    'succeeded': PaymentStatus.COMPLETED,
                    'canceled': PaymentStatus.CANCELLED
                }
                
                return PaymentResult(
                    success=True,
                    payment_id=payment_id,
                    amount=intent.amount / 100,
                    status=status_map.get(intent.status, PaymentStatus.PENDING),
                    metadata={'status': intent.status}
                )
            else:
                return PaymentResult(
                    success=False,
                    error_message="Payment status not available"
                )
                
        except stripe.error.StripeError as e:
            logger.error(f"Payment status error: {e}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    def get_plan_pricing(self, plan_type: str, service_type: str = 'listing') -> Dict[str, Any]:
        """Get pricing for a specific plan."""
        
        if service_type == 'listing':
            prices = self.listing_prices
        elif service_type == 'analytics':
            prices = self.analytics_prices
        else:
            return {'error': f'Unknown service type: {service_type}'}
        
        plan_enum = PlanType(plan_type.lower()) if plan_type.lower() in [p.value for p in PlanType] else None
        
        if plan_enum and plan_enum in prices:
            return {
                'plan_type': plan_type,
                'price': prices[plan_enum],
                'currency': 'EUR',
                'billing_interval': 'monthly'
            }
        else:
            return {'error': f'Unknown plan type: {plan_type}'}
    
    def calculate_api_cost(self, api_calls: int, plan_type: str = 'starter') -> Dict[str, Any]:
        """Calculate API usage cost."""
        
        if plan_type not in self.api_prices:
            return {'error': f'Unknown API plan: {plan_type}'}
        
        base_price = self.api_prices[plan_type]
        included_calls = {'starter': 1000, 'growth': 10000, 'enterprise': 100000}.get(plan_type, 0)
        
        if api_calls <= included_calls:
            return {
                'plan_type': plan_type,
                'api_calls': api_calls,
                'included_calls': included_calls,
                'additional_calls': 0,
                'total_cost': base_price
            }
        else:
            additional_calls = api_calls - included_calls
            cost_per_call = 0.05  # €0.05 per additional call
            additional_cost = additional_calls * cost_per_call
            total_cost = base_price + additional_cost
            
            return {
                'plan_type': plan_type,
                'api_calls': api_calls,
                'included_calls': included_calls,
                'additional_calls': additional_calls,
                'cost_per_call': cost_per_call,
                'additional_cost': additional_cost,
                'total_cost': total_cost
            }
    
    def get_payment_methods(self) -> List[Dict[str, Any]]:
        """Get available payment methods."""
        
        return [
            {
                'id': PaymentMethod.STRIPE.value,
                'name': 'Stripe',
                'description': 'Credit/Debit Card',
                'enabled': True,
                'fees': '2.9% + €0.30'
            },
            {
                'id': PaymentMethod.PAYPAL.value,
                'name': 'PayPal',
                'description': 'PayPal Account',
                'enabled': True,
                'fees': '2.9% + €0.35'
            },
            {
                'id': PaymentMethod.MBWAY.value,
                'name': 'MB WAY',
                'description': 'Mobile Payment',
                'enabled': False,
                'fees': 'Coming soon'
            },
            {
                'id': PaymentMethod.BANK_TRANSFER.value,
                'name': 'Bank Transfer',
                'description': 'Direct Bank Transfer',
                'enabled': False,
                'fees': 'Free'
            }
        ]
    
    async def create_payment_link(self, request: PaymentRequest) -> str:
        """Create payment link for sharing."""
        
        try:
            if request.payment_method == PaymentMethod.STRIPE:
                # Create Stripe payment link
                price_data = {
                    'unit_amount': int(request.amount * 100),
                    'currency': request.currency,
                    'product_data': {
                        'name': request.description or 'VER PRECOS Payment',
                    }
                }
                
                price = stripe.Price.create(price_data)
                
                payment_link = stripe.PaymentLink.create(
                    prices=[price.id],
                    metadata=request.metadata or {}
                )
                
                return payment_link.url
            else:
                # Generate generic payment link
                return f"https://verprecos.com/pay?amount={request.amount}&method={request.payment_method.value}"
                
        except Exception as e:
            logger.error(f"Error creating payment link: {e}")
            return ""
    
    async def validate_webhook(self, payload: bytes, signature: str, endpoint_secret: str) -> Dict[str, Any]:
        """Validate webhook signature."""
        
        try:
            if endpoint_secret.startswith('whsec_'):  # Stripe webhook
                event = stripe.Webhook.construct_event(
                    payload, signature, endpoint_secret
                )
                
                return {
                    'valid': True,
                    'event_type': event.type,
                    'event_data': event.data
                }
            else:
                return {'valid': False, 'error': 'Unknown webhook type'}
                
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook validation error: {e}")
            return {'valid': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return {'valid': False, 'error': str(e)}
