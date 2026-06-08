"""
Schema validator for data schema validation.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Schema validator for data schema validation."""
    
    def __init__(self):
        """Initialize schema validator."""
        self.schemas = {}
        self.validation_history = []
        self._load_default_schemas()
    
    def _load_default_schemas(self):
        """Load default schemas for car listings."""
        
        self.schemas['car_listing'] = {
            'type': 'object',
            'required': ['make', 'model', 'year', 'price'],
            'properties': {
                'make': {
                    'type': 'string',
                    'minLength': 1,
                    'maxLength': 50,
                    'description': 'Car manufacturer'
                },
                'model': {
                    'type': 'string',
                    'minLength': 1,
                    'maxLength': 50,
                    'description': 'Car model'
                },
                'year': {
                    'type': 'integer',
                    'minimum': 1900,
                    'maximum': datetime.now().year + 1,
                    'description': 'Manufacturing year'
                },
                'price': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 1000000,
                    'description': 'Price in euros'
                },
                'mileage': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 500000,
                    'description': 'Mileage in kilometers'
                },
                'fuel_type': {
                    'type': 'string',
                    'enum': ['Gasoline', 'Diesel', 'Electric', 'Hybrid', 'LPG', 'CNG', 'Unknown'],
                    'description': 'Fuel type'
                },
                'transmission': {
                    'type': 'string',
                    'enum': ['Automatic', 'Manual', 'CVT', 'Tiptronic', 'DSG', 'Unknown'],
                    'description': 'Transmission type'
                },
                'engine_size': {
                    'type': 'number',
                    'minimum': 0.5,
                    'maximum': 10.0,
                    'description': 'Engine size in liters'
                },
                'location': {
                    'type': 'string',
                    'minLength': 1,
                    'maxLength': 100,
                    'description': 'Location'
                },
                'condition': {
                    'type': 'string',
                    'enum': ['Excellent', 'Good', 'Fair', 'Poor', 'Unknown'],
                    'description': 'Car condition'
                },
                'description': {
                    'type': 'string',
                    'maxLength': 2000,
                    'description': 'Car description'
                },
                'date_scraped': {
                    'type': 'string',
                    'format': 'date-time',
                    'description': 'When the listing was scraped'
                }
            }
        }
        
        self.schemas['market_analysis'] = {
            'type': 'object',
            'required': ['make', 'model', 'avg_price', 'listings_count'],
            'properties': {
                'make': {
                    'type': 'string',
                    'minLength': 1,
                    'maxLength': 50
                },
                'model': {
                    'type': 'string',
                    'minLength': 1,
                    'maxLength': 50
                },
                'avg_price': {
                    'type': 'number',
                    'minimum': 0
                },
                'median_price': {
                    'type': 'number',
                    'minimum': 0
                },
                'min_price': {
                    'type': 'number',
                    'minimum': 0
                },
                'max_price': {
                    'type': 'number',
                    'minimum': 0
                },
                'listings_count': {
                    'type': 'integer',
                    'minimum': 0
                },
                'price_std': {
                    'type': 'number',
                    'minimum': 0
                }
            }
        }
    
    def validate_schema(self, data: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
        """Validate data against a schema."""
        
        if schema_name not in self.schemas:
            return {
                'valid': False,
                'errors': [f"Schema '{schema_name}' not found"],
                'schema_name': schema_name
            }
        
        schema = self.schemas[schema_name]
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'schema_name': schema_name
        }
        
        # Validate type
        if schema.get('type') == 'object':
            if not isinstance(data, dict):
                validation_result['errors'].append("Data must be an object")
                validation_result['valid'] = False
                return validation_result
        
        # Validate required fields
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in data:
                validation_result['errors'].append(f"Required field '{field}' is missing")
                validation_result['valid'] = False
        
        # Validate properties
        properties = schema.get('properties', {})
        for field, field_schema in properties.items():
            if field in data:
                field_validation = self._validate_field(data[field], field_schema, field)
                
                if not field_validation['valid']:
                    validation_result['errors'].extend(field_validation['errors'])
                    validation_result['valid'] = False
                
                validation_result['warnings'].extend(field_validation['warnings'])
        
        # Check for additional fields
        allowed_fields = set(properties.keys())
        data_fields = set(data.keys())
        additional_fields = data_fields - allowed_fields
        
        if additional_fields:
            validation_result['warnings'].append(f"Additional fields found: {list(additional_fields)}")
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_schema',
            'timestamp': datetime.now().isoformat(),
            'schema_name': schema_name,
            'valid': validation_result['valid'],
            'errors_count': len(validation_result['errors']),
            'warnings_count': len(validation_result['warnings'])
        })
        
        return validation_result
    
    def _validate_field(self, value: Any, field_schema: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Validate a single field against its schema."""
        
        result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Type validation
        expected_type = field_schema.get('type')
        if expected_type:
            type_validation = self._validate_type(value, expected_type, field_name)
            if not type_validation['valid']:
                result['errors'].extend(type_validation['errors'])
                result['valid'] = False
        
        # String-specific validations
        if expected_type == 'string' and isinstance(value, str):
            # Length validation
            min_length = field_schema.get('minLength')
            if min_length is not None and len(value) < min_length:
                result['errors'].append(f"Field '{field_name}' must be at least {min_length} characters long")
                result['valid'] = False
            
            max_length = field_schema.get('maxLength')
            if max_length is not None and len(value) > max_length:
                result['errors'].append(f"Field '{field_name}' must be no more than {max_length} characters long")
                result['valid'] = False
            
            # Enum validation
            enum_values = field_schema.get('enum')
            if enum_values and value not in enum_values:
                result['errors'].append(f"Field '{field_name}' must be one of: {enum_values}")
                result['valid'] = False
        
        # Number-specific validations
        elif expected_type in ['number', 'integer'] and isinstance(value, (int, float)):
            # Range validation
            minimum = field_schema.get('minimum')
            if minimum is not None and value < minimum:
                result['errors'].append(f"Field '{field_name}' must be at least {minimum}")
                result['valid'] = False
            
            maximum = field_schema.get('maximum')
            if maximum is not None and value > maximum:
                result['errors'].append(f"Field '{field_name}' must be no more than {maximum}")
                result['valid'] = False
            
            # Integer-specific validation
            if expected_type == 'integer' and not isinstance(value, int):
                result['errors'].append(f"Field '{field_name}' must be an integer")
                result['valid'] = False
        
        # Format validation
        format_type = field_schema.get('format')
        if format_type:
            format_validation = self._validate_format(value, format_type, field_name)
            if not format_validation['valid']:
                result['errors'].extend(format_validation['errors'])
                result['valid'] = False
        
        return result
    
    def _validate_type(self, value: Any, expected_type: str, field_name: str) -> Dict[str, Any]:
        """Validate data type."""
        
        result = {
            'valid': True,
            'errors': []
        }
        
        type_mapping = {
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        
        if expected_python_type:
            if not isinstance(value, expected_python_type):
                result['errors'].append(f"Field '{field_name}' must be of type {expected_type}")
                result['valid'] = False
        
        return result
    
    def _validate_format(self, value: Any, format_type: str, field_name: str) -> Dict[str, Any]:
        """Validate data format."""
        
        result = {
            'valid': True,
            'errors': []
        }
        
        if format_type == 'date-time':
            if isinstance(value, str):
                try:
                    # Try to parse as datetime
                    from datetime import datetime
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except:
                    result['errors'].append(f"Field '{field_name}' must be a valid ISO date-time string")
                    result['valid'] = False
            else:
                result['errors'].append(f"Field '{field_name}' must be a string for date-time format")
                result['valid'] = False
        
        return result
    
    def validate_dataframe_schema(self, df: pd.DataFrame, schema_name: str) -> Dict[str, Any]:
        """Validate a DataFrame against a schema."""
        
        if schema_name not in self.schemas:
            return {
                'valid': False,
                'errors': [f"Schema '{schema_name}' not found"],
                'schema_name': schema_name
            }
        
        schema = self.schemas[schema_name]
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'schema_name': schema_name,
            'row_validations': {}
        }
        
        # Check required columns
        required_fields = schema.get('required', [])
        missing_columns = [field for field in required_fields if field not in df.columns]
        
        if missing_columns:
            validation_result['errors'].append(f"Missing required columns: {missing_columns}")
            validation_result['valid'] = False
        
        # Validate each row
        valid_rows = 0
        for idx, row in df.iterrows():
            row_data = row.to_dict()
            row_validation = self.validate_schema(row_data, schema_name)
            
            if not row_validation['valid']:
                validation_result['row_validations'][idx] = row_validation['errors']
            else:
                valid_rows += 1
        
        # Add summary statistics
        validation_result['summary'] = {
            'total_rows': len(df),
            'valid_rows': valid_rows,
            'invalid_rows': len(df) - valid_rows,
            'validation_rate': (valid_rows / len(df)) * 100 if len(df) > 0 else 0
        }
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_dataframe_schema',
            'timestamp': datetime.now().isoformat(),
            'schema_name': schema_name,
            'valid': validation_result['valid'],
            'summary': validation_result['summary']
        })
        
        return validation_result
    
    def add_custom_schema(self, schema_name: str, schema: Dict[str, Any]) -> bool:
        """Add a custom schema."""
        
        try:
            # Basic schema validation
            if not isinstance(schema, dict):
                logger.error("Schema must be a dictionary")
                return False
            
            if 'type' not in schema:
                logger.error("Schema must have a 'type' field")
                return False
            
            if schema['type'] != 'object':
                logger.error("Only object schemas are supported")
                return False
            
            self.schemas[schema_name] = schema
            
            logger.info(f"Custom schema '{schema_name}' added successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error adding custom schema: {e}")
            return False
    
    def load_schema_from_file(self, filepath: str, schema_name: str) -> bool:
        """Load schema from JSON file."""
        
        try:
            with open(filepath, 'r') as f:
                schema = json.load(f)
            
            return self.add_custom_schema(schema_name, schema)
            
        except Exception as e:
            logger.error(f"Error loading schema from file: {e}")
            return False
    
    def save_schema_to_file(self, schema_name: str, filepath: str) -> bool:
        """Save schema to JSON file."""
        
        if schema_name not in self.schemas:
            logger.error(f"Schema '{schema_name}' not found")
            return False
        
        try:
            with open(filepath, 'w') as f:
                json.dump(self.schemas[schema_name], f, indent=2)
            
            logger.info(f"Schema '{schema_name}' saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving schema to file: {e}")
            return False
    
    def get_schema_info(self, schema_name: str) -> Dict[str, Any]:
        """Get information about a schema."""
        
        if schema_name not in self.schemas:
            return {'error': f"Schema '{schema_name}' not found"}
        
        schema = self.schemas[schema_name]
        
        info = {
            'schema_name': schema_name,
            'type': schema.get('type'),
            'required_fields': schema.get('required', []),
            'total_fields': len(schema.get('properties', {})),
            'field_details': {}
        }
        
        # Add field details
        properties = schema.get('properties', {})
        for field_name, field_schema in properties.items():
            info['field_details'][field_name] = {
                'type': field_schema.get('type'),
                'required': field_name in info['required_fields'],
                'description': field_schema.get('description', ''),
                'constraints': {
                    'min_length': field_schema.get('minLength'),
                    'max_length': field_schema.get('maxLength'),
                    'minimum': field_schema.get('minimum'),
                    'maximum': field_schema.get('maximum'),
                    'enum': field_schema.get('enum'),
                    'format': field_schema.get('format')
                }
            }
        
        return info
    
    def list_schemas(self) -> List[str]:
        """List all available schemas."""
        
        return list(self.schemas.keys())
    
    def validate_batch(self, data_list: List[Dict[str, Any]], schema_name: str) -> Dict[str, Any]:
        """Validate multiple records against a schema."""
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'schema_name': schema_name,
            'summary': {
                'total_records': len(data_list),
                'valid_records': 0,
                'invalid_records': 0,
                'validation_rate': 0
            },
            'record_validations': {}
        }
        
        valid_records = 0
        
        for i, data in enumerate(data_list):
            record_validation = self.validate_schema(data, schema_name)
            
            if not record_validation['valid']:
                validation_result['record_validations'][i] = record_validation['errors']
            else:
                valid_records += 1
        
        invalid_records = len(data_list) - valid_records
        
        validation_result['summary']['valid_records'] = valid_records
        validation_result['summary']['invalid_records'] = invalid_records
        validation_result['summary']['validation_rate'] = (valid_records / len(data_list)) * 100 if len(data_list) > 0 else 0
        
        validation_result['valid'] = invalid_records == 0
        
        # Log validation
        self.validation_history.append({
            'operation': 'validate_batch',
            'timestamp': datetime.now().isoformat(),
            'schema_name': schema_name,
            'valid': validation_result['valid'],
            'summary': validation_result['summary']
        })
        
        return validation_result
    
    def generate_schema_report(self) -> Dict[str, Any]:
        """Generate comprehensive schema validation report."""
        
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_schemas': len(self.schemas)
            },
            'available_schemas': self.list_schemas(),
            'schema_details': {},
            'validation_history': self.validation_history
        }
        
        # Add details for each schema
        for schema_name in self.schemas:
            report['schema_details'][schema_name] = self.get_schema_info(schema_name)
        
        return report
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validation operations."""
        
        return {
            'total_validations': len(self.validation_history),
            'validation_history': self.validation_history,
            'available_schemas': self.list_schemas(),
            'last_updated': datetime.now().isoformat()
        }
