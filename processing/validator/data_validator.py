"""
Data validator for comprehensive data validation.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataValidator:
    """Data validator for comprehensive data validation."""
    
    def __init__(self):
        """Initialize data validator."""
        self.validation_rules = {}
        self.validation_history = []
        self._initialize_rules()
    
    def _initialize_rules(self):
        """Initialize validation rules."""
        
        self.validation_rules = {
            'price': {
                'required': True,
                'type': 'numeric',
                'min': 0,
                'max': 1000000,
                'allow_null': False
            },
            'mileage': {
                'required': True,
                'type': 'numeric',
                'min': 0,
                'max': 500000,
                'allow_null': False
            },
            'year': {
                'required': True,
                'type': 'numeric',
                'min': 1900,
                'max': datetime.now().year + 1,
                'allow_null': False
            },
            'make': {
                'required': True,
                'type': 'string',
                'min_length': 1,
                'max_length': 50,
                'allow_null': False
            },
            'model': {
                'required': True,
                'type': 'string',
                'min_length': 1,
                'max_length': 50,
                'allow_null': False
            },
            'fuel_type': {
                'required': False,
                'type': 'string',
                'allowed_values': ['Gasoline', 'Diesel', 'Electric', 'Hybrid', 'LPG', 'CNG', 'Unknown'],
                'allow_null': True
            },
            'transmission': {
                'required': False,
                'type': 'string',
                'allowed_values': ['Automatic', 'Manual', 'CVT', 'Tiptronic', 'DSG', 'Unknown'],
                'allow_null': True
            },
            'engine_size': {
                'required': False,
                'type': 'numeric',
                'min': 0.5,
                'max': 10.0,
                'allow_null': True
            },
            'location': {
                'required': False,
                'type': 'string',
                'min_length': 1,
                'max_length': 100,
                'allow_null': True
            }
        }
    
    def validate_data_types(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate data types in the DataFrame."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        for column in df.columns:
            if column in self.validation_rules:
                rule = self.validation_rules[column]
                expected_type = rule['type']
                
                if expected_type == 'numeric':
                    if not pd.api.types.is_numeric_dtype(df[column]):
                        # Try to convert to numeric
                        try:
                            pd.to_numeric(df[column])
                            validation_results['warnings'].append(f"Column '{column}' converted to numeric")
                        except:
                            validation_results['errors'].append(f"Column '{column}' should be numeric but cannot be converted")
                            validation_results['valid'] = False
                
                elif expected_type == 'string':
                    if not pd.api.types.is_string_dtype(df[column]) and not pd.api.types.is_object_dtype(df[column]):
                        validation_results['errors'].append(f"Column '{column}' should be string")
                        validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_data_types',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'errors_count': len(validation_results['errors']),
            'warnings_count': len(validation_results['warnings'])
        })
        
        return validation_results
    
    def validate_required_fields(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate required fields are present."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'missing_fields': []
        }
        
        for field, rule in self.validation_rules.items():
            if rule['required']:
                if field not in df.columns:
                    validation_results['errors'].append(f"Required field '{field}' is missing")
                    validation_results['missing_fields'].append(field)
                    validation_results['valid'] = False
                elif rule['allow_null'] is False and df[field].isnull().any():
                    null_count = df[field].isnull().sum()
                    validation_results['errors'].append(f"Required field '{field}' has {null_count} null values")
                    validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_required_fields',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'missing_fields': validation_results['missing_fields']
        })
        
        return validation_results
    
    def validate_value_ranges(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate values are within acceptable ranges."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'out_of_range_records': {}
        }
        
        for column in df.columns:
            if column in self.validation_rules:
                rule = self.validation_rules[column]
                
                if 'min' in rule:
                    min_violations = df[df[column] < rule['min']]
                    if not min_violations.empty:
                        validation_results['errors'].append(f"Column '{column}' has {len(min_violations)} values below minimum {rule['min']}")
                        validation_results['out_of_range_records'][column] = {
                            'below_min': len(min_violations)
                        }
                        validation_results['valid'] = False
                
                if 'max' in rule:
                    max_violations = df[df[column] > rule['max']]
                    if not max_violations.empty:
                        validation_results['errors'].append(f"Column '{column}' has {len(max_violations)} values above maximum {rule['max']}")
                        if column not in validation_results['out_of_range_records']:
                            validation_results['out_of_range_records'][column] = {}
                        validation_results['out_of_range_records'][column]['above_max'] = len(max_violations)
                        validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_value_ranges',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'out_of_range_records': validation_results['out_of_range_records']
        })
        
        return validation_results
    
    def validate_allowed_values(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate values are in allowed lists."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'invalid_values': {}
        }
        
        for column in df.columns:
            if column in self.validation_rules:
                rule = self.validation_rules[column]
                
                if 'allowed_values' in rule:
                    invalid_values = df[~df[column].isin(rule['allowed_values'])]
                    if not invalid_values.empty:
                        unique_invalid = invalid_values[column].unique().tolist()
                        validation_results['errors'].append(f"Column '{column}' has invalid values: {unique_invalid}")
                        validation_results['invalid_values'][column] = unique_invalid
                        validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_allowed_values',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'invalid_values': validation_results['invalid_values']
        })
        
        return validation_results
    
    def validate_string_lengths(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate string field lengths."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'length_violations': {}
        }
        
        for column in df.columns:
            if column in self.validation_rules:
                rule = self.validation_rules[column]
                
                if rule['type'] == 'string':
                    # Convert to string for length calculation
                    str_lengths = df[column].astype(str).str.len()
                    
                    if 'min_length' in rule:
                        short_violations = df[str_lengths < rule['min_length']]
                        if not short_violations.empty:
                            validation_results['errors'].append(f"Column '{column}' has {len(short_violations)} values shorter than minimum {rule['min_length']}")
                            validation_results['length_violations'][column] = {
                                'below_min': len(short_violations)
                            }
                            validation_results['valid'] = False
                    
                    if 'max_length' in rule:
                        long_violations = df[str_lengths > rule['max_length']]
                        if not long_violations.empty:
                            validation_results['errors'].append(f"Column '{column}' has {len(long_violations)} values longer than maximum {rule['max_length']}")
                            if column not in validation_results['length_violations']:
                                validation_results['length_violations'][column] = {}
                            validation_results['length_violations'][column]['above_max'] = len(long_violations)
                            validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_string_lengths',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'length_violations': validation_results['length_violations']
        })
        
        return validation_results
    
    def validate_data_consistency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate data consistency across fields."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'consistency_issues': {}
        }
        
        # Validate year vs car age consistency
        if 'year' in df.columns:
            current_year = datetime.now().year
            future_cars = df[df['year'] > current_year + 1]
            if not future_cars.empty:
                validation_results['errors'].append(f"Found {len(future_cars)} cars with future years")
                validation_results['consistency_issues']['future_years'] = len(future_cars)
                validation_results['valid'] = False
            
            very_old_cars = df[df['year'] < 1900]
            if not very_old_cars.empty:
                validation_results['errors'].append(f"Found {len(very_old_cars)} cars with years before 1900")
                validation_results['consistency_issues']['impossible_years'] = len(very_old_cars)
                validation_results['valid'] = False
        
        # Validate mileage vs year consistency
        if 'mileage' in df.columns and 'year' in df.columns:
            df_temp = df.copy()
            df_temp['car_age'] = current_year - df_temp['year']
            
            # Assume maximum 30,000 km per year
            max_reasonable_mileage = df_temp['car_age'] * 30000
            high_mileage_cars = df_temp[df_temp['mileage'] > max_reasonable_mileage]
            
            if not high_mileage_cars.empty:
                validation_results['errors'].append(f"Found {len(high_mileage_cars)} cars with unusually high mileage for their age")
                validation_results['consistency_issues']['high_mileage'] = len(high_mileage_cars)
                validation_results['valid'] = False
        
        # Validate price vs year consistency
        if 'price' in df.columns and 'year' in df.columns:
            # Very old cars shouldn't be too expensive
            very_old_expensive = df[(df['year'] < 1990) & (df['price'] > 50000)]
            if not very_old_expensive.empty:
                validation_results['errors'].append(f"Found {len(very_old_expensive)} very old cars with high prices")
                validation_results['consistency_issues']['old_expensive'] = len(very_old_expensive)
                validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_data_consistency',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'consistency_issues': validation_results['consistency_issues']
        })
        
        return validation_results
    
    def validate_duplicates(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate for duplicate records."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'duplicate_info': {}
        }
        
        # Check for exact duplicates
        exact_duplicates = df.duplicated()
        duplicate_count = exact_duplicates.sum()
        
        if duplicate_count > 0:
            validation_results['errors'].append(f"Found {duplicate_count} exact duplicate records")
            validation_results['duplicate_info']['exact_duplicates'] = duplicate_count
            validation_results['valid'] = False
        
        # Check for duplicates in key fields
        key_fields = ['make', 'model', 'year', 'price', 'mileage']
        available_key_fields = [field for field in key_fields if field in df.columns]
        
        if available_key_fields:
            key_duplicates = df.duplicated(subset=available_key_fields)
            key_duplicate_count = key_duplicates.sum()
            
            if key_duplicate_count > 0:
                validation_results['errors'].append(f"Found {key_duplicate_count} duplicates in key fields")
                validation_results['duplicate_info']['key_field_duplicates'] = key_duplicate_count
                validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_duplicates',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'duplicate_info': validation_results['duplicate_info']
        })
        
        return validation_results
    
    def validate_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate overall data quality."""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'quality_metrics': {}
        }
        
        # Calculate quality metrics
        total_records = len(df)
        
        # Missing data percentage
        missing_data = df.isnull().sum()
        missing_percentage = (missing_data / total_records * 100).round(2)
        
        # High missing data columns (>20% missing)
        high_missing_columns = missing_percentage[missing_percentage > 20].to_dict()
        if high_missing_columns:
            validation_results['errors'].append(f"High missing data in columns: {high_missing_columns}")
            validation_results['valid'] = False
        
        # Data completeness score
        completeness_score = ((total_records * len(df.columns) - missing_data.sum()) / (total_records * len(df.columns))) * 100
        
        # Uniqueness score
        uniqueness_scores = {}
        for column in df.columns:
            unique_count = df[column].nunique()
            uniqueness_scores[column] = (unique_count / total_records) * 100
        
        avg_uniqueness = np.mean(list(uniqueness_scores.values()))
        
        validation_results['quality_metrics'] = {
            'total_records': total_records,
            'total_columns': len(df.columns),
            'completeness_score': completeness_score,
            'avg_uniqueness_score': avg_uniqueness,
            'missing_percentage': missing_percentage.to_dict(),
            'uniqueness_scores': uniqueness_scores,
            'high_missing_columns': high_missing_columns
        }
        
        # Overall quality assessment
        if completeness_score < 80:
            validation_results['errors'].append(f"Low data completeness: {completeness_score:.1f}%")
            validation_results['valid'] = False
        
        if avg_uniqueness < 50:
            validation_results['errors'].append(f"Low data uniqueness: {avg_uniqueness:.1f}%")
            validation_results['valid'] = False
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_data_quality',
            'timestamp': datetime.now().isoformat(),
            'valid': validation_results['valid'],
            'quality_metrics': validation_results['quality_metrics']
        })
        
        return validation_results
    
    def validate_all(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run comprehensive validation."""
        
        all_results = {
            'overall_valid': True,
            'validation_summary': {},
            'detailed_results': {}
        }
        
        # Run all validation types
        validation_methods = [
            ('data_types', self.validate_data_types),
            ('required_fields', self.validate_required_fields),
            ('value_ranges', self.validate_value_ranges),
            ('allowed_values', self.validate_allowed_values),
            ('string_lengths', self.validate_string_lengths),
            ('data_consistency', self.validate_data_consistency),
            ('duplicates', self.validate_duplicates),
            ('data_quality', self.validate_data_quality)
        ]
        
        for method_name, method_func in validation_methods:
            try:
                result = method_func(df)
                all_results['detailed_results'][method_name] = result
                all_results['validation_summary'][method_name] = result['valid']
                
                if not result['valid']:
                    all_results['overall_valid'] = False
                    
            except Exception as e:
                logger.error(f"Error in validation method {method_name}: {e}")
                all_results['detailed_results'][method_name] = {
                    'valid': False,
                    'errors': [str(e)]
                }
                all_results['validation_summary'][method_name] = False
                all_results['overall_valid'] = False
        
        # Log comprehensive validation
        self.validation_history.append({
            'operation': 'validate_all',
            'timestamp': datetime.now().isoformat(),
            'overall_valid': all_results['overall_valid'],
            'validation_summary': all_results['validation_summary']
        })
        
        return all_results
    
    def generate_validation_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        
        validation_results = self.validate_all(df)
        
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_records': len(df),
                'total_columns': len(df.columns)
            },
            'validation_results': validation_results,
            'recommendations': self._generate_recommendations(validation_results),
            'validation_history': self.validation_history
        }
        
        return report
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        
        recommendations = []
        
        for method_name, result in validation_results['detailed_results'].items():
            if not result['valid']:
                if method_name == 'required_fields':
                    recommendations.append("Add missing required fields or mark them as optional")
                elif method_name == 'data_types':
                    recommendations.append("Convert data types to match expected formats")
                elif method_name == 'value_ranges':
                    recommendations.append("Remove or correct out-of-range values")
                elif method_name == 'allowed_values':
                    recommendations.append("Standardize values to use allowed options")
                elif method_name == 'string_lengths':
                    recommendations.append("Trim or pad string fields to meet length requirements")
                elif method_name == 'data_consistency':
                    recommendations.append("Review and correct inconsistent data relationships")
                elif method_name == 'duplicates':
                    recommendations.append("Remove duplicate records or investigate data collection process")
                elif method_name == 'data_quality':
                    recommendations.append("Improve data collection processes to increase completeness and uniqueness")
        
        if validation_results['overall_valid']:
            recommendations.append("Data validation passed - no immediate action needed")
        
        return recommendations
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validation operations."""
        
        return {
            'total_validations': len(self.validation_history),
            'validation_history': self.validation_history,
            'validation_rules': self.validation_rules,
            'last_updated': datetime.now().isoformat()
        }
