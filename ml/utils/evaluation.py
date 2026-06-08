"""
Model evaluation utilities for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
from sklearn.metrics import (
    mean_squared_error, r2_score, mean_absolute_error, 
    mean_absolute_percentage_error, explained_variance_score,
    confusion_matrix, classification_report, precision_score, recall_score, f1_score
)
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


class ModelEvaluator:
    """Model evaluation utilities for ML models."""
    
    def __init__(self, output_dir: str = "evaluation_results"):
        """Initialize model evaluator."""
        self.output_dir = output_dir
        self.evaluation_results = {}
        
    def evaluate_regression_model(self, 
                                y_true: np.ndarray, 
                                y_pred: np.ndarray,
                                model_name: str = "Model") -> Dict[str, Any]:
        """Evaluate regression model performance."""
        
        # Basic metrics
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        mape = mean_absolute_percentage_error(y_true, y_pred)
        evs = explained_variance_score(y_true, y_pred)
        
        # Additional metrics
        residuals = y_true - y_pred
        mean_residual = np.mean(residuals)
        std_residual = np.std(residuals)
        
        # Percentage of predictions within certain ranges
        within_5_percent = np.mean(np.abs((y_true - y_pred) / y_true) <= 0.05) * 100
        within_10_percent = np.mean(np.abs((y_true - y_pred) / y_true) <= 0.10) * 100
        within_20_percent = np.mean(np.abs((y_true - y_pred) / y_true) <= 0.20) * 100
        
        # Statistical tests
        # Normality test for residuals
        _, normality_p_value = stats.normaltest(residuals)
        
        # Correlation between predicted and actual
        correlation = np.corrcoef(y_true, y_pred)[0, 1]
        
        evaluation = {
            'model_name': model_name,
            'metrics': {
                'mse': mse,
                'rmse': rmse,
                'mae': mae,
                'r2': r2,
                'mape': mape,
                'explained_variance': evs
            },
            'accuracy_metrics': {
                'within_5_percent': within_5_percent,
                'within_10_percent': within_10_percent,
                'within_20_percent': within_20_percent
            },
            'residual_analysis': {
                'mean_residual': mean_residual,
                'std_residual': std_residual,
                'normality_p_value': normality_p_value,
                'is_normal_residuals': normality_p_value > 0.05
            },
            'correlation': correlation,
            'sample_size': len(y_true)
        }
        
        self.evaluation_results[model_name] = evaluation
        
        return evaluation
    
    def evaluate_classification_model(self, 
                                   y_true: np.ndarray, 
                                   y_pred: np.ndarray,
                                   y_proba: np.ndarray = None,
                                   model_name: str = "Model") -> Dict[str, Any]:
        """Evaluate classification model performance."""
        
        # Basic metrics
        precision = precision_score(y_true, y_pred, average='weighted')
        recall = recall_score(y_true, y_pred, average='weighted')
        f1 = f1_score(y_true, y_pred, average='weighted')
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        
        # Classification report
        report = classification_report(y_true, y_pred, output_dict=True)
        
        evaluation = {
            'model_name': model_name,
            'metrics': {
                'precision': precision,
                'recall': recall,
                'f1_score': f1
            },
            'confusion_matrix': cm.tolist(),
            'classification_report': report,
            'sample_size': len(y_true)
        }
        
        # Add probability-based metrics if available
        if y_proba is not None:
            from sklearn.metrics import roc_auc_score, average_precision_score
            
            try:
                auc_roc = roc_auc_score(y_true, y_proba[:, 1])
                evaluation['metrics']['auc_roc'] = auc_roc
            except:
                pass
            
            try:
                auc_pr = average_precision_score(y_true, y_proba[:, 1])
                evaluation['metrics']['auc_pr'] = auc_pr
            except:
                pass
        
        self.evaluation_results[model_name] = evaluation
        
        return evaluation
    
    def compare_models(self, model_results: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
        """Compare multiple models performance."""
        
        comparison_data = []
        
        for model_name, results in model_results.items():
            if 'metrics' in results:
                row = {'Model': model_name}
                row.update(results['metrics'])
                comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        # Sort by R2 score for regression models
        if 'r2' in comparison_df.columns:
            comparison_df = comparison_df.sort_values('r2', ascending=False)
        elif 'f1_score' in comparison_df.columns:
            comparison_df = comparison_df.sort_values('f1_score', ascending=False)
        
        return comparison_df
    
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
    
    def plot_model_comparison(self, comparison_df: pd.DataFrame, save_path: str = None) -> None:
        """Plot model comparison results."""
        
        if comparison_df.empty:
            print("No models to compare")
            return
        
        # Determine metrics to plot
        metrics = [col for col in comparison_df.columns if col != 'Model']
        
        # Create subplots
        n_metrics = len(metrics)
        n_cols = min(3, n_metrics)
        n_rows = (n_metrics + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 5*n_rows))
        if n_rows == 1:
            axes = axes.reshape(1, -1)
        
        for i, metric in enumerate(metrics):
            row, col = i // n_cols, i % n_cols
            ax = axes[row, col] if n_rows > 1 else axes[col]
            
            # Create bar plot
            comparison_df.plot(x='Model', y=metric, kind='bar', ax=ax)
            ax.set_title(f'{metric.upper()} Comparison')
            ax.set_ylabel(metric)
            ax.tick_params(axis='x', rotation=45)
        
        # Remove empty subplots
        for i in range(n_metrics, n_rows * n_cols):
            row, col = i // n_cols, i % n_cols
            ax = axes[row, col] if n_rows > 1 else axes[col]
            ax.remove()
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def plot_confusion_matrix(self, 
                             y_true: np.ndarray, 
                             y_pred: np.ndarray,
                             model_name: str = "Model",
                             save_path: str = None) -> None:
        """Plot confusion matrix."""
        
        cm = confusion_matrix(y_true, y_pred)
        
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                   xticklabels=['Predicted 0', 'Predicted 1'],
                   yticklabels=['Actual 0', 'Actual 1'])
        plt.title(f'{model_name} - Confusion Matrix')
        plt.ylabel('Actual')
        plt.xlabel('Predicted')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def cross_validate_model(self, 
                           model: Any, 
                           X: pd.DataFrame, 
                           y: pd.Series,
                           cv_folds: int = 5,
                           scoring: str = 'r2') -> Dict[str, Any]:
        """Perform cross-validation on a model."""
        
        from sklearn.model_selection import cross_val_score, KFold
        
        # Create cross-validation strategy
        cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
        
        # Perform cross-validation
        cv_scores = cross_val_score(model, X, y, cv=cv, scoring=scoring)
        
        cv_results = {
            'cv_scores': cv_scores.tolist(),
            'mean_score': cv_scores.mean(),
            'std_score': cv_scores.std(),
            'min_score': cv_scores.min(),
            'max_score': cv_scores.max(),
            'scoring_metric': scoring,
            'cv_folds': cv_folds
        }
        
        return cv_results
    
    def learning_curve_analysis(self, 
                              model: Any, 
                              X: pd.DataFrame, 
                              y: pd.Series,
                              cv_folds: int = 5) -> Dict[str, Any]:
        """Analyze learning curve."""
        
        from sklearn.model_selection import learning_curve
        
        train_sizes, train_scores, val_scores = learning_curve(
            model, X, y, cv=cv_folds, 
            train_sizes=np.linspace(0.1, 1.0, 10),
            scoring='r2'
        )
        
        learning_curve_data = {
            'train_sizes': train_sizes.tolist(),
            'train_scores_mean': train_scores.mean(axis=1).tolist(),
            'train_scores_std': train_scores.std(axis=1).tolist(),
            'val_scores_mean': val_scores.mean(axis=1).tolist(),
            'val_scores_std': val_scores.std(axis=1).tolist()
        }
        
        return learning_curve_data
    
    def plot_learning_curve(self, 
                           learning_curve_data: Dict[str, Any],
                           model_name: str = "Model",
                           save_path: str = None) -> None:
        """Plot learning curve."""
        
        train_sizes = learning_curve_data['train_sizes']
        train_mean = learning_curve_data['train_scores_mean']
        train_std = learning_curve_data['train_scores_std']
        val_mean = learning_curve_data['val_scores_mean']
        val_std = learning_curve_data['val_scores_std']
        
        plt.figure(figsize=(10, 6))
        
        # Plot training scores
        plt.plot(train_sizes, train_mean, 'o-', color='blue', label='Training Score')
        plt.fill_between(train_sizes, 
                        np.array(train_mean) - np.array(train_std),
                        np.array(train_mean) + np.array(train_std),
                        alpha=0.1, color='blue')
        
        # Plot validation scores
        plt.plot(train_sizes, val_mean, 'o-', color='red', label='Validation Score')
        plt.fill_between(train_sizes,
                        np.array(val_mean) - np.array(val_std),
                        np.array(val_mean) + np.array(val_std),
                        alpha=0.1, color='red')
        
        plt.xlabel('Training Set Size')
        plt.ylabel('R² Score')
        plt.title(f'{model_name} - Learning Curve')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def feature_importance_analysis(self, 
                                  model: Any, 
                                  feature_names: List[str],
                                  model_name: str = "Model") -> Dict[str, Any]:
        """Analyze feature importance."""
        
        importance_data = {}
        
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            importance_data['feature_importances'] = dict(zip(feature_names, importances))
            
            # Create importance ranking
            importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': importances
            }).sort_values('importance', ascending=False)
            
            importance_data['ranking'] = importance_df.to_dict('records')
            
        elif hasattr(model, 'coef_'):
            coef = model.coef_
            if coef.ndim > 1:
                coef = coef[0]
            
            importance_data['coefficients'] = dict(zip(feature_names, coef))
            
            # Create coefficient ranking by absolute value
            importance_df = pd.DataFrame({
                'feature': feature_names,
                'coefficient': coef,
                'abs_coefficient': np.abs(coef)
            }).sort_values('abs_coefficient', ascending=False)
            
            importance_data['coefficient_ranking'] = importance_df.to_dict('records')
        
        return importance_data
    
    def generate_evaluation_report(self, 
                                 model_name: str,
                                 evaluation_results: Dict[str, Any]) -> str:
        """Generate comprehensive evaluation report."""
        
        report = f"""
