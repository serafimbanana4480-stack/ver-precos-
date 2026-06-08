"""
ML model evaluator for testing.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import time
import warnings
warnings.filterwarnings('ignore')


class ModelEvaluator:
    """ML model evaluator for testing."""
    
    def __init__(self):
        """Initialize evaluator."""
        self.evaluation_history = {}
        
    def evaluate_model_performance(self, 
                                  model: Any, 
                                  X_test: pd.DataFrame, 
                                  y_test: pd.Series,
                                  model_name: str = "Model") -> Dict[str, Any]:
        """Evaluate model performance on test data."""
        
        start_time = time.time()
        
        # Make predictions
        y_pred = model.predict(X_test)
        
        # Calculate metrics
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        # Calculate prediction time
        prediction_time = time.time() - start_time
        
        evaluation = {
            'model_name': model_name,
            'metrics': {
                'mse': mse,
                'rmse': rmse,
                'mae': mae,
                'r2': r2
            },
            'prediction_time_seconds': prediction_time,
            'samples_tested': len(X_test),
            'features_used': X_test.shape[1]
        }
        
        self.evaluation_history[model_name] = evaluation
        
        return evaluation
    
    def validate_model_predictions(self, 
                                 model: Any, 
                                 X_test: pd.DataFrame, 
                                 y_test: pd.Series) -> Dict[str, Any]:
        """Validate model predictions for correctness."""
        
        try:
            # Test basic prediction
            y_pred = model.predict(X_test)
            
            # Check prediction length
            length_correct = len(y_pred) == len(y_test)
            
            # Check for NaN values
            has_nan = np.isnan(y_pred).any()
            
            # Check for infinite values
            has_inf = np.isinf(y_pred).any()
            
            # Check prediction range (reasonable car prices)
            min_price, max_price = 100, 1000000
            in_range = np.all((y_pred >= min_price) & (y_pred <= max_price))
            
            validation = {
                'prediction_length_correct': length_correct,
                'has_nan_predictions': has_nan,
                'has_inf_predictions': has_inf,
                'predictions_in_reasonable_range': in_range,
                'validation_passed': length_correct and not has_nan and not has_inf and in_range
            }
            
            return validation
            
        except Exception as e:
            return {
                'validation_passed': False,
                'error': str(e)
            }
    
    def test_model_robustness(self, 
                             model: Any, 
                             X_test: pd.DataFrame, 
                             y_test: pd.Series) -> Dict[str, Any]:
        """Test model robustness with edge cases."""
        
        robustness_results = {}
        
        try:
            # Test with empty data
            try:
                empty_pred = model.predict(X_test.iloc[0:0])
                robustness_results['empty_data_handled'] = True
            except:
                robustness_results['empty_data_handled'] = False
            
            # Test with single sample
            try:
                single_pred = model.predict(X_test.iloc[0:1])
                robustness_results['single_sample_handled'] = True
            except:
                robustness_results['single_sample_handled'] = False
            
            # Test with corrupted data (add noise)
            noisy_X = X_test.copy()
            noisy_X.iloc[:, 0] += np.random.normal(0, 100, len(noisy_X))
            
            try:
                noisy_pred = model.predict(noisy_X)
                robustness_results['noisy_data_handled'] = True
            except:
                robustness_results['noisy_data_handled'] = False
            
            # Test with missing values
            missing_X = X_test.copy()
            missing_X.iloc[0, 0] = np.nan
            
            try:
                missing_pred = model.predict(missing_X)
                robustness_results['missing_values_handled'] = True
            except:
                robustness_results['missing_values_handled'] = False
            
        except Exception as e:
            robustness_results['error'] = str(e)
        
        return robustness_results
    
    def compare_model_versions(self, 
                             models: Dict[str, Any], 
                             X_test: pd.DataFrame, 
                             y_test: pd.Series) -> pd.DataFrame:
        """Compare multiple model versions."""
        
        comparison_results = []
        
        for model_name, model in models.items():
            try:
                evaluation = self.evaluate_model_performance(model, X_test, y_test, model_name)
                comparison_results.append({
                    'Model': model_name,
                    'R2': evaluation['metrics']['r2'],
                    'RMSE': evaluation['metrics']['rmse'],
                    'MAE': evaluation['metrics']['mae'],
                    'Prediction_Time': evaluation['prediction_time_seconds']
                })
            except Exception as e:
                comparison_results.append({
                    'Model': model_name,
                    'Error': str(e)
                })
        
        return pd.DataFrame(comparison_results)
    
    def get_evaluation_summary(self) -> Dict[str, Any]:
        """Get summary of all evaluations."""
        
        if not self.evaluation_history:
            return {'message': 'No evaluations performed yet'}
        
        summary = {
            'total_evaluations': len(self.evaluation_history),
            'models_evaluated': list(self.evaluation_history.keys()),
            'best_model_by_r2': None,
            'best_model_by_rmse': None
        }
        
        # Find best models
        best_r2 = -float('inf')
        best_rmse = float('inf')
        
        for model_name, evaluation in self.evaluation_history.items():
            r2 = evaluation['metrics']['r2']
            rmse = evaluation['metrics']['rmse']
            
            if r2 > best_r2:
                best_r2 = r2
                summary['best_model_by_r2'] = model_name
            
            if rmse < best_rmse:
                best_rmse = rmse
                summary['best_model_by_rmse'] = model_name
        
        return summary
