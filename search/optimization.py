"""
Search optimization and query enhancement
Based on Obsidian Vault documentation for Hub - Search
"""
import logging
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger(__name__)


class SearchOptimizer:
    """Optimize search queries for better results"""
    
    # Common Portuguese car brand/model terms
    BRAND_SYNONYMS = {
        'vw': 'volkswagen',
        'bmw': 'bmw',
        'mercedes': 'mercedes-benz',
        'merc': 'mercedes-benz',
        'audi': 'audi',
        'seat': 'seat',
        'renault': 'renault',
        'peugeot': 'peugeot',
        'citroen': 'citroën',
        'fiat': 'fiat',
        'ford': 'ford',
        'opel': 'opel',
        'toyota': 'toyota',
        'nissan': 'nissan',
        'mazda': 'mazda',
        'hyundai': 'hyundai',
        'kia': 'kia',
        'dacia': 'dacia',
        'suzuki': 'suzuki',
        'honda': 'honda',
        'mini': 'mini'
    }
    
    # Common model patterns
    MODEL_PATTERNS = [
        r'golf', r'polo', r'passat', r'touran',
        r'serie \d', r'x\d', r'classe [abc]',
        r'a\d', r'leon', r'ibiza', r'arona',
        r'megane', r'clio', r'captur',
        r'208', r'308', r'2008',
        r'c\d', r'c3', r'c4',
        r'punto', r'500',
        r'focus', r'fiesta', r'puma',
        r'corsa', r'astra', r'insignia',
        r'yaris', r'corolla', r'auris',
        r'qashqai', r'juke', r'leaf',
        r'cx-5', r'cx-3', r'mx-5',
        r'i\d0', r'tucson', r'santa fe',
        r'ceed', r'sportage', r'picanto',
        r'sandero', r'duster', r'logan',
        r'jimny', r'vitara', r'swift',
        r'civic', r'cr-v', r'hr-v',
        r'countryman'
    ]
    
    @staticmethod
    def normalize_query(query: str) -> str:
        """
        Normalize search query
        
        Args:
            query: Original query
            
        Returns:
            Normalized query
        """
        # Convert to lowercase
        normalized = query.lower().strip()
        
        # Remove special characters
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Normalize brand names
        words = normalized.split()
        normalized_words = []
        for word in words:
            if word in SearchOptimizer.BRAND_SYNONYMS:
                normalized_words.append(SearchOptimizer.BRAND_SYNONYMS[word])
            else:
                normalized_words.append(word)
        
        return ' '.join(normalized_words)
    
    @staticmethod
    def extract_filters(query: str) -> Dict[str, Any]:
        """
        Extract filters from natural language query
        
        Args:
            query: Search query
            
        Returns:
            Dictionary of extracted filters
        """
        filters = {}
        normalized = query.lower()
        
        # Extract price range
        price_pattern = r'(?:preço|price)[:\s]*(\d+)[\s]*(?:a|to|até|-)[\s]*(\d+)'
        price_match = re.search(price_pattern, normalized)
        if price_match:
            filters['price'] = {
                'min': float(price_match.group(1)),
                'max': float(price_match.group(2))
            }
        
        # Extract year range
        year_pattern = r'(?:ano|year)[:\s]*(\d{4})[\s]*(?:a|to|até|-)[\s]*(\d{4})'
        year_match = re.search(year_pattern, normalized)
        if year_match:
            filters['year'] = {
                'min': int(year_match.group(1)),
                'max': int(year_match.group(2))
            }
        
        # Extract max km
        km_pattern = r'(?:km|quilómetros)[\s]*(?:máx|max|menos que|<)[:\s]*(\d+)'
        km_match = re.search(km_pattern, normalized)
        if km_match:
            filters['km'] = {'max': int(km_match.group(1))}
        
        # Extract fuel type
        fuel_keywords = {
            'gasolina': 'gasolina',
            'diesel': 'diesel',
            'elétrico': 'eletrico',
            'eletrico': 'eletrico',
            'híbrido': 'hibrido',
            'hibrido': 'hibrido',
            'gpl': 'gpl',
            'gas natural': 'gas natural'
        }
        for keyword, value in fuel_keywords.items():
            if keyword in normalized:
                filters['fuel_type'] = value
                break
        
        # Extract transmission
        if 'automático' in normalized or 'automatico' in normalized:
            filters['transmission'] = 'automatico'
        elif 'manual' in normalized:
            filters['transmission'] = 'manual'
        
        # Extract location
        location_pattern = r'(?:em|na|no)[\s]+([a-zãõáéíóúâêîôûç]+)'
        location_match = re.search(location_pattern, normalized)
        if location_match:
            filters['location'] = location_match.group(1).capitalize()
        
        return filters
    
    @staticmethod
    def build_elastic_query(
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        boost_fields: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Build optimized Elasticsearch query
        
        Args:
            query: Search query
            filters: Optional filters
            boost_fields: Field boost weights
            
        Returns:
            Elasticsearch query body
        """
        if boost_fields is None:
            boost_fields = {
                "brand": 3.0,
                "model": 3.0,
                "title": 2.0,
                "description": 1.0
            }
        
        # Normalize query
        normalized_query = SearchOptimizer.normalize_query(query)
        
        # Extract filters from query if not provided
        if filters is None:
            filters = SearchOptimizer.extract_filters(query)
        
        # Build multi-match query
        fields = [f"{field}^{weight}" for field, weight in boost_fields.items()]
        
        query_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": normalized_query,
                                "fields": fields,
                                "fuzziness": "AUTO",
                                "operator": "and"
                            }
                        }
                    ],
                    "filter": [
                        {"term": {"is_active": True}}
                    ]
                }
            }
        }
        
        # Add filters
        if filters:
            for field, value in filters.items():
                if isinstance(value, dict):
                    # Range filter
                    range_query = {}
                    if "min" in value:
                        range_query["gte"] = value["min"]
                    if "max" in value:
                        range_query["lte"] = value["max"]
                    query_body["query"]["bool"]["filter"].append({"range": {field: range_query}})
                elif isinstance(value, list):
                    query_body["query"]["bool"]["filter"].append({"terms": {field: value}})
                else:
                    query_body["query"]["bool"]["filter"].append({"term": {field: value}})
        
        # Add sorting by deal score
        query_body["sort"] = [
            {"deal_score": {"order": "desc"}},
            "_score"
        ]
        
        return query_body
    
    @staticmethod
    def suggest_corrections(query: str, max_suggestions: int = 3) -> List[str]:
        """
        Suggest spelling corrections for query
        
        Args:
            query: Search query
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of suggested corrections
        """
        suggestions = []
        words = query.lower().split()
        
        for word in words:
            if word in SearchOptimizer.BRAND_SYNONYMS:
                corrected = SearchOptimizer.BRAND_SYNONYMS[word]
                if corrected != word:
                    suggestions.append(corrected)
        
        return suggestions[:max_suggestions]
    
    @staticmethod
    def expand_query(query: str) -> List[str]:
        """
        Expand query with related terms
        
        Args:
            query: Original query
            
        Returns:
            List of expanded queries
        """
        expanded = [query]
        normalized = query.lower()
        
        # Add brand synonym variations
        for word in normalized.split():
            if word in SearchOptimizer.BRAND_SYNONYMS:
                synonym = SearchOptimizer.BRAND_SYNONYMS[word]
                if synonym != word:
                    expanded.append(normalized.replace(word, synonym))
        
        return list(set(expanded))


if __name__ == "__main__":
    # Test search optimizer
    query = "golf diesel em Lisboa preço 5000 a 10000"
    
    print(f"Original query: {query}")
    print(f"Normalized: {SearchOptimizer.normalize_query(query)}")
    print(f"Filters: {SearchOptimizer.extract_filters(query)}")
    print(f"Corrections: {SearchOptimizer.suggest_corrections(query)}")
    print(f"Expanded: {SearchOptimizer.expand_query(query)}")
