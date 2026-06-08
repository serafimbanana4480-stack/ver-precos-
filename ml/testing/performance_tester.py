"""
Performance testing for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import time
import psutil
import os
import gc
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')


class PerformanceTester:
    """Performance testing for ML models."""
    
    def __init__(self):
        """Initialize performance tester."""
        self.test_results = {}
        
    def test_prediction_speed(self, 
                             model: Any, 
                             X_test: pd.DataFrame,
                             sample_sizes: List[int] = [1, 10, 100, 1000]) -> Dict[str, Any]:
        """Test prediction speed across different sample sizes."""
        
        speed_results = {
            'sample_sizes': [],
            'prediction_times': [],
            'samples_per_second': [],
            'memory_usage_mb': []
        }
        
        for size in sample_sizes:
            if size > len(X_test):
                continue
                
            # Take sample
            sample_X = X_test.head(size)
            
            # Measure memory before prediction
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Measure prediction time
            start_time = time.time()
            predictions = model.predict(sample_X)
            end_time = time.time()
            
            prediction_time = end_time - start_time
            samples_per_second = size / prediction_time if prediction_time > 0 else float('inf')
            
            # Measure memory after prediction
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_usage = memory_after - memory_before
            
            speed_results['sample_sizes'].append(size)
            speed_results['prediction_times'].append(prediction_time)
            speed_results['samples_per_second'].append(samples_per_second)
            speed_results['memory_usage_mb'].append(memory_usage)
        
        # Calculate performance metrics
        speed_results['avg_samples_per_second'] = np.mean(speed_results['samples_per_second'])
        speed_results['max_samples_per_second'] = np.max(speed_results['samples_per_second'])
        speed_results['avg_memory_per_sample_mb'] = np.mean([m/s for m, s in zip(speed_results['memory_usage_mb'], speed_results['sample_sizes']) if s > 0])
        
        return speed_results
    
    def test_memory_usage(self, 
                        model: Any, 
                        X_test: pd.DataFrame,
                        iterations: int = 10) -> Dict[str, Any]:
        """Test memory usage during predictions."""
        
        memory_results = {
            'baseline_memory_mb': 0,
            'peak_memory_mb': 0,
            'memory_growth_mb': 0,
            'memory_leak_detected': False
        }
        
        # Get baseline memory
        process = psutil.Process(os.getpid())
        baseline_memory = process.memory_info().rss / 1024 / 1024
        memory_results['baseline_memory_mb'] = baseline_memory
        
        peak_memory = baseline_memory
        
        # Run multiple predictions
        for i in range(iterations):
            predictions = model.predict(X_test)
            
            # Check memory after each prediction
            current_memory = process.memory_info().rss / 1024 / 1024
            peak_memory = max(peak_memory, current_memory)
            
            # Force garbage collection
            gc.collect()
        
        memory_results['peak_memory_mb'] = peak_memory
        memory_results['memory_growth_mb'] = peak_memory - baseline_memory
        
        # Check for potential memory leak (significant growth)
        memory_results['memory_leak_detected'] = memory_results['memory_growth_mb'] > 100  # 100MB threshold
        
        return memory_results
    
    def test_concurrent_predictions(self, 
                                  model: Any, 
                                  X_test: pd.DataFrame,
                                  n_workers: List[int] = [1, 2, 4, 8],
                                  batch_size: int = 100) -> Dict[str, Any]:
        """Test concurrent prediction performance."""
        
        concurrent_results = {
            'workers': [],
            'total_times': [],
            'samples_per_second': []
        }
        
        def predict_batch(batch_data):
            return model.predict(batch_data)
        
        for n_workers in n_workers:
            if n_workers > len(X_test):
                continue
            
            # Split data into batches
            batches = [X_test.iloc[i:i+batch_size] for i in range(0, len(X_test), batch_size)]
            if len(batches) > n_workers:
                batches = batches[:n_workers]
            
            # Measure concurrent prediction time
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = [executor.submit(predict_batch, batch) for batch in batches]
                results = [future.result() for future in futures]
            
            end_time = time.time()
            total_time = end_time - start_time
            total_samples = sum(len(batch) for batch in batches)
            samples_per_second = total_samples / total_time if total_time > 0 else float('inf')
            
            concurrent_results['workers'].append(n_workers)
            concurrent_results['total_times'].append(total_time)
            concurrent_results['samples_per_second'].append(samples_per_second)
        
        return concurrent_results
    
    def test_model_loading_time(self, 
                               model_class: Any, 
                               X_train: pd.DataFrame, 
                               y_train: pd.Series,
                               iterations: int = 5) -> Dict[str, Any]:
        """Test model loading/training time."""
        
        loading_results = {
            'training_times': [],
            'avg_training_time': 0,
            'std_training_time': 0
        }
        
        for i in range(iterations):
            # Create new model instance
            model = model_class()
            
            # Measure training time
            start_time = time.time()
            model.train(X_train, y_train)
            end_time = time.time()
            
            training_time = end_time - start_time
            loading_results['training_times'].append(training_time)
        
        loading_results['avg_training_time'] = np.mean(loading_results['training_times'])
        loading_results['std_training_time'] = np.std(loading_results['training_times'])
        
        return loading_results
    
    def test_scalability(self, 
                         model_class: Any, 
                         base_data: pd.DataFrame,
                         base_target: pd.Series,
                         scale_factors: List[float] = [0.5, 1.0, 2.0, 4.0]) -> Dict[str, Any]:
        """Test model scalability with different data sizes."""
        
        scalability_results = {
            'scale_factors': [],
            'sample_counts': [],
            'training_times': [],
            'prediction_times': [],
            'memory_usage_mb': []
        }
        
        for factor in scale_factors:
            # Scale the data
            scaled_size = int(len(base_data) * factor)
            if scaled_size > len(base_data):
                # Sample with replacement if needed
                indices = np.random.choice(len(base_data), scaled_size, replace=True)
                scaled_X = base_data.iloc[indices].reset_index(drop=True)
                scaled_y = base_target.iloc[indices].reset_index(drop=True)
            else:
                # Sample without replacement
                scaled_X = base_data.head(scaled_size)
                scaled_y = base_target.head(scaled_size)
            
            # Measure memory before
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024
            
            # Test training time
            model = model_class()
            start_time = time.time()
            model.train(scaled_X, scaled_y)
            training_time = time.time() - start_time
            
            # Test prediction time
            test_X = scaled_X.head(min(100, len(scaled_X)))
            start_time = time.time()
            predictions = model.predict(test_X)
            prediction_time = time.time() - start_time
            
            # Measure memory after
            memory_after = process.memory_info().rss / 1024 / 1024
            memory_usage = memory_after - memory_before
            
            scalability_results['scale_factors'].append(factor)
            scalability_results['sample_counts'].append(len(scaled_X))
            scalability_results['training_times'].append(training_time)
            scalability_results['prediction_times'].append(prediction_time)
            scalability_results['memory_usage_mb'].append(memory_usage)
        
        # Calculate scalability metrics
        scalability_results['training_time_complexity'] = self._calculate_complexity(
            scalability_results['sample_counts'], 
            scalability_results['training_times']
        )
        scalability_results['prediction_time_complexity'] = self._calculate_complexity(
            scalability_results['sample_counts'], 
            scalability_results['prediction_times']
        )
        
        return scalability_results
    
    def _calculate_complexity(self, sizes: List[int], times: List[float]) -> str:
        """Estimate time complexity from size-time data."""
        if len(sizes) < 2:
            return "insufficient_data"
        
        # Simple linear regression on log-log scale to estimate exponent
        log_sizes = np.log(sizes)
        log_times = np.log(times)
        
        # Calculate slope (complexity exponent)
        slope = np.polyfit(log_sizes, log_times, 1)[0]
        
        if slope < 1.5:
            return "O(n)"
        elif slope < 2.5:
            return "O(n^2)"
        else:
            return "O(n^k) where k > 2"
    
    def generate_performance_report(self, model_name: str, test_results: Dict[str, Any]) -> str:
        """Generate comprehensive performance report."""
        
        report = f"""
