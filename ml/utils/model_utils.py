"""
Model utilities for ML operations.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
import joblib
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report
import warnings
warnings.filterwarnings('ignore')


class ModelUtils:
    """Utilities for ML model operations."""
    
    def __init__(self, output_dir: str = "ml_outputs"):
        """Initialize model utilities."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def save_model_with_metadata(self, 
                                model: Any, 
                                model_name: str, 
                                metadata: Dict[str, Any] = None,
                                version: str = None) -> str:
        """Save model with comprehensive metadata."""
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Model file path
        model_path = os.path.join(self.output_dir, f"{model_name}_{version}.pkl")
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            'model_name': model_name,
            'version': version,
            'saved_at': datetime.now().isoformat(),
            'model_type': type(model).__name__,
            'model_size_bytes': len(joblib.dumps(model))
        })
        
        # Add model-specific metadata
        if hasattr(model, 'feature_importances_'):
            metadata['has_feature_importance'] = True
        
        if hasattr(model, 'n_features_in_'):
            metadata['n_features'] = model.n_features_in_
        
        if hasattr(model, 'is_trained'):
            metadata['is_trained'] = model.is_trained
        
        # Save model
        joblib.dump(model, model_path)
        
        # Save metadata
        metadata_path = os.path.join(self.output_dir, f"{model_name}_{version}_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return model_path
    
    def load_model_with_metadata(self, model_path: str) -> Tuple[Any, Dict[str, Any]]:
        """Load model with metadata."""
        # Load model
        model = joblib.load(model_path)
        
        # Load metadata
        metadata_path = model_path.replace('.pkl', '_metadata.json')
        metadata = {}
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        
        return model, metadata
    
    def compare_models(self, 
                      models: Dict[str, Any], 
                      X_test: pd.DataFrame, 
                      y_test: pd.Series) -> pd.DataFrame:
        """Compare multiple models performance."""
        from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
        
        results = []
        
        for name, model in models.items():
            try:
                # Make predictions
                y_pred = model.predict(X_test)
                
                # Calculate metrics
                mse = mean_squared_error(y_test, y_pred)
                rmse = np.sqrt(mse)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
                
                # Calculate percentage errors
                mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
                
                results.append({
                    'Model': name,
                    'MSE': mse,
                    'RMSE': rmse,
                    'MAE': mae,
                    'R2': r2,
                    'MAPE': mape,
                    'Model_Type': type(model).__name__
                })
                
            except Exception as e:
                results.append({
                    'Model': name,
                    'Error': str(e),
                    'Model_Type': type(model).__name__
                })
        
        return pd.DataFrame(results)
    
    def plot_model_comparison(self, comparison_df: pd.DataFrame, save_path: str = None) -> None:
        """Plot model comparison results."""
        if 'Error' in comparison_df.columns:
            comparison_df = comparison_df[comparison_df['Error'].isna()]
        
        if comparison_df.empty:
            print("No valid models to compare")
            return
        
        metrics = ['MSE', 'RMSE', 'MAE', 'R2', 'MAPE']
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()
        
        for i, metric in enumerate(metrics):
            if metric in comparison_df.columns:
                ax = axes[i]
                comparison_df.plot(x='Model', y=metric, kind='bar', ax=ax)
                ax.set_title(f'{metric} Comparison')
                ax.set_ylabel(metric)
                ax.tick_params(axis='x', rotation=45)
        
        # Remove empty subplot
        if len(metrics) < len(axes):
            axes[-1].remove()
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def plot_feature_importance(self, 
                               model: Any, 
                               feature_names: List[str], 
                               top_n: int = 20,
                               save_path: str = None) -> None:
        """Plot feature importance."""
        if not hasattr(model, 'feature_importances_') and not hasattr(model, 'feature_importance'):
            print("Model does not have feature importance")
            return
        
        if hasattr(model, 'feature_importance'):
            importance_dict = model.feature_importance()
            importance_df = pd.DataFrame([
                {'feature': k, 'importance': v} 
                for k, v in importance_dict.items()
            ])
        else:
            importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': model.feature_importances_
            })
        
        # Sort and get top features
        importance_df = importance_df.sort_values('importance', ascending=False)
        top_features = importance_df.head(top_n)
        
        # Plot
        plt.figure(figsize=(10, 8))
        sns.barplot(data=top_features, x='importance', y='feature')
        plt.title(f'Top {top_n} Feature Importance')
        plt.xlabel('Importance')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def plot_prediction_vs_actual(self, 
                                  y_true: np.ndarray, 
                                  y_pred: np.ndarray,
                                  model_name: str = "Model",
                                  save_path: str = None) -> None:
        """Plot predictions vs actual values."""
        plt.figure(figsize=(10, 8))
        
        # Scatter plot
        plt.scatter(y_true, y_pred, alpha=0.6, s=20)
        
        # Perfect prediction line
        min_val = min(y_true.min(), y_pred.min())
        max_val = max(y_true.max(), y_pred.max())
        plt.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='Perfect Prediction')
        
        # Calculate R2
        from sklearn.metrics import r2_score
        r2 = r2_score(y_true, y_pred)
        
        plt.xlabel('Actual Values')
        plt.ylabel('Predicted Values')
        plt.title(f'{model_name} - Predictions vs Actual (R² = {r2:.3f})')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def plot_residuals(self, 
                       y_true: np.ndarray, 
                       y_pred: np.ndarray,
                       model_name: str = "Model",
                       save_path: str = None) -> None:
        """Plot residual analysis."""
        residuals = y_true - y_pred
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Residuals vs Predicted
        axes[0, 0].scatter(y_pred, residuals, alpha=0.6)
        axes[0, 0].axhline(y=0, color='r', linestyle='--')
        axes[0, 0].set_xlabel('Predicted Values')
        axes[0, 0].set_ylabel('Residuals')
        axes[0, 0].set_title(f'{model_name} - Residuals vs Predicted')
        axes[0, 0].grid(True, alpha=0.3)
        
        # Histogram of residuals
        axes[0, 1].hist(residuals, bins=30, alpha=0.7, edgecolor='black')
        axes[0, 1].set_xlabel('Residuals')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title(f'{model_name} - Residuals Distribution')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Q-Q plot
        from scipy import stats
        stats.probplot(residuals, dist="norm", plot=axes[1, 0])
        axes[1, 0].set_title(f'{model_name} - Q-Q Plot')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Residuals vs Actual
        axes[1, 1].scatter(y_true, residuals, alpha=0.6)
        axes[1, 1].axhline(y=0, color='r', linestyle='--')
        axes[1, 1].set_xlabel('Actual Values')
        axes[1, 1].set_ylabel('Residuals')
        axes[1, 1].set_title(f'{model_name} - Residuals vs Actual')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def generate_model_report(self, 
                             model: Any, 
                             X_test: pd.DataFrame, 
                             y_test: pd.Series,
                             model_name: str = "Model",
                             feature_names: List[str] = None) -> Dict[str, Any]:
        """Generate comprehensive model report."""
        from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
        
        # Make predictions
        y_pred = model.predict(X_test)
        
        # Calculate metrics
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
        
        # Basic model info
        model_info = {
            'model_name': model_name,
            'model_type': type(model).__name__,
            'test_samples': len(X_test),
            'features': X_test.shape[1]
        }
        
        # Performance metrics
        performance = {
            'mse': mse,
            'rmse': rmse,
            'mae': mae,
            'r2': r2,
            'mape': mape
        }
        
        # Feature importance (if available)
        feature_importance = {}
        if hasattr(model, 'feature_importances_') and feature_names:
            feature_importance = dict(zip(feature_names, model.feature_importances_))
        elif hasattr(model, 'feature_importance'):
            feature_importance = model.feature_importance()
        
        # Prediction statistics
        predictions_stats = {
            'mean_predicted': np.mean(y_pred),
            'std_predicted': np.std(y_pred),
            'min_predicted': np.min(y_pred),
            'max_predicted': np.max(y_pred),
            'mean_actual': np.mean(y_test),
            'std_actual': np.std(y_test),
            'min_actual': np.min(y_test),
            'max_actual': np.max(y_test)
        }
        
        report = {
            'model_info': model_info,
            'performance': performance,
            'feature_importance': feature_importance,
            'predictions_statistics': predictions_stats,
            'generated_at': datetime.now().isoformat()
        }
        
        return report
    
    def save_model_report(self, report: Dict[str, Any], model_name: str) -> str:
        """Save model report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.output_dir, f"{model_name}_report_{timestamp}.json")
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report_path
    
    def create_model_pipeline(self, 
                             preprocessing_steps: List[Any], 
                             model: Any) -> Any:
        """Create a scikit-learn pipeline."""
        from sklearn.pipeline import Pipeline
        
        pipeline_steps = []
        
        for i, step in enumerate(preprocessing_steps):
            step_name = f"step_{i}"
            if hasattr(step, '__class__'):
                step_name = f"{step.__class__.__name__.lower()}_{i}"
            
            pipeline_steps.append((step_name, step))
        
        pipeline_steps.append(('model', model))
        
        return Pipeline(pipeline_steps)
    
    def optimize_model_threshold(self, 
                                model: Any, 
                                X_val: pd.DataFrame, 
                                y_val: pd.Series,
                                metric: str = 'f1') -> Tuple[float, float]:
        """Optimize decision threshold for classification models."""
        from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
        
        # Get prediction probabilities
        if hasattr(model, 'predict_proba'):
            y_proba = model.predict_proba(X_val)[:, 1]
        else:
            y_proba = model.predict(X_val)
        
        thresholds = np.arange(0.1, 1.0, 0.05)
        best_threshold = 0.5
        best_score = 0
        
        for threshold in thresholds:
            y_pred = (y_proba >= threshold).astype(int)
            
            if metric == 'f1':
                score = f1_score(y_val, y_pred)
            elif metric == 'precision':
                score = precision_score(y_val, y_pred)
            elif metric == 'recall':
                score = recall_score(y_val, y_pred)
            elif metric == 'accuracy':
                score = accuracy_score(y_val, y_pred)
            
            if score > best_score:
                best_score = score
                best_threshold = threshold
        
        return best_threshold, best_score
    
    def calculate_model_complexity(self, model: Any) -> Dict[str, Any]:
        """Calculate model complexity metrics."""
        complexity = {}
        
        # Number of parameters
        if hasattr(model, 'coef_'):
            complexity['coefficients_count'] = len(model.coef_.flatten())
        
        if hasattr(model, 'intercept_'):
            complexity['has_intercept'] = True
        
        # Tree-based models
        if hasattr(model, 'n_estimators'):
            complexity['n_estimators'] = model.n_estimators
        
        if hasattr(model, 'max_depth'):
            complexity['max_depth'] = model.max_depth
        
        # Neural networks
        if hasattr(model, 'model') and hasattr(model.model, 'count_params'):
            complexity['total_parameters'] = model.model.count_params()
        
        # Model size
        try:
            model_bytes = len(joblib.dumps(model))
            complexity['model_size_mb'] = model_bytes / (1024 * 1024)
        except:
            complexity['model_size_mb'] = 'unknown'
        
        return complexity
    
    def validate_model_assumptions(self, 
                                  X: pd.DataFrame, 
                                  y: pd.Series,
                                  model: Any) -> Dict[str, Any]:
        """Validate model assumptions."""
        assumptions = {}
        
        # Linear regression assumptions
        if 'LinearRegression' in str(type(model)):
            # Linearity
            y_pred = model.predict(X)
            residuals = y - y_pred
            
            # Homoscedasticity test (simplified)
            assumptions['homoscedasticity'] = {
                'test': 'Breusch-Pagan (simplified)',
                'result': 'Not implemented - requires statsmodels'
            }
            
            # Normality of residuals
            from scipy import stats
            _, p_value = stats.normaltest(residuals)
            assumptions['normality_residuals'] = {
                'test': 'D\'Agostino-Pearson',
                'p_value': p_value,
                'is_normal': p_value > 0.05
            }
        
        # General assumptions
        assumptions['sample_size'] = len(X)
        assumptions['feature_count'] = X.shape[1]
        assumptions['features_per_sample_ratio'] = X.shape[1] / len(X)
        
        return assumptions