# Model Evaluation Report: {model_name}

## Performance Metrics
"""
        
        if 'metrics' in evaluation_results:
            for metric, value in evaluation_results['metrics'].items():
                report += f"- {metric.upper()}: {value:.4f}\n"
        
        if 'accuracy_metrics' in evaluation_results:
            report += "\n## Accuracy Metrics\n"
            for metric, value in evaluation_results['accuracy_metrics'].items():
                report += f"- {metric.replace('_', ' ').title()}: {value:.2f}%\n"
        
        if 'residual_analysis' in evaluation_results:
            report += "\n## Residual Analysis\n"
            for metric, value in evaluation_results['residual_analysis'].items():
                if isinstance(value, float):
                    report += f"- {metric.replace('_', ' ').title()}: {value:.4f}\n"
                else:
                    report += f"- {metric.replace('_', ' ').title()}: {value}\n"
        
        if 'correlation' in evaluation_results:
            report += f"\n## Correlation\n- Correlation between predicted and actual: {evaluation_results['correlation']:.4f}\n"
        
        report += f"\n## Sample Information\n- Total samples: {evaluation_results.get('sample_size', 'N/A')}\n"
        
        return report
    
    def save_evaluation_results(self, model_name: str, results: Dict[str, Any]) -> str:
        """Save evaluation results to file."""
        
        import json
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_evaluation_{timestamp}.json"
        filepath = f"{self.output_dir}/{filename}"
        
        # Convert numpy arrays to lists for JSON serialization
        def convert_numpy(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            return obj
        
        # Recursively convert numpy objects
        def recursive_convert(data):
            if isinstance(data, dict):
                return {key: recursive_convert(value) for key, value in data.items()}
            elif isinstance(data, list):
                return [recursive_convert(item) for item in data]
            else:
                return convert_numpy(data)
        
        converted_results = recursive_convert(results)
        
        with open(filepath, 'w') as f:
            json.dump(converted_results, f, indent=2)
        
        return filepath
    
    def get_best_model(self, metric: str = 'r2') -> Tuple[str, float]:
        """Get the best model based on specified metric."""
        
        best_model = None
        best_score = float('-inf') if 'r2' in metric or 'f1' in metric else float('inf')
        
        for model_name, results in self.evaluation_results.items():
            if 'metrics' in results and metric in results['metrics']:
                score = results['metrics'][metric]
                
                if 'r2' in metric or 'f1' in metric:
                    if score > best_score:
                        best_score = score
                        best_model = model_name
                else:
                    if score < best_score:
                        best_score = score
                        best_model = model_name
        
        return best_model, best_score