# Performance Test Report: {model_name}

## Test Results Summary
"""
        
        if 'prediction_speed' in test_results:
            speed = test_results['prediction_speed']
            report += f"""
### Prediction Speed
- Average samples per second: {speed.get('avg_samples_per_second', 0):.2f}
- Maximum samples per second: {speed.get('max_samples_per_second', 0):.2f}
- Average memory per sample: {speed.get('avg_memory_per_sample_mb', 0):.4f} MB
"""
        
        if 'memory_usage' in test_results:
            memory = test_results['memory_usage']
            report += f"""
### Memory Usage
- Baseline memory: {memory.get('baseline_memory_mb', 0):.2f} MB
- Peak memory: {memory.get('peak_memory_mb', 0):.2f} MB
- Memory growth: {memory.get('memory_growth_mb', 0):.2f} MB
- Memory leak detected: {memory.get('memory_leak_detected', False)}
"""
        
        if 'concurrent_predictions' in test_results:
            concurrent = test_results['concurrent_predictions']
            report += f"""
### Concurrent Performance
- Best performance with {concurrent['workers'][np.argmax(concurrent['samples_per_second'])]} workers
- Maximum samples per second: {max(concurrent['samples_per_second']):.2f}
"""
        
        if 'scalability' in test_results:
            scalability = test_results['scalability']
            report += f"""
### Scalability
- Training time complexity: {scalability.get('training_time_complexity', 'Unknown')}
- Prediction time complexity: {scalability.get('prediction_time_complexity', 'Unknown')}
"""
        
        return report
    
    def run_comprehensive_performance_test(self, 
                                         model: Any, 
                                         model_class: Any,
                                         X_train: pd.DataFrame, 
                                         y_train: pd.Series,
                                         X_test: pd.DataFrame) -> Dict[str, Any]:
        """Run comprehensive performance test suite."""
        
        all_results = {}
        
        print("Running prediction speed test...")
        all_results['prediction_speed'] = self.test_prediction_speed(model, X_test)
        
        print("Running memory usage test...")
        all_results['memory_usage'] = self.test_memory_usage(model, X_test)
        
        print("Running concurrent predictions test...")
        all_results['concurrent_predictions'] = self.test_concurrent_predictions(model, X_test)
        
        print("Running model loading test...")
        all_results['model_loading'] = self.test_model_loading_time(model_class, X_train, y_train)
        
        print("Running scalability test...")
        all_results['scalability'] = self.test_scalability(model_class, X_train, y_train)
        
        return all_results
