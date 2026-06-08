"""
Text cleaner for cleaning and normalizing text data.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TextCleaner:
    """Text cleaner for cleaning and normalizing text data."""
    
    def __init__(self):
        """Initialize text cleaner."""
        self.cleaning_patterns = {}
        self.cleaning_history = []
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Initialize text cleaning patterns."""
        
        # Common patterns to clean
        self.cleaning_patterns = {
            'currency_symbols': r'[€$£¥]',
            'numbers': r'\d+',
            'phone_numbers': r'(\d{2,3}[-\s]?\d{3}[-\s]?\d{4})',
            'emails': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'websites': r'https?://[^\s]+|www\.[^\s]+',
            'extra_whitespace': r'\s+',
            'special_chars': r'[^\w\s\-\.]',
            'repeated_chars': r'(.)\1{2,}',
            'html_tags': r'<[^>]+>',
            'brackets': r'\[([^\]]+)\]',
            'parentheses': r'\(([^)]+)\)'
        }
    
    def clean_basic_text(self, text: str) -> str:
        """Clean basic text formatting."""
        
        if not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        cleaned = text.lower()
        
        # Remove HTML tags
        cleaned = re.sub(self.cleaning_patterns['html_tags'], '', cleaned)
        
        # Remove extra whitespace
        cleaned = re.sub(self.cleaning_patterns['extra_whitespace'], ' ', cleaned)
        
        # Strip leading/trailing whitespace
        cleaned = cleaned.strip()
        
        return cleaned
    
    def remove_contact_info(self, text: str) -> str:
        """Remove contact information from text."""
        
        if not isinstance(text, str):
            return ""
        
        cleaned = text
        
        # Remove phone numbers
        cleaned = re.sub(self.cleaning_patterns['phone_numbers'], '', cleaned)
        
        # Remove emails
        cleaned = re.sub(self.cleaning_patterns['emails'], '', cleaned)
        
        # Remove websites
        cleaned = re.sub(self.cleaning_patterns['websites'], '', cleaned)
        
        # Remove contact keywords
        contact_keywords = [
            'contato', 'contact', 'telefone', 'tel', 'phone', 'whatsapp',
            'ligar', 'chamar', 'call', 'mensagem', 'message', 'sms'
        ]
        
        for keyword in contact_keywords:
            cleaned = re.sub(rf'\b{keyword}\b', '', cleaned)
        
        return cleaned
    
    def extract_numeric_values(self, text: str) -> Dict[str, List[int]]:
        """Extract numeric values from text."""
        
        if not isinstance(text, str):
            return {}
        
        extracted = {}
        
        # Extract all numbers
        numbers = re.findall(self.cleaning_patterns['numbers'], text)
        extracted['all_numbers'] = [int(num) for num in numbers]
        
        # Extract years (4-digit numbers between 1900-2030)
        years = re.findall(r'\b(19|20)\d{2}\b', text)
        extracted['years'] = [int(year) for year in years]
        
        # Extract prices (numbers near currency symbols)
        price_pattern = r'(\d+)[\s]*[€$£¥]'
        prices = re.findall(price_pattern, text)
        extracted['prices'] = [int(price) for price in prices]
        
        # Extract mileage (numbers near km/kms)
        mileage_pattern = r'(\d+)[\s]*(km|kms|quilómetros)'
        mileage = re.findall(mileage_pattern, text)
        extracted['mileage'] = [int(mile[0]) for mile in mileage]
        
        return extracted
    
    def normalize_car_terms(self, text: str) -> str:
        """Normalize car-related terms."""
        
        if not isinstance(text, str):
            return ""
        
        cleaned = text
        
        # Normalize fuel types
        fuel_mapping = {
            'gasolina': 'gasoline',
            'gasóleo': 'diesel',
            'diesel': 'diesel',
            'elétrico': 'electric',
            'electric': 'electric',
            'híbrido': 'hybrid',
            'hybrid': 'hybrid',
            'gpl': 'lpg',
            'lpg': 'lpg',
            'gnv': 'cng',
            'cng': 'cng'
        }
        
        for pt_term, en_term in fuel_mapping.items():
            cleaned = re.sub(rf'\b{pt_term}\b', en_term, cleaned)
        
        # Normalize transmission
        transmission_mapping = {
            'automático': 'automatic',
            'automatic': 'automatic',
            'manual': 'manual',
            'cvt': 'cvt',
            'tiptronic': 'tiptronic',
            'dsg': 'dsg'
        }
        
        for pt_term, en_term in transmission_mapping.items():
            cleaned = re.sub(rf'\b{pt_term}\b', en_term, cleaned)
        
        # Normalize condition
        condition_mapping = {
            'excelente': 'excellent',
            'perfeito': 'excellent',
            'ótimo': 'good',
            'bom': 'good',
            'regular': 'fair',
            'aceitável': 'fair',
            'ruim': 'poor',
            'mau': 'poor'
        }
        
        for pt_term, en_term in condition_mapping.items():
            cleaned = re.sub(rf'\b{pt_term}\b', en_term, cleaned)
        
        return cleaned
    
    def remove_spam_indicators(self, text: str) -> str:
        """Remove spam indicators from text."""
        
        if not isinstance(text, str):
            return ""
        
        cleaned = text
        
        # Remove excessive capitalization
        if cleaned.isupper():
            cleaned = cleaned.lower()
        
        # Remove repeated characters (more than 2)
        cleaned = re.sub(self.cleaning_patterns['repeated_chars'], r'\1\1', cleaned)
        
        # Remove spam keywords
        spam_keywords = [
            'urgente', 'urgent', 'oferta especial', 'special offer',
            'promoção', 'promotion', 'desconto', 'discount',
            'limitado', 'limited', 'última chance', 'last chance'
        ]
        
        for keyword in spam_keywords:
            cleaned = re.sub(rf'\b{keyword}\b', '', cleaned)
        
        return cleaned
    
    def extract_key_features(self, text: str) -> Dict[str, bool]:
        """Extract key features from text."""
        
        if not isinstance(text, str):
            return {}
        
        features = {}
        text_lower = text.lower()
        
        # Feature patterns
        feature_patterns = {
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
        
        for feature, keywords in feature_patterns.items():
            features[feature] = any(keyword in text_lower for keyword in keywords)
        
        return features
    
    def calculate_text_quality(self, text: str) -> Dict[str, Any]:
        """Calculate text quality metrics."""
        
        if not isinstance(text, str):
            return {'quality_score': 0.0, 'issues': ['Invalid text input']}
        
        issues = []
        score = 100.0
        
        # Length check
        if len(text) < 20:
            issues.append('Too short')
            score -= 30
        elif len(text) > 2000:
            issues.append('Too long')
            score -= 10
        
        # Word count check
        word_count = len(text.split())
        if word_count < 5:
            issues.append('Too few words')
            score -= 20
        
        # Character diversity check
        unique_chars = len(set(text))
        if unique_chars < 10:
            issues.append('Low character diversity')
            score -= 15
        
        # Spam indicators check
        spam_indicators = len(self.extract_key_features(text)) == 0 and word_count > 50
        if spam_indicators:
            issues.append('Possible spam content')
            score -= 25
        
        # Contact info check
        has_contact = bool(self.remove_contact_info(text) != text)
        if has_contact:
            issues.append('Contains contact information')
            score -= 20
        
        score = max(0, score)
        
        return {
            'quality_score': score / 100.0,
            'issues': issues,
            'word_count': word_count,
            'char_count': len(text),
            'unique_chars': unique_chars
        }
    
    def clean_description_text(self, text: str) -> Dict[str, Any]:
        """Comprehensive text cleaning for descriptions."""
        
        if not isinstance(text, str):
            return {
                'original_text': '',
                'cleaned_text': '',
                'extracted_data': {},
                'features': {},
                'quality': {'quality_score': 0.0, 'issues': ['Invalid input']}
            }
        
        # Step-by-step cleaning
        cleaned = text
        
        # Remove contact information
        cleaned = self.remove_contact_info(cleaned)
        
        # Remove spam indicators
        cleaned = self.remove_spam_indicators(cleaned)
        
        # Normalize car terms
        cleaned = self.normalize_car_terms(cleaned)
        
        # Basic cleaning
        cleaned = self.clean_basic_text(cleaned)
        
        # Extract data
        extracted_data = self.extract_numeric_values(text)
        
        # Extract features
        features = self.extract_key_features(cleaned)
        
        # Calculate quality
        quality = self.calculate_text_quality(text)
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'clean_description_text',
            'timestamp': datetime.now().isoformat(),
            'original_length': len(text),
            'cleaned_length': len(cleaned),
            'quality_score': quality['quality_score']
        })
        
        return {
            'original_text': text,
            'cleaned_text': cleaned,
            'extracted_data': extracted_data,
            'features': features,
            'quality': quality
        }
    
    def batch_clean_texts(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Clean multiple texts in batch."""
        
        results = []
        
        for i, text in enumerate(texts):
            try:
                result = self.clean_description_text(text)
                result['batch_index'] = i
                results.append(result)
            except Exception as e:
                logger.error(f"Error cleaning text {i}: {e}")
                results.append({
                    'batch_index': i,
                    'error': str(e),
                    'cleaned_text': '',
                    'quality': {'quality_score': 0.0, 'issues': ['Processing error']}
                })
        
        return results
    
    def clean_dataframe_column(self, df: pd.DataFrame, column: str) -> pd.DataFrame:
        """Clean a text column in a DataFrame."""
        
        if column not in df.columns:
            logger.warning(f"Column '{column}' not found in DataFrame")
            return df
        
        df_clean = df.copy()
        
        # Apply cleaning to each text
        cleaned_results = df_clean[column].apply(self.clean_description_text)
        
        # Extract cleaned text
        df_clean[f'{column}_cleaned'] = cleaned_results.apply(lambda x: x['cleaned_text'])
        
        # Extract features
        features_list = cleaned_results.apply(lambda x: x['features'])
        feature_df = pd.json_normalize(features_list)
        
        # Merge features back to main DataFrame
        for col in feature_df.columns:
            df_clean[f'{column}_{col}'] = feature_df[col]
        
        # Extract quality scores
        df_clean[f'{column}_quality_score'] = cleaned_results.apply(lambda x: x['quality']['quality_score'])
        
        # Log cleaning
        self.cleaning_history.append({
            'operation': 'clean_dataframe_column',
            'timestamp': datetime.now().isoformat(),
            'column': column,
            'records_processed': len(df_clean)
        })
        
        return df_clean
    
    def generate_cleaning_summary(self) -> Dict[str, Any]:
        """Generate summary of cleaning operations."""
        
        return {
            'total_operations': len(self.cleaning_history),
            'operations': self.cleaning_history,
            'patterns_used': list(self.cleaning_patterns.keys()),
            'last_updated': datetime.now().isoformat()
        }
