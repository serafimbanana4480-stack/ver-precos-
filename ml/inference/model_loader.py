"""
Model loader for ML inference.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
import joblib
import os
import json
from datetime import datetime
import hashlib

from ..models import XGBoostModel, RandomForestModel, LinearRegressionModel, NeuralNetworkModel, SVMModel, KNNModel


class ModelLoader:
    """Model loader for managing ML models."""
    
    def __init__(self, model_dir: str = "models"):
        """Initialize model loader."""
        self.model_dir = model_dir
        self.loaded_models = {}
        self.model_metadata = {}
        self.model_registry = {}
        
        # Create models directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
        
        # Load model registry
        self._load_model_registry()
    
    def _load_model_registry(self) -> None:
        """Load model registry from file."""
        registry_path = os.path.join(self.model_dir, "model_registry.json")
        
        if os.path.exists(registry_path):
            with open(registry_path, 'r') as f:
                self.model_registry = json.load(f)
    
    def _save_model_registry(self) -> None:
        """Save model registry to file."""
        registry_path = os.path.join(self.model_dir, "model_registry.json")
        
        with open(registry_path, 'w') as f:
            json.dump(self.model_registry, f, indent=2, default=str)
    
    def register_model(self, 
                       model_name: str, 
                       model_path: str, 
                       metadata: Dict[str, Any] = None) -> None:
        """Register a model in the registry."""
        if metadata is None:
            metadata = {}
        
        # Calculate model file hash
        file_hash = self._calculate_file_hash(model_path)
        
        # Get model file info
        file_info = os.stat(model_path)
        
        registry_entry = {
            'model_name': model_name,
            'model_path': model_path,
            'file_hash': file_hash,
            'file_size': file_info.st_size,
            'created_at': datetime.fromtimestamp(file_info.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(file_info.st_mtime).isoformat(),
            'registered_at': datetime.now().isoformat(),
            'metadata': metadata
        }
        
        self.model_registry[model_name] = registry_entry
        self._save_model_registry()
    
    def _calculate_file_hash(self, filepath: str) -> str:
        """Calculate SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    def load_model(self, model_name: str, version: str = 'latest') -> Any:
        """Load a model from disk."""
        cache_key = f"{model_name}_{version}"
        
        # Check if model is already loaded
        if cache_key in self.loaded_models:
            return self.loaded_models[cache_key]
        
        # Determine model path
        if version == 'latest':
            model_path = os.path.join(self.model_dir, f"{model_name}_latest.pkl")
        else:
            model_path = os.path.join(self.model_dir, f"{model_name}_{version}.pkl")
        
        # Check if model exists
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        # Load model
        try:
            model = joblib.load(model_path)
            self.loaded_models[cache_key] = model
            
            # Load metadata if available
            metadata_path = model_path.replace('.pkl', '_metadata.json')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    self.model_metadata[cache_key] = json.load(f)
            
            return model
            
        except Exception as e:
            raise RuntimeError(f"Failed to load model {model_name}: {e}")
    
    def load_model_with_metadata(self, model_name: str, version: str = 'latest') -> tuple:
        """Load model along with its metadata."""
        model = self.load_model(model_name, version)
        cache_key = f"{model_name}_{version}"
        
        metadata = self.model_metadata.get(cache_key, {})
        
        return model, metadata
    
    def get_available_models(self) -> List[str]:
        """Get list of available model names."""
        models = []
        
        for filename in os.listdir(self.model_dir):
            if filename.endswith('.pkl') and not filename.startswith('temp_'):
                model_name = filename.replace('_latest.pkl', '').replace('.pkl', '')
                if model_name not in models:
                    models.append(model_name)
        
        return models
    
    def get_model_versions(self, model_name: str) -> List[str]:
        """Get available versions for a model."""
        versions = []
        
        for filename in os.listdir(self.model_dir):
            if filename.startswith(f"{model_name}_") and filename.endswith('.pkl'):
                version = filename.replace(f"{model_name}_", "").replace('.pkl', '')
                if version != 'latest':
                    versions.append(version)
        
        return sorted(versions)
    
    def get_model_info(self, model_name: str, version: str = 'latest') -> Dict[str, Any]:
        """Get information about a model."""
        if model_name in self.model_registry:
            registry_info = self.model_registry[model_name]
        else:
            registry_info = {}
        
        # Get file info
        if version == 'latest':
            model_path = os.path.join(self.model_dir, f"{model_name}_latest.pkl")
        else:
            model_path = os.path.join(self.model_dir, f"{model_name}_{version}.pkl")
        
        if os.path.exists(model_path):
            file_info = os.stat(model_path)
            file_hash = self._calculate_file_hash(model_path)
            
            file_info_dict = {
                'file_path': model_path,
                'file_size': file_info.st_size,
                'file_hash': file_hash,
                'created_at': datetime.fromtimestamp(file_info.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(file_info.st_mtime).isoformat()
            }
        else:
            file_info_dict = {}
        
        # Get metadata
        cache_key = f"{model_name}_{version}"
        metadata = self.model_metadata.get(cache_key, {})
        
        return {
            'model_name': model_name,
            'version': version,
            'registry_info': registry_info,
            'file_info': file_info_dict,
            'metadata': metadata,
            'is_loaded': cache_key in self.loaded_models
        }
    
    def unload_model(self, model_name: str, version: str = 'latest') -> None:
        """Unload a model from memory."""
        cache_key = f"{model_name}_{version}"
        
        if cache_key in self.loaded_models:
            del self.loaded_models[cache_key]
        
        if cache_key in self.model_metadata:
            del self.model_metadata[cache_key]
    
    def unload_all_models(self) -> None:
        """Unload all models from memory."""
        self.loaded_models.clear()
        self.model_metadata.clear()
    
    def validate_model(self, model_name: str, version: str = 'latest') -> Dict[str, Any]:
        """Validate a model file."""
        if version == 'latest':
            model_path = os.path.join(self.model_dir, f"{model_name}_latest.pkl")
        else:
            model_path = os.path.join(self.model_dir, f"{model_name}_{version}.pkl")
        
        validation_results = {
            'model_name': model_name,
            'version': version,
            'file_exists': os.path.exists(model_path),
            'file_readable': False,
            'model_loadable': False,
            'model_attributes': {},
            'validation_errors': []
        }
        
        if not os.path.exists(model_path):
            validation_results['validation_errors'].append("Model file does not exist")
            return validation_results
        
        try:
            # Check if file is readable
            with open(model_path, 'rb') as f:
                f.read(1024)  # Try to read first 1KB
            
            validation_results['file_readable'] = True
            
            # Try to load model
            model = joblib.load(model_path)
            validation_results['model_loadable'] = True
            
            # Check model attributes
            if hasattr(model, 'predict'):
                validation_results['model_attributes']['has_predict'] = True
            
            if hasattr(model, 'feature_importance'):
                validation_results['model_attributes']['has_feature_importance'] = True
            
            if hasattr(model, 'is_trained'):
                validation_results['model_attributes']['is_trained'] = model.is_trained
            
            if hasattr(model, 'feature_names'):
                validation_results['model_attributes']['feature_names'] = model.feature_names
            
        except Exception as e:
            validation_results['validation_errors'].append(f"Error loading model: {e}")
        
        return validation_results
    
    def get_model_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics for loaded models."""
        memory_info = {}
        
        for cache_key, model in self.loaded_models.items():
            try:
                # Estimate memory usage (rough approximation)
                model_size = len(joblib.dumps(model)) / (1024 * 1024)  # MB
                
                memory_info[cache_key] = {
                    'estimated_size_mb': model_size,
                    'model_type': type(model).__name__
                }
            except Exception:
                memory_info[cache_key] = {
                    'estimated_size_mb': 'unknown',
                    'model_type': type(model).__name__
                }
        
        total_memory = sum(
            info['estimated_size_mb'] for info in memory_info.values()
            if isinstance(info['estimated_size_mb'], (int, float))
        )
        
        return {
            'model_memory_info': memory_info,
            'total_estimated_memory_mb': total_memory,
            'loaded_models_count': len(self.loaded_models)
        }
    
    def cleanup_old_models(self, keep_versions: int = 5) -> Dict[str, Any]:
        """Clean up old model versions, keeping only the most recent ones."""
        cleanup_results = {
            'models_cleaned': [],
            'files_deleted': [],
            'errors': []
        }
        
        for model_name in self.get_available_models():
            versions = self.get_model_versions(model_name)
            
            if len(versions) > keep_versions:
                # Sort versions and keep only the most recent ones
                versions_to_delete = versions[:-keep_versions]
                
                for version in versions_to_delete:
                    model_path = os.path.join(self.model_dir, f"{model_name}_{version}.pkl")
                    metadata_path = os.path.join(self.model_dir, f"{model_name}_{version}_metadata.json")
                    
                    try:
                        if os.path.exists(model_path):
                            os.remove(model_path)
                            cleanup_results['files_deleted'].append(model_path)
                        
                        if os.path.exists(metadata_path):
                            os.remove(metadata_path)
                            cleanup_results['files_deleted'].append(metadata_path)
                        
                        cleanup_results['models_cleaned'].append(f"{model_name}_{version}")
                        
                    except Exception as e:
                        cleanup_results['errors'].append(f"Error deleting {model_name}_{version}: {e}")
        
        return cleanup_results
    
    def export_model_info(self, output_path: str) -> None:
        """Export model registry and information to a JSON file."""
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'model_registry': self.model_registry,
            'loaded_models': list(self.loaded_models.keys()),
            'available_models': self.get_available_models(),
            'memory_usage': self.get_model_memory_usage()
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
