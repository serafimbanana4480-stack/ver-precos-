"""
Relevance scoring for search results
Based on Obsidian Vault documentation for Hub - Search
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RelevanceScorer:
    """Calculate relevance scores for search results"""
    
    def __init__(
        self,
        deal_score_weight: float = 0.4,
        recency_weight: float = 0.2,
        price_weight: float = 0.2,
        completeness_weight: float = 0.2
    ):
        self.deal_score_weight = deal_score_weight
        self.recency_weight = recency_weight
        self.price_weight = price_weight
        self.completeness_weight = completeness_weight
    
    def calculate_relevance_score(
        self,
        vehicle: Dict[str, Any],
        query: str,
        base_score: float = 1.0
    ) -> float:
        """
        Calculate relevance score for a vehicle
        
        Args:
            vehicle: Vehicle data
            query: Search query
            base_score: Base relevance score from Elasticsearch
            
        Returns:
            Relevance score (0-1)
        """
        scores = {}
        
        # Deal score component
        scores['deal_score'] = self._score_deal_score(vehicle)
        
        # Recency component
        scores['recency'] = self._score_recency(vehicle)
        
        # Price component
        scores['price'] = self._score_price(vehicle)
        
        # Completeness component
        scores['completeness'] = self._score_completeness(vehicle)
        
        # Query matching component
        scores['query_match'] = self._score_query_match(vehicle, query)
        
        # Weighted sum
        relevance = (
            self.deal_score_weight * scores['deal_score'] +
            self.recency_weight * scores['recency'] +
            self.price_weight * scores['price'] +
            self.completeness_weight * scores['completeness']
        ) * base_score
        
        logger.debug(f"Relevance scores for {vehicle.get('source_id')}: {scores} -> {relevance}")
        return relevance
    
    def _score_deal_score(self, vehicle: Dict[str, Any]) -> float:
        """Score based on deal score (0-10 scale)"""
        deal_score = vehicle.get('deal_score', 0)
        return min(deal_score / 10.0, 1.0)
    
    def _score_recency(self, vehicle: Dict[str, Any]) -> float:
        """Score based on how recently the vehicle was seen"""
        last_seen = vehicle.get('last_seen')
        if not last_seen:
            return 0.5
        
        if isinstance(last_seen, str):
            last_seen = datetime.fromisoformat(last_seen)
        
        # Calculate days since last seen
        days_old = (datetime.now() - last_seen).days
        
        # Decay function: newer is better
        # 0 days old = 1.0, 30 days old = 0.5, 60+ days old = 0.0
        if days_old < 7:
            return 1.0
        elif days_old < 30:
            return 0.7
        elif days_old < 60:
            return 0.4
        else:
            return 0.1
    
    def _score_price(self, vehicle: Dict[str, Any]) -> float:
        """Score based on price competitiveness"""
        price = vehicle.get('price', 0)
        estimated_value = vehicle.get('estimated_value')
        
        if not estimated_value or estimated_value == 0:
            return 0.5
        
        # Calculate price deviation
        deviation = (estimated_value - price) / estimated_value
        
        # Positive deviation (below market value) is good
        # Negative deviation (above market value) is bad
        if deviation > 0.2:  # 20% below market
            return 1.0
        elif deviation > 0.1:  # 10% below market
            return 0.8
        elif deviation > 0:  # Below market
            return 0.6
        elif deviation > -0.1:  # Within 10% of market
            return 0.5
        else:  # Above market
            return 0.3
    
    def _score_completeness(self, vehicle: Dict[str, Any]) -> float:
        """Score based on data completeness"""
        required_fields = [
            'brand', 'model', 'year', 'price', 'km',
            'fuel_type', 'transmission', 'location'
        ]
        
        optional_fields = [
            'description', 'images', 'condition_score',
            'horsepower', 'engine_size', 'color', 'doors'
        ]
        
        # Count required fields present
        required_present = sum(
            1 for field in required_fields
            if vehicle.get(field) is not None
        )
        required_score = required_present / len(required_fields)
        
        # Count optional fields present
        optional_present = sum(
            1 for field in optional_fields
            if vehicle.get(field) is not None
        )
        optional_score = optional_present / len(optional_fields)
        
        # Weighted combination
        return 0.7 * required_score + 0.3 * optional_score
    
    def _score_query_match(self, vehicle: Dict[str, Any], query: str) -> float:
        """Score based on query term matching"""
        if not query:
            return 1.0
        
        query_lower = query.lower()
        vehicle_text = ' '.join([
            str(vehicle.get('brand', '')),
            str(vehicle.get('model', '')),
            str(vehicle.get('title', '')),
            str(vehicle.get('description', ''))
        ]).lower()
        
        # Count matching terms
        query_terms = query_lower.split()
        matched_terms = sum(
            1 for term in query_terms
            if term in vehicle_text
        )
        
        if not query_terms:
            return 1.0
        
        return matched_terms / len(query_terms)
    
    def rerank_results(
        self,
        results: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results based on relevance scores
        
        Args:
            results: List of search results
            query: Search query
            
        Returns:
            Reranked results
        """
        scored_results = []
        
        for result in results:
            base_score = result.get('_score', 1.0)
            vehicle = result.get('_source', result)
            
            relevance = self.calculate_relevance_score(
                vehicle,
                query,
                base_score
            )
            
            result['relevance_score'] = relevance
            scored_results.append(result)
        
        # Sort by relevance score
        reranked = sorted(
            scored_results,
            key=lambda x: x['relevance_score'],
            reverse=True
        )
        
        logger.info(f"Reranked {len(results)} results")
        return reranked
    
    def explain_score(
        self,
        vehicle: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """
        Explain the relevance score for a vehicle
        
        Args:
            vehicle: Vehicle data
            query: Search query
            
        Returns:
            Score breakdown
        """
        return {
            'deal_score': self._score_deal_score(vehicle),
            'recency': self._score_recency(vehicle),
            'price': self._score_price(vehicle),
            'completeness': self._score_completeness(vehicle),
            'query_match': self._score_query_match(vehicle, query),
            'weights': {
                'deal_score': self.deal_score_weight,
                'recency': self.recency_weight,
                'price': self.price_weight,
                'completeness': self.completeness_weight
            }
        }


if __name__ == "__main__":
    # Test relevance scorer
    scorer = RelevanceScorer()
    
    vehicle = {
        'source_id': '123',
        'brand': 'Volkswagen',
        'model': 'Golf',
        'year': 2020,
        'price': 15000,
        'km': 50000,
        'fuel_type': 'diesel',
        'transmission': 'manual',
        'location': 'Lisboa',
        'deal_score': 8.5,
        'estimated_value': 18000,
        'last_seen': datetime.now(),
        'description': 'Golf em bom estado',
        'images': ['img1.jpg', 'img2.jpg'],
        'condition_score': 7.0
    }
    
    query = "golf diesel lisboa"
    
    relevance = scorer.calculate_relevance_score(vehicle, query)
    print(f"Relevance score: {relevance}")
    
    explanation = scorer.explain_score(vehicle, query)
    print(f"Score breakdown: {explanation}")
