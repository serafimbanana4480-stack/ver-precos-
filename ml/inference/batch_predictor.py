"""
Batch predictor for large-scale ML inference.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Iterator
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import time
from datetime import datetime
import json
import os

from .predictor import Predictor


class BatchPredictor:
    """Batch predictor for large-scale ML inference."""
    
    def __init__(self, model_dir: str = "models", batch_size: int = 1000, n_workers: int = None):
        """Initialize batch predictor."""
        self.predictor = Predictor(model_dir)
        self.batch_size = batch_size
        self.n_workers = n_workers or mp.cpu_count()
        
    def predict_large_dataset(self, 
                           input_path: str, 
                           output_path: str,
                           model_name: str = None,
                           chunk_size: int = 10000) -> Dict[str, Any]:
        """Predict on large dataset using chunked processing."""
        start_time = time.time()
        
        # Read input data in chunks
        chunks = pd.read_csv(input_path, chunksize=chunk_size)
        
        all_predictions = []
        total_rows = 0
        
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1} with {len(chunk)} rows...")
            
            # Make predictions on chunk
            predictions_df = self.predictor.predict_from_dataframe(chunk, model_name)
            
            # Append to results
            all_predictions.append(predictions_df)
            total_rows += len(chunk)
            
            # Save intermediate results
            if i % 10 == 0:
                intermediate_df = pd.concat(all_predictions, ignore_index=True)
                intermediate_df.to_csv(f"{output_path}.intermediate_{i}.csv", index=False)
                print(f"Saved intermediate results: {len(intermediate_df)} rows")
        
        # Combine all predictions
        final_df = pd.concat(all_predictions, ignore_index=True)
        
        # Save final results
        final_df.to_csv(output_path, index=False)
        
        # Clean up intermediate files
        for i in range(0, len(all_predictions), 10):
            intermediate_file = f"{output_path}.intermediate_{i}.csv"
            if os.path.exists(intermediate_file):
                os.remove(intermediate_file)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        results = {
            'total_rows_processed': total_rows,
            'processing_time_seconds': processing_time,
            'rows_per_second': total_rows / processing_time if processing_time > 0 else 0,
            'output_file': output_path,
            'model_used': model_name or self.predictor.default_model
        }
        
        return results
    
    def predict_parallel(self, 
                        features_list: List[Dict[str, Any]], 
                        model_name: str = None,
                        use_processes: bool = True) -> List[Dict[str, Any]]:
        """Make predictions using parallel processing."""
        if len(features_list) <= self.batch_size:
            # Use single-threaded prediction for small datasets
            return self.predictor.predict_batch(features_list, model_name)
        
        # Split data into batches
        batches = [
            features_list[i:i + self.batch_size] 
            for i in range(0, len(features_list), self.batch_size)
        ]
        
        # Process batches in parallel
        executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        
        with executor_class(max_workers=self.n_workers) as executor:
            # Submit all batches for processing
            futures = [
                executor.submit(self._process_batch, batch, model_name)
                for batch in batches
            ]
            
            # Collect results
            all_results = []
            for future in futures:
                batch_results = future.result()
                all_results.extend(batch_results)
        
        return all_results
    
    def _process_batch(self, batch: List[Dict[str, Any]], model_name: str) -> List[Dict[str, Any]]:
        """Process a single batch of predictions."""
        return self.predictor.predict_batch(batch, model_name)
    
    def predict_streaming(self, 
                         data_iterator: Iterator[Dict[str, Any]], 
                         output_path: str,
                         model_name: str = None,
                         save_interval: int = 1000) -> Dict[str, Any]:
        """Predict on streaming data."""
        start_time = time.time()
        
        batch_results = []
        total_processed = 0
        batch_count = 0
        
        # Create output file with headers
        first_batch = True
        
        for features in data_iterator:
            batch_results.append(features)
            total_processed += 1
            
            # Process batch when it reaches batch_size
            if len(batch_results) >= self.batch_size:
                predictions = self.predictor.predict_batch(batch_results, model_name)
                
                # Save predictions to file
                self._save_predictions_to_file(predictions, output_path, first_batch)
                first_batch = False
                
                batch_results = []
                batch_count += 1
                
                if batch_count % save_interval == 0:
                    print(f"Processed {total_processed} records...")
        
        # Process remaining records
        if batch_results:
            predictions = self.predictor.predict_batch(batch_results, model_name)
            self._save_predictions_to_file(predictions, output_path, first_batch)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        results = {
            'total_records_processed': total_processed,
            'processing_time_seconds': processing_time,
            'records_per_second': total_processed / processing_time if processing_time > 0 else 0,
            'output_file': output_path,
            'model_used': model_name or self.predictor.default_model
        }
        
        return results
    
    def _save_predictions_to_file(self, 
                                  predictions: List[Dict[str, Any]], 
                                  output_path: str, 
                                  write_header: bool) -> None:
        """Save predictions to CSV file."""
        df = pd.DataFrame(predictions)
        
        if write_header or not os.path.exists(output_path):
            df.to_csv(output_path, mode='w', index=False, header=True)
        else:
            df.to_csv(output_path, mode='a', index=False, header=False)
    
    def predict_with_confidence_filtering(self, 
                                        features_list: List[Dict[str, Any]], 
                                        model_name: str = None,
                                        min_confidence: float = 0.7) -> Dict[str, Any]:
        """Make predictions with confidence filtering."""
        predictions = self.predictor.predict_batch(features_list, model_name)
        
        # Filter by confidence
        high_confidence_predictions = [
            pred for pred in predictions 
            if pred['confidence'] >= min_confidence
        ]
        
        low_confidence_predictions = [
            pred for pred in predictions 
            if pred['confidence'] < min_confidence
        ]
        
        results = {
            'total_predictions': len(predictions),
            'high_confidence_count': len(high_confidence_predictions),
            'low_confidence_count': len(low_confidence_predictions),
            'high_confidence_predictions': high_confidence_predictions,
            'low_confidence_predictions': low_confidence_predictions,
            'min_confidence_threshold': min_confidence,
            'model_used': model_name or self.predictor.default_model
        }
        
        return results
    
    def predict_with_price_ranges(self, 
                                 features_list: List[Dict[str, Any]], 
                                 model_name: str = None,
                                 price_tolerance: float = 0.1) -> Dict[str, Any]:
        """Make predictions with price range estimates."""
        predictions = self.predictor.predict_batch(features_list, model_name)
        
        # Calculate price ranges based on confidence
        for pred in predictions:
            predicted_price = pred['predicted_price']
            confidence = pred['confidence']
            
            # Adjust tolerance based on confidence
            adjusted_tolerance = price_tolerance * (2.0 - confidence)
            
            lower_bound = predicted_price * (1.0 - adjusted_tolerance)
            upper_bound = predicted_price * (1.0 + adjusted_tolerance)
            
            pred['price_range'] = {
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'tolerance_percent': adjusted_tolerance * 100
            }
        
        results = {
            'predictions_with_ranges': predictions,
            'model_used': model_name or self.predictor.default_model,
            'price_tolerance': price_tolerance
        }
        
        return results
    
    def benchmark_prediction_performance(self, 
                                       sample_sizes: List[int] = [100, 1000, 10000, 100000],
                                       model_name: str = None) -> Dict[str, Any]:
        """Benchmark prediction performance across different sample sizes."""
        # Generate sample data
        sample_data = self._generate_sample_data(max(sample_sizes))
        
        benchmark_results = {}
        
        for size in sample_sizes:
            print(f"Benchmarking with {size} samples...")
            
            # Take subset of data
            subset = sample_data[:size]
            
            # Measure prediction time
            start_time = time.time()
            predictions = self.predictor.predict_batch(subset, model_name)
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            benchmark_results[size] = {
                'processing_time_seconds': processing_time,
                'samples_per_second': size / processing_time if processing_time > 0 else 0,
                'average_confidence': np.mean([pred['confidence'] for pred in predictions]),
                'prediction_count': len(predictions)
            }
        
        return benchmark_results
    
    def _generate_sample_data(self, n_samples: int) -> List[Dict[str, Any]]:
        """Generate sample data for benchmarking."""
        sample_data = []
        
        for i in range(n_samples):
            features = {
                'make': 'Toyota',
                'model': 'Corolla',
                'year': 2020,
                'mileage': np.random.randint(1000, 100000),
                'engine_size': np.random.uniform(1.0, 3.0),
                'fuel_type': 'Gasoline',
                'transmission': 'Automatic',
                'condition': np.random.choice(['Excellent', 'Good', 'Fair']),
                'location': 'Lisbon'
            }
            sample_data.append(features)
        
        return sample_data
    
    def predict_with_model_ensemble(self, 
                                   features_list: List[Dict[str, Any]], 
                                   model_names: List[str],
                                   voting_strategy: str = 'weighted_average') -> List[Dict[str, Any]]:
        """Make predictions using multiple models (ensemble)."""
        if len(model_names) < 2:
            raise ValueError("At least 2 models required for ensemble prediction")
        
        ensemble_predictions = []
        
        for features in features_list:
            model_predictions = []
            model_confidences = []
            
            # Get predictions from each model
            for model_name in model_names:
                try:
                    pred = self.predictor.predict_single(features, model_name)
                    model_predictions.append(pred['predicted_price'])
                    model_confidences.append(pred['confidence'])
                except Exception as e:
                    print(f"Error with model {model_name}: {e}")
                    continue
            
            if not model_predictions:
                continue
            
            # Combine predictions using voting strategy
            if voting_strategy == 'average':
                ensemble_price = np.mean(model_predictions)
                ensemble_confidence = np.mean(model_confidences)
            elif voting_strategy == 'weighted_average':
                weights = np.array(model_confidences)
                weights = weights / np.sum(weights)  # Normalize weights
                ensemble_price = np.average(model_predictions, weights=weights)
                ensemble_confidence = np.mean(model_confidences)
            elif voting_strategy == 'median':
                ensemble_price = np.median(model_predictions)
                ensemble_confidence = np.median(model_confidences)
            else:
                raise ValueError(f"Unknown voting strategy: {voting_strategy}")
            
            ensemble_predictions.append({
                'predicted_price': ensemble_price,
                'confidence': ensemble_confidence,
                'individual_predictions': model_predictions,
                'individual_confidences': model_confidences,
                'voting_strategy': voting_strategy
            })
        
        return ensemble_predictions
    
    def predict_with_uncertainty_estimation(self, 
                                          features_list: List[Dict[str, Any]], 
                                          model_name: str = None,
                                          n_bootstrap: int = 100) -> List[Dict[str, Any]]:
        """Make predictions with uncertainty estimation using bootstrap."""
        predictions_with_uncertainty = []
        
        for features in features_list:
            bootstrap_predictions = []
            
            # Generate bootstrap predictions
            for _ in range(n_bootstrap):
                # Add noise to features for bootstrap
                noisy_features = self._add_noise_to_features(features)
                pred = self.predictor.predict_single(noisy_features, model_name)
                bootstrap_predictions.append(pred['predicted_price'])
            
            # Calculate statistics
            mean_prediction = np.mean(bootstrap_predictions)
            std_prediction = np.std(bootstrap_predictions)
            confidence_interval = np.percentile(bootstrap_predictions, [2.5, 97.5])
            
            # Get original prediction
            original_pred = self.predictor.predict_single(features, model_name)
            
            predictions_with_uncertainty.append({
                'predicted_price': original_pred['predicted_price'],
                'confidence': original_pred['confidence'],
                'uncertainty_std': std_prediction,
                'uncertainty_mean': mean_prediction,
                'confidence_interval_95': {
                    'lower': confidence_interval[0],
                    'upper': confidence_interval[1]
                },
                'bootstrap_samples': n_bootstrap,
                'coefficient_of_variation': std_prediction / mean_prediction if mean_prediction > 0 else 0
            })
        
        return predictions_with_uncertainty
    
    def _add_noise_to_features(self, features: Dict[str, Any], noise_level: float = 0.05) -> Dict[str, Any]:
        """Add controlled noise to features for bootstrap."""
        noisy_features = features.copy()
        
        # Add noise to numerical features
        numerical_features = ['year', 'mileage', 'engine_size']
        for feature in numerical_features:
            if feature in noisy_features and isinstance(noisy_features[feature], (int, float)):
                noise = np.random.normal(0, noise_level * noisy_features[feature])
                noisy_features[feature] = max(0, noisy_features[feature] + noise)
        
        return noisy_features
    
    def predict_with_feature_importance(self, 
                                      features_list: List[Dict[str, Any]], 
                                      model_name: str = None) -> List[Dict[str, Any]]:
        """Make predictions with feature importance analysis."""
        predictions_with_importance = []
        
        for features in features_list:
            # Get original prediction
            original_pred = self.predictor.predict_single(features, model_name)
            
            # Calculate feature importance by permutation
            feature_importance = {}
            base_price = original_pred['predicted_price']
            
            for feature_name, feature_value in features.items():
                if isinstance(feature_value, (int, float)):
                    # Permute the feature value
                    perturbed_features = features.copy()
                    
                    # Add small perturbation
                    perturbation = feature_value * 0.1
                    perturbed_features[feature_name] = feature_value + perturbation
                    
                    # Get perturbed prediction
                    perturbed_pred = self.predictor.predict_single(perturbed_features, model_name)
                    
                    # Calculate importance as price change
                    price_change = abs(perturbed_pred['predicted_price'] - base_price)
                    importance_score = price_change / base_price if base_price > 0 else 0
                    
                    feature_importance[feature_name] = importance_score
            
            # Sort features by importance
            sorted_importance = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            
            predictions_with_importance.append({
                'predicted_price': original_pred['predicted_price'],
                'confidence': original_pred['confidence'],
                'feature_importance': dict(sorted_importance),
                'top_features': sorted_importance[:5],
                'most_important_feature': sorted_importance[0] if sorted_importance else None
            })
        
        return predictions_with_importance
    
    def predict_batch_with_progress_tracking(self, 
                                           features_list: List[Dict[str, Any]], 
                                           model_name: str = None,
                                           progress_callback: callable = None) -> List[Dict[str, Any]]:
        """Make batch predictions with progress tracking."""
        total_batches = len(features_list) // self.batch_size + (1 if len(features_list) % self.batch_size else 0)
        all_predictions = []
        
        for i in range(0, len(features_list), self.batch_size):
            batch = features_list[i:i + self.batch_size]
            batch_predictions = self.predictor.predict_batch(batch, model_name)
            all_predictions.extend(batch_predictions)
            
            # Report progress
            progress = (i + len(batch)) / len(features_list) * 100
            if progress_callback:
                progress_callback(progress, i + len(batch), len(features_list))
            else:
                print(f"Progress: {progress:.1f}% ({i + len(batch)}/{len(features_list)})")
        
        return all_predictions
    
    def predict_with_error_handling(self, 
                                  features_list: List[Dict[str, Any]], 
                                  model_name: str = None,
                                  continue_on_error: bool = True) -> Dict[str, Any]:
        """Make predictions with comprehensive error handling."""
        successful_predictions = []
        failed_predictions = []
        errors = []
        
        for i, features in enumerate(features_list):
            try:
                pred = self.predictor.predict_single(features, model_name)
                pred['input_index'] = i
                successful_predictions.append(pred)
            except Exception as e:
                error_info = {
                    'input_index': i,
                    'error_message': str(e),
                    'input_features': features
                }
                failed_predictions.append(error_info)
                errors.append(f"Error processing item {i}: {e}")
                
                if not continue_on_error:
                    break
        
        results = {
            'successful_predictions': successful_predictions,
            'failed_predictions': failed_predictions,
            'errors': errors,
            'total_processed': len(features_list),
            'successful_count': len(successful_predictions),
            'failed_count': len(failed_predictions),
            'success_rate': len(successful_predictions) / len(features_list) if features_list else 0,
            'model_used': model_name or self.predictor.default_model
        }
        
        return results
    
    def predict_with_caching(self, 
                           features_list: List[Dict[str, Any]], 
                           model_name: str = None,
                           cache_size: int = 10000) -> List[Dict[str, Any]]:
        """Make predictions with feature caching for performance."""
        from functools import lru_cache
        
        # Create cache key function
        def create_cache_key(features: Dict[str, Any]) -> str:
            # Create a deterministic key from features
            key_parts = []
            for k in sorted(features.keys()):
                value = features[k]
                if isinstance(value, (int, float)):
                    key_parts.append(f"{k}:{value}")
                else:
                    key_parts.append(f"{k}:{str(value)}")
            return "|".join(key_parts)
        
        # Cache for predictions
        @lru_cache(maxsize=cache_size)
        def cached_predict(cache_key: str, model_name: str) -> Dict[str, Any]:
            # Reconstruct features from cache key (simplified)
            # In practice, you'd store the actual features
            return {'predicted_price': 0, 'confidence': 0.5}  # Placeholder
        
        predictions = []
        cache_hits = 0
        cache_misses = 0
        
        for features in features_list:
            cache_key = create_cache_key(features)
            
            # Check cache
            try:
                cached_result = cached_predict(cache_key, model_name or 'default')
                if cached_result['predicted_price'] > 0:  # Valid cache hit
                    predictions.append(cached_result)
                    cache_hits += 1
                    continue
            except:
                pass
            
            # Cache miss - make prediction
            pred = self.predictor.predict_single(features, model_name)
            predictions.append(pred)
            cache_misses += 1
        
        return predictions
    
    def predict_with_async_processing(self, 
                                    features_list: List[Dict[str, Any]], 
                                    model_name: str = None) -> Dict[str, Any]:
        """Make predictions using async processing for I/O bound operations."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        async def predict_async(features_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            loop = asyncio.get_event_loop()
            
            with ThreadPoolExecutor() as executor:
                tasks = []
                for features in features_batch:
                    task = loop.run_in_executor(
                        executor, 
                        self.predictor.predict_single, 
                        features, 
                        model_name
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Filter out exceptions
                successful_results = []
                for result in results:
                    if not isinstance(result, Exception):
                        successful_results.append(result)
                
                return successful_results
        
        # Run async prediction
        start_time = time.time()
        
        # Split into smaller batches for async processing
        async_batch_size = min(100, len(features_list))
        all_predictions = []
        
        for i in range(0, len(features_list), async_batch_size):
            batch = features_list[i:i + async_batch_size]
            batch_predictions = asyncio.run(predict_async(batch))
            all_predictions.extend(batch_predictions)
        
        end_time = time.time()
        
        return {
            'predictions': all_predictions,
            'total_processed': len(features_list),
            'successful_predictions': len(all_predictions),
            'processing_time_seconds': end_time - start_time,
            'predictions_per_second': len(all_predictions) / (end_time - start_time) if end_time > start_time else 0
        }
    
    def get_prediction_statistics(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive statistics for predictions."""
        if not predictions:
            return {}
        
        prices = [pred['predicted_price'] for pred in predictions if 'predicted_price' in pred]
        confidences = [pred['confidence'] for pred in predictions if 'confidence' in pred]
        
        stats = {
            'total_predictions': len(predictions),
            'price_statistics': {
                'mean': np.mean(prices) if prices else 0,
                'median': np.median(prices) if prices else 0,
                'std': np.std(prices) if prices else 0,
                'min': np.min(prices) if prices else 0,
                'max': np.max(prices) if prices else 0,
                'q25': np.percentile(prices, 25) if prices else 0,
                'q75': np.percentile(prices, 75) if prices else 0
            },
            'confidence_statistics': {
                'mean': np.mean(confidences) if confidences else 0,
                'median': np.median(confidences) if confidences else 0,
                'std': np.std(confidences) if confidences else 0,
                'min': np.min(confidences) if confidences else 0,
                'max': np.max(confidences) if confidences else 0
            },
            'price_ranges': {
                'under_5000': sum(1 for p in prices if p < 5000),
                '5000_to_10000': sum(1 for p in prices if 5000 <= p < 10000),
                '10000_to_20000': sum(1 for p in prices if 10000 <= p < 20000),
                '20000_to_30000': sum(1 for p in prices if 20000 <= p < 30000),
                '30000_to_50000': sum(1 for p in prices if 30000 <= p < 50000),
                'over_50000': sum(1 for p in prices if p >= 50000)
            }
        }
        
        return stats
    
    def export_predictions_to_excel(self, 
                                  predictions: List[Dict[str, Any]], 
                                  output_path: str,
                                  include_statistics: bool = True) -> Dict[str, Any]:
        """Export predictions to Excel format with multiple sheets."""
        try:
            import pandas as pd
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Main predictions sheet
                predictions_df = pd.DataFrame(predictions)
                predictions_df.to_excel(writer, sheet_name='Predictions', index=False)
                
                if include_statistics:
                    # Statistics sheet
                    stats = self.get_prediction_statistics(predictions)
                    stats_data = []
                    
                    for category, values in stats.items():
                        if isinstance(values, dict):
                            for metric, value in values.items():
                                stats_data.append({
                                    'Category': category,
                                    'Metric': metric,
                                    'Value': value
                                })
                    
                    stats_df = pd.DataFrame(stats_data)
                    stats_df.to_excel(writer, sheet_name='Statistics', index=False)
                
                # Summary sheet
                summary_data = {
                    'Metric': ['Total Predictions', 'Export Date', 'Model Used'],
                    'Value': [
                        len(predictions),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'BatchPredictor'
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            return {
                'success': True,
                'output_file': output_path,
                'predictions_exported': len(predictions),
                'sheets_created': ['Predictions', 'Statistics', 'Summary'] if include_statistics else ['Predictions', 'Summary']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'output_file': output_path
            }
