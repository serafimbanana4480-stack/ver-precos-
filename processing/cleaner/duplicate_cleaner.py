"""
Duplicate cleaner for identifying and removing duplicate records.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
import logging
from datetime import datetime
from difflib import SequenceMatcher
import hashlib

logger = logging.getLogger(__name__)


class DuplicateCleaner:
    """Duplicate cleaner for identifying and removing duplicate records."""
    
    def __init__(self):
        """Initialize duplicate cleaner."""
        self.duplicate_history = []
        self.similarity_threshold = 0.8
        
    def find_exact_duplicates(self, df: pd.DataFrame, subset: List[str] = None) -> pd.DataFrame:
        """Find exact duplicate records."""
        
        if subset is None:
            subset = df.columns.tolist()
        
        # Filter available columns
        available_subset = [col for col in subset if col in df.columns]
        
        if not available_subset:
            logger.warning("No valid columns for duplicate detection")
            return pd.DataFrame()
        
        # Find duplicates
        duplicates = df[df.duplicated(subset=available_subset, keep=False)]
        
        # Log detection
        self.duplicate_history.append({
            'operation': 'find_exact_duplicates',
            'timestamp': datetime.now().isoformat(),
            'subset_used': available_subset,
            'total_records': len(df),
            'exact_duplicates': len(duplicates)
        })
        
        return duplicates
    
    def find_fuzzy_duplicates(self, df: pd.DataFrame, text_columns: List[str] = None) -> pd.DataFrame:
        """Find fuzzy duplicates using text similarity."""
        
        if text_columns is None:
            text_columns = ['make', 'model', 'description']
        
        # Filter available columns
        available_columns = [col for col in text_columns if col in df.columns]
        
        if not available_columns:
            logger.warning("No valid text columns for fuzzy duplicate detection")
            return pd.DataFrame()
        
        duplicates = []
        processed_pairs = set()
        
        # Compare each pair of records
        for i in range(len(df)):
            for j in range(i + 1, len(df)):
                pair = (i, j)
                if pair in processed_pairs:
                    continue
                
                similarity = self._calculate_text_similarity(
                    df.iloc[i], df.iloc[j], available_columns
                )
                
                if similarity >= self.similarity_threshold:
                    duplicates.append(df.iloc[j])
                    processed_pairs.add(pair)
        
        duplicate_df = pd.DataFrame(duplicates)
        
        # Log detection
        self.duplicate_history.append({
            'operation': 'find_fuzzy_duplicates',
            'timestamp': datetime.now().isoformat(),
            'columns_used': available_columns,
            'similarity_threshold': self.similarity_threshold,
            'total_records': len(df),
            'fuzzy_duplicates': len(duplicate_df)
        })
        
        return duplicate_df
    
    def _calculate_text_similarity(self, row1: pd.Series, row2: pd.Series, columns: List[str]) -> float:
        """Calculate text similarity between two rows."""
        
        similarities = []
        
        for col in columns:
            text1 = str(row1[col]).lower().strip()
            text2 = str(row2[col]).lower().strip()
            
            if text1 and text2:
                similarity = SequenceMatcher(None, text1, text2).ratio()
                similarities.append(similarity)
        
        return np.mean(similarities) if similarities else 0.0
    
    def find_price_duplicates(self, df: pd.DataFrame, price_column: str = 'price', 
                           tolerance: float = 0.05, group_columns: List[str] = None) -> pd.DataFrame:
        """Find duplicates based on price tolerance."""
        
        if price_column not in df.columns:
            logger.warning(f"Price column '{price_column}' not found")
            return pd.DataFrame()
        
        if group_columns is None:
            group_columns = ['make', 'model', 'year']
        
        # Filter available columns
        available_groups = [col for col in group_columns if col in df.columns]
        
        if not available_groups:
            logger.warning("No valid grouping columns for price duplicate detection")
            return pd.DataFrame()
        
        duplicates = []
        
        # Group by specified columns
        for name, group in df.groupby(available_groups):
            if len(group) < 2:
                continue
            
            # Calculate price statistics
            prices = group[price_column].values
            mean_price = np.mean(prices)
            
            # Find records with similar prices
            for idx, row in group.iterrows():
                price_diff = abs(row[price_column] - mean_price) / mean_price
                
                if price_diff <= tolerance:
                    duplicates.append(row)
        
        duplicate_df = pd.DataFrame(duplicates)
        
        # Log detection
        self.duplicate_history.append({
            'operation': 'find_price_duplicates',
            'timestamp': datetime.now().isoformat(),
            'price_column': price_column,
            'tolerance': tolerance,
            'group_columns': available_groups,
            'total_records': len(df),
            'price_duplicates': len(duplicate_df)
        })
        
        return duplicate_df
    
    def find_content_hash_duplicates(self, df: pd.DataFrame, content_columns: List[str] = None) -> pd.DataFrame:
        """Find duplicates based on content hash."""
        
        if content_columns is None:
            content_columns = ['make', 'model', 'year', 'mileage', 'price']
        
        # Filter available columns
        available_columns = [col for col in content_columns if col in df.columns]
        
        if not available_columns:
            logger.warning("No valid columns for content hash duplicate detection")
            return pd.DataFrame()
        
        # Calculate content hash for each record
        hashes = {}
        duplicates = []
        
        for idx, row in df.iterrows():
            # Create content string
            content_parts = []
            for col in available_columns:
                content_parts.append(str(row[col]))
            
            content_str = '|'.join(content_parts)
            content_hash = hashlib.md5(content_str.encode()).hexdigest()
            
            # Check for existing hash
            if content_hash in hashes:
                duplicates.append(row)
            else:
                hashes[content_hash] = idx
        
        duplicate_df = pd.DataFrame(duplicates)
        
        # Log detection
        self.duplicate_history.append({
            'operation': 'find_content_hash_duplicates',
            'timestamp': datetime.now().isoformat(),
            'content_columns': available_columns,
            'total_records': len(df),
            'hash_duplicates': len(duplicate_df)
        })
        
        return duplicate_df
    
    def remove_duplicates(self, df: pd.DataFrame, method: str = 'exact', 
                        subset: List[str] = None, keep: str = 'first') -> pd.DataFrame:
        """Remove duplicates using specified method."""
        
        if method == 'exact':
            duplicates = self.find_exact_duplicates(df, subset)
            df_clean = df.drop_duplicates(subset=subset, keep=keep)
        
        elif method == 'fuzzy':
            duplicates = self.find_fuzzy_duplicates(df, subset)
            # For fuzzy duplicates, we need to manually remove them
            df_clean = self._remove_fuzzy_duplicates(df, duplicates, keep)
        
        elif method == 'price':
            duplicates = self.find_price_duplicates(df, subset=subset)
            df_clean = self._remove_fuzzy_duplicates(df, duplicates, keep)
        
        elif method == 'content_hash':
            duplicates = self.find_content_hash_duplicates(df, subset)
            df_clean = self._remove_fuzzy_duplicates(df, duplicates, keep)
        
        else:
            logger.error(f"Unknown duplicate removal method: {method}")
            return df
        
        # Log removal
        self.duplicate_history.append({
            'operation': 'remove_duplicates',
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'subset': subset,
            'keep': keep,
            'records_before': len(df),
            'records_after': len(df_clean),
            'duplicates_removed': len(df) - len(df_clean)
        })
        
        return df_clean
    
    def _remove_fuzzy_duplicates(self, df: pd.DataFrame, duplicates: pd.DataFrame, keep: str = 'first') -> pd.DataFrame:
        """Remove fuzzy duplicates from DataFrame."""
        
        if duplicates.empty:
            return df.copy()
        
        df_clean = df.copy()
        
        # Get indices of duplicates
        duplicate_indices = set(duplicates.index.tolist())
        
        if keep == 'first':
            # Keep first occurrence of each duplicate group
            df_clean = df_clean[~df_clean.index.isin(duplicate_indices)]
        elif keep == 'last':
            # Keep last occurrence of each duplicate group
            # This is more complex for fuzzy duplicates
            # For simplicity, we'll keep non-duplicates
            df_clean = df_clean[~df_clean.index.isin(duplicate_indices)]
        
        return df_clean
    
    def analyze_duplicate_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze patterns in duplicate records."""
        
        analysis = {
            'exact_duplicates': {},
            'fuzzy_duplicates': {},
            'price_duplicates': {},
            'content_hash_duplicates': {},
            'recommendations': []
        }
        
        # Find all types of duplicates
        exact_dups = self.find_exact_duplicates(df)
        fuzzy_dups = self.find_fuzzy_duplicates(df)
        price_dups = self.find_price_duplicates(df)
        hash_dups = self.find_content_hash_duplicates(df)
        
        # Analyze exact duplicates
        if not exact_dups.empty:
            exact_group_counts = exact_dups.groupby(df.columns.tolist()).size()
            analysis['exact_duplicates'] = {
                'count': len(exact_dups),
                'percentage': (len(exact_dups) / len(df)) * 100,
                'most_common_patterns': exact_group_counts.head(5).to_dict()
            }
        
        # Analyze fuzzy duplicates
        if not fuzzy_dups.empty:
            analysis['fuzzy_duplicates'] = {
                'count': len(fuzzy_dups),
                'percentage': (len(fuzzy_dups) / len(df)) * 100
            }
        
        # Analyze price duplicates
        if not price_dups.empty:
            analysis['price_duplicates'] = {
                'count': len(price_dups),
                'percentage': (len(price_dups) / len(df)) * 100
            }
        
        # Analyze content hash duplicates
        if not hash_dups.empty:
            analysis['content_hash_duplicates'] = {
                'count': len(hash_dups),
                'percentage': (len(hash_dups) / len(df)) * 100
            }
        
        # Generate recommendations
        total_duplicates = len(exact_dups) + len(fuzzy_dups) + len(price_dups) + len(hash_dups)
        
        if total_duplicates > 0:
            analysis['recommendations'].append(f"Found {total_duplicates} potential duplicates")
            
            if len(exact_dups) > 0:
                analysis['recommendations'].append("Consider removing exact duplicates first")
            
            if len(fuzzy_dups) > 0:
                analysis['recommendations'].append("Review fuzzy duplicates for potential data quality issues")
            
            if len(price_dups) > 0:
                analysis['recommendations'].append("Check price duplicates for possible pricing errors")
        else:
            analysis['recommendations'].append("No duplicates found - data quality is good")
        
        return analysis
    
    def create_duplicate_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create comprehensive duplicate analysis report."""
        
        report = {
            'summary': {
                'total_records': len(df),
                'analysis_timestamp': datetime.now().isoformat()
            },
            'duplicate_analysis': self.analyze_duplicate_patterns(df),
            'detection_methods': {
                'exact_duplicates': 'Finds records with identical values in specified columns',
                'fuzzy_duplicates': 'Finds records with similar text content',
                'price_duplicates': 'Finds records with similar prices within tolerance',
                'content_hash_duplicates': 'Finds records with identical content hash'
            },
            'cleaning_history': self.duplicate_history
        }
        
        return report
    
    def clean_all_duplicates(self, df: pd.DataFrame, aggressive: bool = False) -> pd.DataFrame:
        """Apply comprehensive duplicate cleaning."""
        
        df_clean = df.copy()
        
        # Step 1: Remove exact duplicates
        df_clean = self.remove_duplicates(df_clean, method='exact')
        
        # Step 2: Remove content hash duplicates
        df_clean = self.remove_duplicates(df_clean, method='content_hash')
        
        # Step 3: Remove price duplicates (if aggressive)
        if aggressive:
            df_clean = self.remove_duplicates(df_clean, method='price', tolerance=0.02)
        
        # Step 4: Remove fuzzy duplicates (if very aggressive)
        if aggressive:
            self.similarity_threshold = 0.9  # Higher threshold for aggressive cleaning
            df_clean = self.remove_duplicates(df_clean, method='fuzzy')
        
        # Log comprehensive cleaning
        self.duplicate_history.append({
            'operation': 'clean_all_duplicates',
            'timestamp': datetime.now().isoformat(),
            'aggressive': aggressive,
            'records_before': len(df),
            'records_after': len(df_clean),
            'total_removed': len(df) - len(df_clean)
        })
        
        return df_clean
    
    def set_similarity_threshold(self, threshold: float):
        """Set similarity threshold for fuzzy duplicate detection."""
        
        if 0.0 <= threshold <= 1.0:
            self.similarity_threshold = threshold
            logger.info(f"Similarity threshold set to {threshold}")
        else:
            logger.error("Similarity threshold must be between 0.0 and 1.0")
    
    def get_cleaning_summary(self) -> Dict[str, Any]:
        """Get summary of duplicate cleaning operations."""
        
        return {
            'total_operations': len(self.duplicate_history),
            'operations': self.duplicate_history,
            'similarity_threshold': self.similarity_threshold,
            'last_updated': datetime.now().isoformat()
        }
