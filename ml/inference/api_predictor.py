"""
API predictor for ML inference endpoints.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime
import uuid
import json
import os

from .predictor import Predictor
from .batch_predictor import BatchPredictor


class PredictionRequest(BaseModel):
    """Request model for single prediction."""
    make: str = Field(..., description="Car make")
    model: str = Field(..., description="Car model")
    year: int = Field(..., ge=1900, le=2030, description="Car year")
    mileage: int = Field(..., ge=0, description="Car mileage in km")
    engine_size: float = Field(..., ge=0.0, description="Engine size in liters")
    fuel_type: str = Field(..., description="Fuel type")
    transmission: str = Field(..., description="Transmission type")
    condition: str = Field(..., description="Car condition")
    location: str = Field(..., description="Car location")


class BatchPredictionRequest(BaseModel):
    """Request model for batch prediction."""
    predictions: List[PredictionRequest] = Field(..., description="List of car predictions")
    model_name: Optional[str] = Field(None, description="Model name to use")


class PredictionResponse(BaseModel):
    """Response model for prediction."""
    predicted_price: float = Field(..., description="Predicted price")
    confidence: float = Field(..., description="Prediction confidence")
    model_used: str = Field(..., description="Model used for prediction")
    timestamp: str = Field(..., description="Prediction timestamp")


class BatchPredictionResponse(BaseModel):
    """Response model for batch prediction."""
    predictions: List[PredictionResponse] = Field(..., description="List of predictions")
    total_predictions: int = Field(..., description="Total number of predictions")
    model_used: str = Field(..., description="Model used for predictions")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class APIPredictor:
    """API predictor for ML inference endpoints."""
    
    def __init__(self, model_dir: str = "models"):
        """Initialize API predictor."""
        self.predictor = Predictor(model_dir)
        self.batch_predictor = BatchPredictor(model_dir)
        self.app = FastAPI(title="VER PRECOS ML API", version="1.0.0")
        self.prediction_history = {}
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup API routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "message": "VER PRECOS ML API",
                "version": "1.0.0",
                "available_models": self.predictor.get_loaded_models(),
                "default_model": self.predictor.default_model
            }
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "loaded_models": self.predictor.get_loaded_models()
            }
        
        @self.app.get("/models")
        async def get_available_models():
            """Get available models."""
            return {
                "available_models": self.predictor.get_loaded_models(),
                "default_model": self.predictor.default_model
            }
        
        @self.app.post("/predict", response_model=PredictionResponse)
        async def predict_single(request: PredictionRequest, model_name: Optional[str] = None):
            """Make single prediction."""
            try:
                features = request.dict()
                result = self.predictor.predict_single(features, model_name)
                
                response = PredictionResponse(
                    predicted_price=result['predicted_price'],
                    confidence=result['confidence'],
                    model_used=result['model_used'],
                    timestamp=result['timestamp']
                )
                
                # Store prediction history
                prediction_id = str(uuid.uuid4())
                self.prediction_history[prediction_id] = {
                    'request': features,
                    'response': result,
                    'timestamp': datetime.now().isoformat()
                }
                
                return response
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/predict/batch", response_model=BatchPredictionResponse)
        async def predict_batch(request: BatchPredictionRequest):
            """Make batch prediction."""
            try:
                start_time = datetime.now()
                
                # Convert requests to feature list
                features_list = [pred.dict() for pred in request.predictions]
                
                # Make predictions
                results = self.predictor.predict_batch(features_list, request.model_name)
                
                # Convert to response format
                predictions = []
                for result in results:
                    prediction = PredictionResponse(
                        predicted_price=result['predicted_price'],
                        confidence=result['confidence'],
                        model_used=result['model_used'],
                        timestamp=result['timestamp']
                    )
                    predictions.append(prediction)
                
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                
                response = BatchPredictionResponse(
                    predictions=predictions,
                    total_predictions=len(predictions),
                    model_used=results[0]['model_used'] if results else 'unknown',
                    processing_time_ms=processing_time
                )
                
                return response
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/predict/async")
        async def predict_async(request: PredictionRequest, background_tasks: BackgroundTasks, model_name: Optional[str] = None):
            """Make asynchronous prediction."""
            prediction_id = str(uuid.uuid4())
            
            # Add background task for processing
            background_tasks.add_task(
                self._process_prediction_async,
                prediction_id,
                request.dict(),
                model_name
            )
            
            return {
                "prediction_id": prediction_id,
                "status": "processing",
                "message": "Prediction is being processed asynchronously"
            }
        
        @self.app.get("/predict/async/{prediction_id}")
        async def get_async_prediction_status(prediction_id: str):
            """Get async prediction status."""
            if prediction_id not in self.prediction_history:
                raise HTTPException(status_code=404, detail="Prediction not found")
            
            prediction_data = self.prediction_history[prediction_id]
            
            return {
                "prediction_id": prediction_id,
                "status": prediction_data.get('status', 'completed'),
                "result": prediction_data.get('result'),
                "timestamp": prediction_data['timestamp']
            }
        
        @self.app.get("/models/{model_name}/features")
        async def get_model_features(model_name: str):
            """Get feature importance for a model."""
            try:
                if model_name not in self.predictor.get_loaded_models():
                    self.predictor.load_model(model_name)
                
                feature_importance = self.predictor.get_feature_importance(model_name)
                
                return {
                    "model_name": model_name,
                    "feature_importance": feature_importance
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/models/{model_name}/validate")
        async def validate_model(model_name: str):
            """Validate a model."""
            try:
                # Create sample data for validation
                sample_features = {
                    'make': 'Toyota',
                    'model': 'Corolla',
                    'year': 2020,
                    'mileage': 50000,
                    'engine_size': 1.8,
                    'fuel_type': 'Gasoline',
                    'transmission': 'Automatic',
                    'condition': 'Good',
                    'location': 'Lisbon'
                }
                
                result = self.predictor.predict_single(sample_features, model_name)
                
                return {
                    "model_name": model_name,
                    "validation_status": "success",
                    "sample_prediction": result,
                    "validation_timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                return {
                    "model_name": model_name,
                    "validation_status": "failed",
                    "error": str(e),
                    "validation_timestamp": datetime.now().isoformat()
                }
        
        @self.app.get("/predictions/history")
        async def get_prediction_history(limit: int = 100):
            """Get prediction history."""
            history_items = list(self.prediction_history.items())[-limit:]
            
            return {
                "total_predictions": len(self.prediction_history),
                "predictions": [
                    {
                        "prediction_id": pred_id,
                        "timestamp": data['timestamp'],
                        "model_used": data['response'].get('model_used'),
                        "predicted_price": data['response'].get('predicted_price')
                    }
                    for pred_id, data in history_items
                ]
            }
        
        @self.app.delete("/predictions/history")
        async def clear_prediction_history():
            """Clear prediction history."""
            self.prediction_history.clear()
            
            return {
                "message": "Prediction history cleared",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _process_prediction_async(self, 
                                       prediction_id: str, 
                                       features: Dict[str, Any], 
                                       model_name: Optional[str]) -> None:
        """Process prediction asynchronously."""
        try:
            result = self.predictor.predict_single(features, model_name)
            
            self.prediction_history[prediction_id] = {
                'status': 'completed',
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.prediction_history[prediction_id] = {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def load_default_model(self, model_name: str) -> None:
        """Load default model for API."""
        self.predictor.load_model(model_name)
        self.predictor.set_default_model(model_name)
    
    def set_feature_columns(self, columns: List[str]) -> None:
        """Set expected feature columns."""
        self.predictor.set_feature_columns(columns)
    
    def get_app(self) -> FastAPI:
        """Get FastAPI application instance."""
        return self.app
    
    def run_server(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Run the API server."""
        import uvicorn
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
