"""
Deal Profit Calculator
Unified profit analysis integrating Pricing and Scoring engines
"""
from __future__ import annotations
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from config import settings
from intelligence.pricing.engine import pricing_engine
from intelligence.scoring.engine import scoring_engine

logger = logging.getLogger(__name__)


@dataclass
class DealProfitAnalysis:
    """Complete deal profit analysis result."""
    # Price information
    listing_price: float
    estimated_market_price: float
    price_discount_percentage: float
    estimated_savings: float
    
    # Buyer profit (if buying this deal)
    buyer_profit: float
    buyer_profit_margin: float
    buyer_roi: float
    buyer_payback_months: Optional[float]
    
    # Seller profit (if selling this vehicle)
    seller_profit: Optional[float]
    seller_profit_margin: Optional[float]
    seller_roi: Optional[float]
    
    # Cost breakdown
    repair_costs: float
    taxes: float
    total_additional_costs: float
    
    # Risk assessment
    risk_score: float
    risk_level: str
    
    # Overall deal quality
    deal_score: float
    deal_grade: str
    recommendation: str
    
    # Metadata
    calculated_at: str
    calculation_method: str


class DealProfitCalculator:
    """
    Unified deal profit calculator integrating Pricing and Scoring engines.

    Profit definitions (aligned with HybridValuator):
    - buyer_profit / profit_potential: GROSS spread (estimated_market_value - asking_price).
      Used for ranking/scoring. Does NOT include acquisition costs.
    - net_profit: REALISTIC profit after Portugal vehicle transfer taxes,
      computed via valuation.pt_fiscal.calculate_transaction_costs() (2026
      official tables: registo de propriedade 55,30 € + IPO; ISV only for
      imports), and estimated repair costs based on condition.
    """
    
    def __init__(self):
        """Initialize deal profit calculator."""
        self.pricing_engine = pricing_engine
        self.scoring_engine = scoring_engine
        
        # Repair cost estimates by condition score bucket (EUR)
        # Aligned with HybridValuator._REPAIR_COST_BY_CONDITION
        self.repair_cost_estimates = {
            'excellent': 0,      # condition >= 8
            'good': 500,         # condition >= 6
            'fair': 1500,        # condition >= 4
            'poor': 3000,        # condition >= 2
            'very_poor': 5000,   # condition < 2
            'unknown': 1000
        }
        
        logger.info("Deal profit calculator initialized")
    
    # Tipos de preço que representam de facto o custo total de aquisição.
    # Tudo o resto (base de leilão, mensalidade, entrada) não é comparável
    # com um valor de mercado retail e não pode gerar profit.
    RETAIL_PRICE_KINDS = frozenset({'total', 'retail', None, ''})

    @staticmethod
    def _has_retail_price(vehicle: Dict[str, Any]) -> bool:
        """True apenas quando o preço é um valor retail total e positivo."""
        price = vehicle.get('price') or 0
        if price <= 0:
            return False
        kind = vehicle.get('price_kind')
        if kind not in DealProfitCalculator.RETAIL_PRICE_KINDS:
            return False
        if vehicle.get('price_rejection_reason'):
            return False
        return True

    def _no_price_analysis(self, vehicle: Dict[str, Any]) -> DealProfitAnalysis:
        """Análise neutra para viaturas sem preço retail utilizável.

        Todos os campos de profit ficam a 0.0 e o grade a ``'N/A'`` — nunca
        um número que possa ser somado, ordenado ou apresentado como lucro.
        """
        kind = vehicle.get('price_kind') or 'desconhecido'
        return DealProfitAnalysis(
            listing_price=0.0,
            estimated_market_price=0.0,
            price_discount_percentage=0.0,
            estimated_savings=0.0,
            buyer_profit=0.0,
            buyer_profit_margin=0.0,
            buyer_roi=0.0,
            buyer_payback_months=None,
            seller_profit=None,
            seller_profit_margin=None,
            seller_roi=None,
            repair_costs=0.0,
            taxes=0.0,
            total_additional_costs=0.0,
            risk_score=vehicle.get('ai_risk_score', 5.0) or 5.0,
            risk_level='unknown',
            deal_score=0.0,
            deal_grade='N/A',
            recommendation=(
                f'Sem preço retail (price_kind={kind}) — profit não calculável. '
                'Requer preço final de venda para avaliação.'
            ),
            calculated_at=datetime.utcnow().isoformat(),
            calculation_method='no_retail_price_gate',
        )

    def calculate_deal_profit(self, vehicle: Dict[str, Any]) -> DealProfitAnalysis:
        """
        Calculate complete deal profit analysis
        
        Args:
            vehicle: Vehicle dictionary with all necessary fields
            
        Returns:
            DealProfitAnalysis with complete profit breakdown
        """
        try:
            # === PORTA DE PREÇO RETAIL ===
            # Sem preço retail não existe profit. Antes desta guarda, viaturas
            # de leilão (price=0, price_kind='auction_start') produziam
            # buyer_profit = estimated_value - 0, gerando 5,4 M€ de lucro
            # fantasma em 990 registos. Ver valuation/reliability.py.
            if not self._has_retail_price(vehicle):
                return self._no_price_analysis(vehicle)

            # Get pricing analysis
            pricing_result = self.pricing_engine.calculate_price(vehicle)
            estimated_value = pricing_result.get('final_price')
            if estimated_value is None:
                estimated_value = vehicle.get('price', 0) or 0

            # Get scoring analysis
            scoring_result = self.scoring_engine.calculate_final_score(vehicle)
            deal_score = scoring_result.final_score

            listing_price = vehicle.get('price', 0) or 0

            # Calculate price discount
            price_discount_percentage = self._calculate_price_discount_percentage(
                estimated_value, listing_price
            )
            estimated_savings = estimated_value - listing_price
            
            # Estimate repair costs based on condition
            condition_score = vehicle.get('condition_score', 6.0)
            repair_costs = self._estimate_repair_costs(condition_score)
            
            # Calculate taxes
            taxes = self._calculate_taxes(vehicle, listing_price)
            total_additional_costs = repair_costs + taxes
            
            # Calculate buyer profit
            buyer_profit, buyer_profit_margin, buyer_roi, buyer_payback_months = \
                self._calculate_buyer_profit(
                    listing_price, estimated_value, repair_costs, taxes
                )
            
            # Calculate seller profit (if original purchase price available)
            seller_profit, seller_profit_margin, seller_roi = \
                self._calculate_seller_profit(
                    listing_price, vehicle.get('original_purchase_price'), vehicle
                )
            
            # Determine risk level
            ai_risk_score = vehicle.get('ai_risk_score', 5.0)
            risk_level = self._determine_risk_level(ai_risk_score)
            
            # Determine deal grade and recommendation
            deal_grade = self._determine_deal_grade(deal_score)
            recommendation = self._generate_recommendation(
                deal_grade, price_discount_percentage, risk_level
            )
            
            return DealProfitAnalysis(
                listing_price=listing_price,
                estimated_market_price=estimated_value,
                price_discount_percentage=price_discount_percentage,
                estimated_savings=estimated_savings,
                buyer_profit=buyer_profit,
                buyer_profit_margin=buyer_profit_margin,
                buyer_roi=buyer_roi,
                buyer_payback_months=buyer_payback_months,
                seller_profit=seller_profit,
                seller_profit_margin=seller_profit_margin,
                seller_roi=seller_roi,
                repair_costs=repair_costs,
                taxes=taxes,
                total_additional_costs=total_additional_costs,
                risk_score=ai_risk_score,
                risk_level=risk_level,
                deal_score=deal_score,
                deal_grade=deal_grade,
                recommendation=recommendation,
                calculated_at=datetime.utcnow().isoformat(),
                calculation_method='unified_pricing_scoring'
            )
            
        except Exception as e:
            logger.error(f"Error calculating deal profit: {e}")
            # Return neutral analysis on error
            return DealProfitAnalysis(
                listing_price=vehicle.get('price', 0),
                estimated_market_price=vehicle.get('price', 0),
                price_discount_percentage=0.0,
                estimated_savings=0.0,
                buyer_profit=0.0,
                buyer_profit_margin=0.0,
                buyer_roi=0.0,
                buyer_payback_months=None,
                seller_profit=None,
                seller_profit_margin=None,
                seller_roi=None,
                repair_costs=0.0,
                taxes=0.0,
                total_additional_costs=0.0,
                risk_score=5.0,
                risk_level='medium',
                deal_score=5.0,
                deal_grade='fair',
                recommendation='Calculation error - manual review needed',
                calculated_at=datetime.utcnow().isoformat(),
                calculation_method='error_fallback'
            )
    
    def _calculate_price_discount_percentage(self, market_price: float, listing_price: float) -> float:
        """Calculate discount percentage."""
        if market_price <= 0:
            return 0.0
        discount = (market_price - listing_price) / market_price
        return max(-1.0, min(1.0, discount)) * 100  # Cap at -100% to +100%
    
    def _estimate_repair_costs(self, condition_score: float) -> float:
        """Estimate repair costs based on condition score (1-10)."""
        if condition_score >= 8:
            return self.repair_cost_estimates['excellent']
        elif condition_score >= 6:
            return self.repair_cost_estimates['good']
        elif condition_score >= 4:
            return self.repair_cost_estimates['fair']
        elif condition_score >= 2:
            return self.repair_cost_estimates['poor']
        else:
            return self.repair_cost_estimates['unknown']
    
    def _calculate_taxes(self, vehicle: Dict[str, Any], price: float) -> float:
        """Real Portuguese acquisition taxes (2026) via pt_fiscal.

        National used vehicle: registo de propriedade (55,30 € online) + IPO.
        ISV + legalização only apply to imports (is_import=True). IMT and
        stamp duty do NOT exist for vehicle sales.
        """
        from valuation.pt_fiscal import calculate_transaction_costs

        tc = calculate_transaction_costs(
            asking_price=float(price or 0.0),
            engine_cc=int(vehicle.get('engine_size') or vehicle.get('engine_cc') or 1500),
            co2_gkm=vehicle.get('co2_gkm'),
            fuel_type=vehicle.get('fuel_type') or 'gasolina',
            year=vehicle.get('year'),
            vehicle_type=vehicle.get('vehicle_type') or 'carros',
            is_national=not bool(vehicle.get('is_import', False)),
            condition_score=vehicle.get('condition_score'),
            repair_costs=0.0,  # repairs are tracked separately (repair_costs field)
        )
        # Tax component only: registo + ISV + legalização + IPO. Reconditioning
        # (tc.reconditioning) and annual IUC are NOT acquisition taxes and are
        # accounted elsewhere.
        return round(tc.registo_propriedade + tc.isv + tc.legalization + tc.ipo, 2)
    
    def _calculate_buyer_profit(self,
                               listing_price: float,
                               estimated_value: float,
                               repair_costs: float,
                               taxes: float) -> Tuple[float, float, float, Optional[float]]:
        """
        Calculate buyer profit metrics for deal evaluation.

        Note: For deal scoring purposes, profit is based on market value vs asking price.
        Taxes and repairs are tracked separately as additional costs, not subtracted
        from the deal profit potential (which measures how good the price is relative
        to the market, not total cost of ownership).

        Returns:
            (profit, profit_margin, roi, payback_months)
        """
        if listing_price <= 0 or estimated_value <= 0:
            return 0.0, 0.0, 0.0, None

        # Deal profit = estimated market value - asking price
        # This measures the intrinsic discount vs market, before ownership costs
        profit = estimated_value - listing_price

        # Profit margin relative to estimated value
        profit_margin = (profit / estimated_value) * 100 if estimated_value > 0 else 0

        # ROI relative to asking price
        roi = (profit / listing_price) * 100 if listing_price > 0 else 0

        # Payback not meaningful for vehicle deals; return None
        payback_months = None

        return round(profit, 2), round(profit_margin, 2), round(roi, 2), payback_months
    
    def _calculate_seller_profit(self, 
                                 listing_price: float, 
                                 original_purchase_price: Optional[float],
                                 vehicle: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate seller profit metrics
        
        Returns:
            (profit, profit_margin, roi) or (None, None, None) if original price not available
        """
        if original_purchase_price is None or original_purchase_price <= 0:
            return None, None, None
        
        # Profit = listing price - original purchase price - taxes
        taxes = self._calculate_taxes(vehicle, listing_price)
        profit = listing_price - original_purchase_price - taxes
        
        # Profit margin = profit / listing price
        profit_margin = (profit / listing_price) * 100 if listing_price > 0 else 0
        
        # ROI = profit / original_purchase_price
        roi = (profit / original_purchase_price) * 100 if original_purchase_price > 0 else 0
        
        return round(profit, 2), round(profit_margin, 2), round(roi, 2)
    
    def _determine_risk_level(self, ai_risk_score: float) -> str:
        """Determine risk level from AI risk score (1-10)."""
        if ai_risk_score <= 3:
            return 'low'
        elif ai_risk_score <= 5:
            return 'medium'
        elif ai_risk_score <= 7:
            return 'high'
        else:
            return 'very_high'
    
    def _determine_deal_grade(self, deal_score: float) -> str:
        """Determine deal grade from deal score (0-10).
        Thresholds aligned with robust pricing v6."""
        if deal_score >= 8.5:
            return 'exceptional'
        elif deal_score >= 7.5:
            return 'excellent'
        elif deal_score >= 6.0:
            return 'good'
        elif deal_score >= 4.5:
            return 'fair'
        else:
            return 'poor'
    
    def _generate_recommendation(self,
                                 deal_grade: str,
                                 discount_percentage: float,
                                 risk_level: str) -> str:
        """Generate recommendation based on deal quality.
        Aligned with robust pricing v6 — uses deal_grade as primary signal."""
        if risk_level == 'very_high':
            return 'HIGH RISK - Avoid or inspect thoroughly'
        elif deal_grade == 'exceptional':
            return 'EXCELLENT DEAL - Strong buy recommendation'
        elif deal_grade == 'excellent':
            return 'GOOD DEAL - Consider purchasing'
        elif deal_grade == 'good':
            return 'FAIR DEAL - Worth considering'
        elif deal_grade == 'fair':
            return 'NEUTRAL - Negotiate if possible'
        else:
            return 'OVERPRICED - Avoid or inspect thoroughly'
    
    def calculate_portfolio_profit(self, vehicles: list) -> Dict[str, Any]:
        """
        Calculate profit analysis for a portfolio of vehicles
        
        Args:
            vehicles: List of vehicle dictionaries
            
        Returns:
            Portfolio profit analysis summary
        """
        try:
            analyses = []
            total_buyer_profit = 0.0
            total_estimated_savings = 0.0
            excellent_deals = 0
            good_deals = 0
            
            for vehicle in vehicles:
                analysis = self.calculate_deal_profit(vehicle)
                analyses.append(analysis)
                
                total_buyer_profit += analysis.buyer_profit
                total_estimated_savings += analysis.estimated_savings
                
                if analysis.deal_grade in ['exceptional', 'excellent']:
                    excellent_deals += 1
                elif analysis.deal_grade in ['very_good', 'good']:
                    good_deals += 1
            
            return {
                'total_vehicles': len(vehicles),
                'total_buyer_profit': round(total_buyer_profit, 2),
                'total_estimated_savings': round(total_estimated_savings, 2),
                'average_buyer_profit': round(total_buyer_profit / len(vehicles), 2) if vehicles else 0,
                'excellent_deals': excellent_deals,
                'good_deals': good_deals,
                'deal_quality_distribution': {
                    'exceptional': sum(1 for a in analyses if a.deal_grade == 'exceptional'),
                    'excellent': sum(1 for a in analyses if a.deal_grade == 'excellent'),
                    'very_good': sum(1 for a in analyses if a.deal_grade == 'very_good'),
                    'good': sum(1 for a in analyses if a.deal_grade == 'good'),
                    'fair': sum(1 for a in analyses if a.deal_grade == 'fair'),
                    'poor': sum(1 for a in analyses if a.deal_grade == 'poor')
                },
                'calculated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio profit: {e}")
            return {'error': str(e)}


# Singleton instance
deal_profit_calculator = DealProfitCalculator()
