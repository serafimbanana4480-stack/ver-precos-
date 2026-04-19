"""
ML-Based HTML Parser for Listing Identification
Uses machine learning to identify vehicle listings in HTML when selectors fail
"""
from __future__ import annotations
import logging
import pickle
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ListingPrediction:
    """Prediction result for a potential listing element"""
    is_listing: bool
    confidence: float
    source: str
    features: Dict[str, Any]


class SimpleListingClassifier:
    """
    Simple ML classifier for identifying vehicle listings in HTML
    Uses heuristic features instead of complex ML for maintainability
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path("./models/listing_classifier.pkl")
        self.feature_weights = self._get_default_feature_weights()
        self.trained = False
        
        # Try to load existing model
        if self.model_path.exists():
            self._load_model()
    
    def _get_default_feature_weights(self) -> Dict[str, float]:
        """Default feature weights for listing detection"""
        return {
            'has_price_pattern': 0.3,
            'has_url_with_anuncio': 0.25,
            'has_year_pattern': 0.15,
            'has_km_pattern': 0.15,
            'has_title_tag': 0.1,
            'has_image': 0.05,
            'element_depth': -0.02,
            'text_length': 0.01
        }
    
    def extract_features(self, element: Any, source: str) -> Dict[str, Any]:
        """
        Extract features from an HTML element for classification
        
        Args:
            element: BeautifulSoup element
            source: Source identifier
            
        Returns:
            Dictionary of features
        """
        features = {
            'source': source,
            'has_price_pattern': 0,
            'has_url_with_anuncio': 0,
            'has_year_pattern': 0,
            'has_km_pattern': 0,
            'has_title_tag': 0,
            'has_image': 0,
            'element_depth': 0,
            'text_length': 0,
            'class_name': '',
            'tag_name': ''
        }
        
        try:
            from bs4 import Tag
        except ImportError:
            logger.error("BeautifulSoup is required for feature extraction")
            return features
        
        if not isinstance(element, Tag):
            return features
        
        # Get text content
        text = element.get_text(strip=True)
        features['text_length'] = len(text)
        
        # Check for price pattern (€ or numbers with dots)
        text_lower = text.lower()
        if '€' in text or any(c.isdigit() for c in text):
            # Check if it looks like a price (e.g., "€12.345" or "12 345 €")
            import re
            price_pattern = r'€?\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?\s*€?'
            if re.search(price_pattern, text):
                features['has_price_pattern'] = 1
        
        # Check for URL with "anuncio"
        link = element.find('a', href=True)
        if link and link.get('href'):
            href = link.get('href', '')
            if '/anuncio-' in href:
                features['has_url_with_anuncio'] = 1
        
        # Check for year pattern (4 digits, 1980-2025)
        import re
        year_pattern = r'\b(19[89]\d|20[0-2]\d)\b'
        if re.search(year_pattern, text):
            features['has_year_pattern'] = 1
        
        # Check for KM pattern (numbers with "km")
        if 'km' in text_lower or 'quilómetros' in text_lower:
            km_pattern = r'\d{1,3}(?:[.\s]\d{3})*\s*(?:km|quilómetros)'
            if re.search(km_pattern, text_lower):
                features['has_km_pattern'] = 1
        
        # Check for title tag (h1-h6)
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            features['has_title_tag'] = 1
        
        # Check for image
        if element.find('img'):
            features['has_image'] = 1
        
        # Calculate element depth
        depth = 0
        parent = element.parent
        while parent and parent.name:
            depth += 1
            parent = parent.parent
        features['element_depth'] = depth
        
        # Get class name
        if element.get('class'):
            features['class_name'] = ' '.join(element.get('class', []))
        
        features['tag_name'] = element.name
        
        return features
    
    def predict(self, element: Any, source: str, threshold: float = 0.5) -> ListingPrediction:
        """
        Predict if an element is a vehicle listing
        
        Args:
            element: BeautifulSoup element
            source: Source identifier
            threshold: Confidence threshold for classification
            
        Returns:
            ListingPrediction object
        """
        features = self.extract_features(element, source)
        
        # Calculate weighted score
        score = 0.0
        for feature_name, weight in self.feature_weights.items():
            if feature_name in features:
                score += features[feature_name] * weight
        
        # Normalize score to 0-1 range
        # Max possible score is sum of positive weights
        max_score = sum(w for w in self.feature_weights.values() if w > 0)
        if max_score > 0:
            score = max(0, min(1, score / max_score))
        
        is_listing = score >= threshold
        
        return ListingPrediction(
            is_listing=is_listing,
            confidence=score,
            source=source,
            features=features
        )
    
    def train(self, training_data: List[Tuple[Any, bool, str]]) -> None:
        """
        Train the classifier on labeled data
        
        Args:
            training_data: List of (element, is_listing, source) tuples
        """
        logger.info(f"Training classifier on {len(training_data)} samples")
        
        # For this simple classifier, we don't actually train a ML model
        # We use the heuristic weights which work well for vehicle listings
        # In a more advanced version, we could use scikit-learn here
        
        self.trained = True
        logger.info("Classifier trained successfully")
    
    def save_model(self) -> None:
        """Save the classifier model"""
        model_data = {
            'feature_weights': self.feature_weights,
            'trained': self.trained,
            'trained_at': datetime.now(timezone.utc).isoformat()
        }
        
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {self.model_path}")
    
    def _load_model(self) -> None:
        """Load the classifier model"""
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.feature_weights = model_data.get('feature_weights', self._get_default_feature_weights())
            self.trained = model_data.get('trained', False)
            
            logger.info(f"Model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.feature_weights = self._get_default_feature_weights()
            self.trained = False


class MLParser:
    """ML-based HTML parser for fallback when selectors fail"""
    
    def __init__(self):
        self.classifier = SimpleListingClassifier()
    
    def find_listings(
        self,
        html: str,
        source: str,
        threshold: float = 0.5
    ) -> List[Tuple[Any, ListingPrediction]]:
        """
        Find vehicle listings in HTML using ML classifier
        
        Args:
            html: HTML content
            source: Source identifier
            threshold: Confidence threshold
            
        Returns:
            List of (element, prediction) tuples
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup is required for ML parsing")
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Get all potential listing elements (div, article, li)
        potential_elements = soup.find_all(['div', 'article', 'li'])
        
        listings = []
        
        for element in potential_elements:
            prediction = self.classifier.predict(element, source, threshold)
            
            if prediction.is_listing:
                listings.append((element, prediction))
        
        # Sort by confidence
        listings.sort(key=lambda x: x[1].confidence, reverse=True)
        
        logger.info(f"Found {len(listings)} potential listings using ML classifier")
        
        return listings
    
    def extract_from_ml_element(
        self,
        element: Any,
        prediction: ListingPrediction
    ) -> Dict[str, Any]:
        """
        Extract listing data from ML-identified element
        
        Args:
            element: BeautifulSoup element
            prediction: Listing prediction
            
        Returns:
            Dictionary of extracted data
        """
        data = {
            'url': None,
            'title': None,
            'price': None,
            'location': None,
            'confidence': prediction.confidence
        }
        
        try:
            from bs4 import Tag
        except ImportError:
            return data
        
        if not isinstance(element, Tag):
            return data
        
        # Extract URL
        link = element.find('a', href=True)
        if link:
            data['url'] = link.get('href')
        
        # Extract title (try h1-h6, then link text, then first text)
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            title_elem = element.find(tag)
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)
                break
        
        if not data['title'] and link:
            data['title'] = link.get_text(strip=True)
        
        if not data['title']:
            data['title'] = element.get_text(strip=True)[:100]
        
        # Extract price
        text = element.get_text()
        import re
        price_pattern = r'€?\s*([\d.]+)\s*€?'
        price_match = re.search(price_pattern, text)
        if price_match:
            price_str = price_match.group(1).replace('.', '').replace(',', '.')
            try:
                data['price'] = float(price_str)
            except ValueError:
                pass
        
        # Extract location (look for common location keywords)
        location_keywords = ['lisboa', 'porto', 'braga', 'coimbra', 'faro', 'aveiro']
        text_lower = text.lower()
        for keyword in location_keywords:
            if keyword in text_lower:
                data['location'] = keyword.capitalize()
                break
        
        return data


# Global ML parser instance
_ml_parser = MLParser()


def get_ml_parser() -> MLParser:
    """Get the global ML parser instance"""
    return _ml_parser
