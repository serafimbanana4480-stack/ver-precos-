"""
Data Validation Pipeline
Production-grade data validation and quality checks
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from validation.schemas import ScrapedVehicle, ValidationResult, VehicleType
from validation.normalizers import normalize_vehicle_data

logger = logging.getLogger(__name__)


class DataValidator:
    """Production-grade data validator"""
    
    def __init__(self):
        self.required_fields = {
            VehicleType.carros: ['source', 'source_id', 'url', 'title', 'brand', 'model', 'year', 'price', 'km'],
            VehicleType.motos: ['source', 'source_id', 'url', 'title', 'brand', 'model', 'year', 'price']
        }
        
        self.important_fields = ['description', 'images', 'location', 'fuel_type', 'transmission']
    
    def validate_vehicle(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate vehicle data against schema and business rules
        
        Args:
            data: Raw scraped vehicle data
            
        Returns:
            ValidationResult with validation status and issues
        """
        errors = []
        warnings = []
        missing_fields = []
        
        try:
            # Normalize Portuguese values to English enum values
            normalized_data = normalize_vehicle_data(data)
            
            # Validate against Pydantic schema
            vehicle = ScrapedVehicle(**normalized_data)
            
            # Check required fields for vehicle type (use normalized_data)
            required = self.required_fields.get(vehicle.vehicle_type, [])
            for field in required:
                if field not in normalized_data or normalized_data[field] is None:
                    missing_fields.append(field)
                    errors.append(f"Required field '{field}' is missing")
            
            # Check important fields (warnings only) - use normalized_data
            for field in self.important_fields:
                if field not in normalized_data or normalized_data[field] is None:
                    missing_fields.append(field)
                    warnings.append(f"Important field '{field}' is missing")
            
            # Business rule validations
            self._validate_business_rules(vehicle, errors, warnings)
            
            # Calculate data quality score
            quality_score = self._calculate_quality_score(vehicle, missing_fields)
            
            is_valid = len(errors) == 0
            
            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                missing_fields=missing_fields,
                data_quality_score=quality_score
            )
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Schema validation failed: {str(e)}"],
                warnings=[],
                missing_fields=[],
                data_quality_score=0.0
            )
    
    def _validate_business_rules(self, vehicle: ScrapedVehicle, errors: List[str], warnings: List[str]):
        """Validate business rules"""
        
        # Check for suspicious prices (possible deposits)
        if vehicle.price < 500 and vehicle.vehicle_type == VehicleType.carros:
            warnings.append("Price suspiciously low (possible deposit)")
        
        # Check for unrealistic KM
        if vehicle.km and vehicle.km > 300000:
            warnings.append(f"KM unusually high: {vehicle.km}")
        
        # Check for very old vehicles
        if vehicle.year < 2000:
            warnings.append(f"Vehicle very old: {vehicle.year}")
        
        # Check for missing description (needed for AI analysis)
        if not vehicle.description:
            warnings.append("Description missing - AI analysis will be limited")
        
        # Check for missing images (needed for Vision AI)
        if not vehicle.images or len(vehicle.images) == 0:
            warnings.append("No images - Vision analysis will be skipped")
    
    def _calculate_quality_score(self, vehicle: ScrapedVehicle, missing_fields: List[str]) -> float:
        """
        Calculate data quality score (0-1)
        
        Higher score = better data quality
        """
        total_fields = len(self.required_fields.get(vehicle.vehicle_type, [])) + len(self.important_fields)
        present_fields = total_fields - len(missing_fields)
        
        # Base score from field completeness
        base_score = present_fields / total_fields if total_fields > 0 else 0
        
        # Bonus for having description and images
        bonus = 0.0
        if vehicle.description:
            bonus += 0.1
        if vehicle.images and len(vehicle.images) > 0:
            bonus += 0.1
        
        # Cap at 1.0
        return min(1.0, base_score + bonus)
    
    def validate_batch(self, vehicles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a batch of vehicles
        
        Args:
            vehicles: List of vehicle data dictionaries
            
        Returns:
            Summary of validation results
        """
        results = {
            'total': len(vehicles),
            'valid': 0,
            'invalid': 0,
            'warnings': 0,
            'avg_quality_score': 0.0,
            'common_missing_fields': {},
            'validation_results': []
        }
        
        total_quality = 0.0
        missing_field_counts = {}
        
        for data in vehicles:
            result = self.validate_vehicle(data)
            results['validation_results'].append(result)
            
            if result.is_valid:
                results['valid'] += 1
            else:
                results['invalid'] += 1
            
            if result.warnings:
                results['warnings'] += 1
            
            total_quality += result.data_quality_score
            
            # Track common missing fields
            for field in result.missing_fields:
                missing_field_counts[field] = missing_field_counts.get(field, 0) + 1
        
        # Calculate averages
        if results['total'] > 0:
            results['avg_quality_score'] = total_quality / results['total']
            results['common_missing_fields'] = {
                k: v for k, v in sorted(missing_field_counts.items(), 
                                         key=lambda x: x[1], 
                                         reverse=True)
            }
        
        return results


# Singleton instance
validator = DataValidator()
