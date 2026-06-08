"""
Text analyzer for AI-powered text processing.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TextAnalyzer:
    """Text analyzer for AI-powered text processing of car listings."""
    
    def __init__(self):
        """Initialize text analyzer."""
        self.text_patterns = {}
        self.sentiment_keywords = {}
        self.feature_keywords = {}
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Initialize text patterns for analysis."""
        
        # Car condition patterns
        self.text_patterns['condition'] = {
            'excellent': ['excelente', 'perfeito', 'impecável', 'como novo', 'zero km', 'novíssimo'],
            'good': ['bom', 'ótimo', 'conservado', 'bem cuidado', 'em bom estado'],
            'fair': ['aceitável', 'regular', 'usado', 'com alguns sinais', 'normal'],
            'poor': ['mau', 'ruim', 'precisa de reparação', 'com problemas', 'avariado']
        }
        
        # Feature patterns
        self.text_patterns['features'] = {
            'air_conditioning': ['ar condicionado', 'ac', 'climatização'],
            'power_steering': ['direção assistida', 'direção hidráulica'],
            'abs': ['abs', 'freios abs'],
            'airbags': ['airbag', 'airbags', 'sacos de ar'],
            'cruise_control': ['cruise control', 'controlo de velocidade'],
            'parking_sensors': ['sensores de estacionamento', 'parking sensors'],
            'navigation': ['gps', 'navegação', 'sistema de navegação'],
            'leather_seats': ['couro', 'assentos de couro'],
            'alloy_wheels': ['jantes de liga', 'alloy wheels'],
            'sunroof': ['teto solar', 'sunroof'],
            'automatic': ['automático', 'automática', 'cambio automático']
        }
        
        # Sentiment patterns
        self.sentiment_keywords['positive'] = [
            'excelente', 'perfeito', 'ótimo', 'bom', 'conservado', 'cuidado', 
            'novíssimo', 'impecável', 'funciona bem', 'sem problemas'
        ]
        
        self.sentiment_keywords['negative'] = [
            'mau', 'ruim', 'avariado', 'com problemas', 'precisa de reparação',
            'danificado', 'com defeito', 'não funciona', 'com ferrugem'
        ]
    
    def extract_condition_from_text(self, text: str) -> Dict[str, Any]:
        """Extract car condition from text description."""
        
        if not text or not isinstance(text, str):
            return {'condition': 'unknown', 'confidence': 0.0}
        
        text_lower = text.lower()
        condition_scores = {}
        
        for condition, keywords in self.text_patterns['condition'].items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            
            if score > 0:
                condition_scores[condition] = score
        
        if condition_scores:
            best_condition = max(condition_scores, key=condition_scores.get)
            confidence = condition_scores[best_condition] / len(self.text_patterns['condition'][best_condition])
            
            return {
                'condition': best_condition,
                'confidence': min(confidence, 1.0),
                'all_scores': condition_scores
            }
        
        return {'condition': 'unknown', 'confidence': 0.0}
    
    def extract_features_from_text(self, text: str) -> Dict[str, bool]:
        """Extract car features from text description."""
        
        if not text or not isinstance(text, str):
            return {}
        
        text_lower = text.lower()
        extracted_features = {}
        
        for feature, keywords in self.text_patterns['features'].items():
            has_feature = any(keyword in text_lower for keyword in keywords)
            extracted_features[feature] = has_feature
        
        return extracted_features
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text description."""
        
        if not text or not isinstance(text, str):
            return {'sentiment': 'neutral', 'confidence': 0.0}
        
        text_lower = text.lower()
        
        positive_count = sum(1 for word in self.sentiment_keywords['positive'] if word in text_lower)
        negative_count = sum(1 for word in self.sentiment_keywords['negative'] if word in text_lower)
        
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return {'sentiment': 'neutral', 'confidence': 0.0}
        
        positive_ratio = positive_count / total_sentiment_words
        
        if positive_ratio > 0.6:
            sentiment = 'positive'
        elif positive_ratio < 0.4:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        confidence = total_sentiment_words / 10  # Normalize by expected max
        confidence = min(confidence, 1.0)
        
        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'positive_words': positive_count,
            'negative_words': negative_count
        }
    
    def extract_key_information(self, text: str) -> Dict[str, Any]:
        """Extract key information from text description."""
        
        if not text or not isinstance(text, str):
            return {}
        
        extracted_info = {}
        
        # Extract year
        year_pattern = r'\b(19|20)\d{2}\b'
        years = re.findall(year_pattern, text)
        if years:
            extracted_info['mentioned_years'] = [int(year) for year in years]
        
        # Extract mileage
        mileage_pattern = r'\b(\d{1,6})\s*(km|kms|quilómetros|quilometros)\b'
        mileage_matches = re.findall(mileage_pattern, text.lower())
        if mileage_matches:
            extracted_info['mentioned_mileage'] = [int(match[0]) for match in mileage_matches]
        
        # Extract price
        price_pattern = r'\b(\d{1,6})\s*(€|euros)\b'
        price_matches = re.findall(price_pattern, text.lower())
        if price_matches:
            extracted_info['mentioned_prices'] = [int(match[0]) for match in price_matches]
        
        # Extract engine size
        engine_pattern = r'\b(\d{1,2}\.\d)\s*(l|litros|cc)\b'
        engine_matches = re.findall(engine_pattern, text.lower())
        if engine_matches:
            extracted_info['mentioned_engine_sizes'] = [float(match[0]) for match in engine_matches]
        
        return extracted_info
    
    def calculate_text_quality_score(self, text: str) -> Dict[str, Any]:
        """Calculate quality score of text description."""
        
        if not text or not isinstance(text, str):
            return {'quality_score': 0.0, 'issues': ['Empty or invalid text']}
        
        issues = []
        score = 100.0
        
        # Length check
        if len(text) < 50:
            issues.append('Too short')
            score -= 30
        elif len(text) > 2000:
            issues.append('Too long')
            score -= 10
        
        # Check for meaningful content
        if len(text.split()) < 10:
            issues.append('Too few words')
            score -= 20
        
        # Check for repeated content
        words = text.lower().split()
        if len(set(words)) / len(words) < 0.5:
            issues.append('Too much repetition')
            score -= 15
        
        # Check for spam indicators
        spam_indicators = ['contato', 'whatsapp', 'telefone', 'ligar', 'chamar', 'urgente']
        spam_count = sum(1 for indicator in spam_indicators if indicator in text.lower())
        if spam_count > 3:
            issues.append('Possible spam content')
            score -= 25
        
        # Check for capitalization
        if text.isupper():
            issues.append('All caps')
            score -= 10
        
        score = max(0, score)
        
        return {
            'quality_score': score / 100.0,
            'issues': issues,
            'word_count': len(text.split()),
            'char_count': len(text)
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for better processing."""
        
        if not text or not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        # Remove special characters but keep important ones
        normalized = re.sub(r'[^\w\s\-\.]', ' ', normalized)
        
        # Remove multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def process_listing_text(self, text: str) -> Dict[str, Any]:
        """Process complete listing text and return comprehensive analysis."""
        
        if not text or not isinstance(text, str):
            return {
                'error': 'Invalid text input',
                'condition': 'unknown',
                'features': {},
                'sentiment': 'neutral',
                'quality_score': 0.0
            }
        
        # Extract all information
        condition = self.extract_condition_from_text(text)
        features = self.extract_features_from_text(text)
        sentiment = self.analyze_sentiment(text)
        key_info = self.extract_key_information(text)
        quality = self.calculate_text_quality_score(text)
        
        # Calculate overall score
        overall_score = (
            condition['confidence'] * 0.3 +
            sentiment['confidence'] * 0.2 +
            quality['quality_score'] * 0.5
        )
        
        return {
            'condition': condition['condition'],
            'condition_confidence': condition['confidence'],
            'features': features,
            'sentiment': sentiment['sentiment'],
            'sentiment_confidence': sentiment['confidence'],
            'key_information': key_info,
            'quality_score': quality['quality_score'],
            'quality_issues': quality['issues'],
            'overall_score': overall_score,
            'processed_at': datetime.now().isoformat()
        }
    
    def batch_process_texts(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Process multiple texts in batch."""
        
        results = []
        
        for i, text in enumerate(texts):
            try:
                result = self.process_listing_text(text)
                result['batch_index'] = i
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing text {i}: {e}")
                results.append({
                    'batch_index': i,
                    'error': str(e),
                    'processed_at': datetime.now().isoformat()
                })
        
        return results
    
    def generate_text_summary(self, text: str) -> Dict[str, Any]:
        """Generate summary of text analysis."""
        
        analysis = self.process_listing_text(text)
        
        summary = {
            'condition': analysis.get('condition', 'unknown'),
            'feature_count': len(analysis.get('features', {})),
            'features_present': [k for k, v in analysis.get('features', {}).items() if v],
            'sentiment': analysis.get('sentiment', 'neutral'),
            'quality_score': analysis.get('quality_score', 0.0),
            'overall_assessment': self._get_overall_assessment(analysis),
            'recommendations': self._get_recommendations(analysis)
        }
        
        return summary
    
    def _get_overall_assessment(self, analysis: Dict[str, Any]) -> str:
        """Get overall assessment based on analysis."""
        
        quality_score = analysis.get('quality_score', 0.0)
        sentiment = analysis.get('sentiment', 'neutral')
        condition = analysis.get('condition', 'unknown')
        
        if quality_score > 0.8 and sentiment == 'positive':
            return 'Excellent listing with good description'
        elif quality_score > 0.6 and sentiment in ['positive', 'neutral']:
            return 'Good listing with decent description'
        elif quality_score > 0.4:
            return 'Fair listing with some description issues'
        else:
            return 'Poor listing with significant description problems'
    
    def _get_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Get recommendations based on analysis."""
        
        recommendations = []
        quality_issues = analysis.get('quality_issues', [])
        
        if 'Too short' in quality_issues:
            recommendations.append('Add more detailed description')
        
        if 'Too few words' in quality_issues:
            recommendations.append('Expand description with more details')
        
        if 'Possible spam content' in quality_issues:
            recommendations.append('Remove excessive contact information')
        
        if 'All caps' in quality_issues:
            recommendations.append('Use normal capitalization')
        
        if analysis.get('sentiment') == 'negative':
            recommendations.append('Focus on positive aspects of the vehicle')
        
        if analysis.get('condition') == 'unknown':
            recommendations.append('Clearly state the condition of the vehicle')
        
        feature_count = len(analysis.get('features', {}))
        if feature_count < 3:
            recommendations.append('Mention more vehicle features')
        
        return recommendations
