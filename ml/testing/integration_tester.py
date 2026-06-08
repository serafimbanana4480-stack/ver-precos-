"""
Integration testing for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class IntegrationTester:
    """Integration testing for ML models."""
    
    def __init__(self, test_data_dir: str = "test_data"):
        """Initialize integration tester."""
        self.test_data_dir = test_data_dir
        os.makedirs(test_data_dir, exist_ok=True)
        self.test_results = {}
        
    def test_end_to_end_pipeline(self, 
                               model_class: Any,
                               raw_data: pd.DataFrame,
                               target_column: str) -> Dict[str, Any]:
        """Test end-to-end ML pipeline."""
        
        pipeline_results = {
            'data_preprocessing': False,
            'model_training': False,
            'model_prediction': False,
            'pipeline_complete': False,
            'error': None
        }
        
        try:
            # Step 1: Data preprocessing
            from ..utils.data_preprocessing import DataPreprocessor
            
            preprocessor = DataPreprocessor()
            X, y = preprocessor.preprocess_pipeline(raw_data, target_column)
            
            pipeline_results['data_preprocessing'] = True
            
            # Step 2: Model training
            model = model_class()
            training_metrics = model.train(X, y)
            
            pipeline_results['model_training'] = True
            
            # Step 3: Model prediction
            predictions = model.predict(X.head(10))
            
            pipeline_results['model_prediction'] = True
            pipeline_results['pipeline_complete'] = True
            
            pipeline_results['training_metrics'] = training_metrics
            pipeline_results['sample_predictions'] = predictions.tolist()[:5]
            
        except Exception as e:
            pipeline_results['error'] = str(e)
        
        return pipeline_results
    
    def test_model_persistence(self, 
                             model: Any,
                             test_data: pd.DataFrame) -> Dict[str, Any]:
        """Test model saving and loading."""
        
        persistence_results = {
            'model_saved': False,
            'model_loaded': False,
            'predictions_match': False,
            'error': None
        }
        
        try:
            # Make original predictions
            original_predictions = model.predict(test_data)
            
            # Save model
            from ..utils.model_utils import ModelUtils
            
            utils = ModelUtils()
            model_path = utils.save_model_with_metadata(model, "test_model")
            
            persistence_results['model_saved'] = True
            
            # Load model
            loaded_model, metadata = utils.load_model_with_metadata(model_path)
            
            persistence_results['model_loaded'] = True
            
            # Make predictions with loaded model
            loaded_predictions = loaded_model.predict(test_data)
            
            # Check if predictions match
            predictions_match = np.allclose(original_predictions, loaded_predictions, rtol=1e-5)
            persistence_results['predictions_match'] = predictions_match
            
            persistence_results['metadata'] = metadata
            
        except Exception as e:
            persistence_results['error'] = str(e)
        
        return persistence_results
    
    def test_api_integration(self, 
                            model: Any,
                            sample_request: Dict[str, Any]) -> Dict[str, Any]:
        """Test API integration."""
        
        api_results = {
            'api_response_valid': False,
            'prediction_reasonable': False,
            'error': None
        }
        
        try:
            from ..inference.api_predictor import APIPredictor
            
            # Create API predictor
            api_predictor = APIPredictor()
            
            # Load model into API
            api_predictor.predictor.loaded_models['test_model'] = model
            api_predictor.predictor.default_model = 'test_model'
            
            # Test single prediction
            response = api_predictor.predictor.predict_single(sample_request)
            
            api_results['api_response_valid'] = True
            
            # Check if prediction is reasonable
            predicted_price = response.get('predicted_price', 0)
            api_results['prediction_reasonable'] = 100 <= predicted_price <= 1000000
            
            api_results['response'] = response
            
        except Exception as e:
            api_results['error'] = str(e)
        
        return api_results
    
    def test_batch_processing(self, 
                             model: Any,
                             batch_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test batch processing capabilities."""
        
        batch_results = {
            'batch_processed': False,
            'all_predictions_valid': False,
            'processing_time_reasonable': False,
            'error': None
        }
        
        try:
            from ..inference.batch_predictor import BatchPredictor
            
            batch_predictor = BatchPredictor()
            batch_predictor.predictor.loaded_models['test_model'] = model
            batch_predictor.predictor.default_model = 'test_model'
            
            # Process batch
            import time
            start_time = time.time()
            predictions = batch_predictor.predictor.predict_batch(batch_data)
            end_time = time.time()
            
            batch_results['batch_processed'] = True
            
            # Check all predictions are valid
            all_valid = all(
                100 <= pred['predicted_price'] <= 1000000 
                for pred in predictions
            )
            batch_results['all_predictions_valid'] = all_valid
            
            # Check processing time is reasonable (< 1 second per sample)
            processing_time = end_time - start_time
            time_per_sample = processing_time / len(batch_data)
            batch_results['processing_time_reasonable'] = time_per_sample < 1.0
            
            batch_results['processing_time_seconds'] = processing_time
            batch_results['time_per_sample_seconds'] = time_per_sample
            batch_results['predictions_count'] = len(predictions)
            
        except Exception as e:
            batch_results['error'] = str(e)
        
        return batch_results
    
    def test_data_pipeline_integration(self, 
                                     raw_data_path: str,
                                     target_column: str) -> Dict[str, Any]:
        """Test complete data pipeline integration."""
        
        pipeline_results = {
            'data_loaded': False,
            'preprocessing_complete': False,
            'feature_engineering_complete': False,
            'data_split_complete': False,
            'error': None
        }
        
        try:
            # Load data
            if raw_data_path.endswith('.csv'):
                data = pd.read_csv(raw_data_path)
            elif raw_data_path.endswith('.json'):
                data = pd.read_json(raw_data_path)
            else:
                raise ValueError("Unsupported file format")
            
            pipeline_results['data_loaded'] = True
            
            # Test preprocessing
            from ..utils.data_preprocessing import DataPreprocessor
            
            preprocessor = DataPreprocessor()
            X, y = preprocessor.preprocess_pipeline(data, target_column)
            
            pipeline_results['preprocessing_complete'] = True
            
            # Test feature engineering
            from ..utils.features import FeatureEngineer
            
            feature_engineer = FeatureEngineer()
            X_engineered = feature_engineer.extract_car_features(X)
            
            pipeline_results['feature_engineering_complete'] = True
            
            # Test data splitting
            X_train, X_val, X_test, y_train, y_val, y_test = preprocessor.split_data(X_engineered, y)
            
            pipeline_results['data_split_complete'] = True
            
            pipeline_results['data_shape'] = {
                'original': data.shape,
                'processed': X.shape,
                'engineered': X_engineered.shape,
                'train': X_train.shape,
                'val': X_val.shape,
                'test': X_test.shape
            }
            
        except Exception as e:
            pipeline_results['error'] = str(e)
        
        return pipeline_results
    
    def test_model_monitoring_integration(self, 
                                        model: Any,
                                        test_data: pd.DataFrame) -> Dict[str, Any]:
        """Test model monitoring integration."""
        
        monitoring_results = {
            'monitoring_data_generated': False,
            'metrics_calculated': False,
            'alerts_triggered': False,
            'error': None
        }
        
        try:
            # Generate monitoring data
            predictions = model.predict(test_data)
            
            # Calculate metrics
            from ..utils.evaluation import ModelEvaluator
            
            evaluator = ModelEvaluator()
            
            # Create dummy actual values for testing
            actual_values = predictions + np.random.normal(0, predictions * 0.1, len(predictions))
            
            evaluation = evaluator.evaluate_regression_model(
                actual_values, predictions, "test_model"
            )
            
            monitoring_results['monitoring_data_generated'] = True
            monitoring_results['metrics_calculated'] = True
            
            # Check for alerts (e.g., poor performance)
            r2_score = evaluation['metrics']['r2']
            monitoring_results['alerts_triggered'] = r2_score < 0.5
            
            monitoring_results['evaluation_metrics'] = evaluation['metrics']
            
        except Exception as e:
            monitoring_results['error'] = str(e)
        
        return monitoring_results
    
    def run_comprehensive_integration_test(self, 
                                        model_class: Any,
                                        raw_data: pd.DataFrame,
                                        target_column: str) -> Dict[str, Any]:
        """Run comprehensive integration test suite."""
        
        all_results = {}
        
        print("Running end-to-end pipeline test...")
        all_results['end_to_end_pipeline'] = self.test_end_to_end_pipeline(
            model_class, raw_data, target_column
        )
        
        # Only run other tests if pipeline succeeded
        if all_results['end_to_end_pipeline'].get('pipeline_complete', False):
            # Create a trained model for other tests
            from ..utils.data_preprocessing import DataPreprocessor
            
            preprocessor = DataPreprocessor()
            X, y = preprocessor.preprocess_pipeline(raw_data, target_column)
            
            model = model_class()
            model.train(X, y)
            
            # Prepare test data
            test_X = X.head(10)
            
            print("Testing model persistence...")
            all_results['model_persistence'] = self.test_model_persistence(model, test_X)
            
            print("Testing API integration...")
            sample_request = X.iloc[0].to_dict()
            all_results['api_integration'] = self.test_api_integration(model, sample_request)
            
            print("Testing batch processing...")
            batch_data = [X.iloc[i].to_dict() for i in range(min(5, len(X)))]
            all_results['batch_processing'] = self.test_batch_processing(model, batch_data)
            
            print("Testing model monitoring...")
            all_results['model_monitoring'] = self.test_model_monitoring_integration(model, test_X)
        
        return all_results
    
    def generate_integration_report(self, test_results: Dict[str, Any]) -> str:
        """Generate integration test report."""
        
        report = f"""
# Integration Test Report
Generated: {datetime.now().isoformat()}

## Test Results Summary
"""
        
        for test_name, results in test_results.items():
            status = "PASSED" if results.get('pipeline_complete') or results.get('model_saved') or results.get('api_response_valid') else "FAILED"
            
            report += f"""
### {test_name.replace('_', ' ').title()}
- Status: {status}
"""
            
            if 'error' in results:
                report += f"- Error: {results['error']}\n"
            
            # Add specific metrics based on test type
            if 'training_metrics' in results:
                report += f"- Training R2: {results['training_metrics'].get('val_r2', 'N/A'):.4f}\n"
            
            if 'processing_time_seconds' in results:
                report += f"- Processing Time: {results['processing_time_seconds']:.4f}s\nn"
        
        return report
    
    def save_test_results(self, test_results: Dict[str, Any], filename: str = None) -> str:
        """Save test results to file."""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"integration_test_results_{timestamp}.json"
        
        filepath = os.path.join(self.test_data_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(test_results, f, indent=2, default=str)
        
        return filepath
