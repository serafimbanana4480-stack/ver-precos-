"""
Vision AI Analyzer for Vehicle Image Analysis
Production-grade Vision AI integration with structured output
"""
from __future__ import annotations
import logging
import json
import requests
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime
from validation.schemas import AIAnalysisResult

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Vision AI analyzer for vehicle image analysis"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.ollama_url = ollama_url
        self.model = model
        
        self.system_prompt = """You are an expert automotive visual analyst.
Analyze vehicle images and provide structured JSON output:

{
  "exterior_damage": ["dents", "scratches", "rust", "paint damage"],
  "accident_indicators": ["panel misalignment", "color mismatch", "repaired areas"],
  "tire_condition": "good | fair | poor",
  "interior_condition": "excellent | good | fair | poor",
  "condition_score": 0-10,
  "major_concerns": [],
  "confidence": 0-1
}

Look for:
- Exterior: dents, scratches, rust, paint damage, windshield damage
- Accident indicators: panel misalignment, color difference, repair marks
- Tires: tread depth, wear patterns, cracking
- Interior: seat wear, dashboard condition, cleanliness

Provide analysis in Portuguese."""
    
    def analyze_vehicle_images(self, vehicle_data: Dict[str, Any], max_images: int = 3) -> Optional[AIAnalysisResult]:
        """
        Analyze vehicle images using Vision AI
        
        Args:
            vehicle_data: Vehicle data dictionary with images
            max_images: Maximum number of images to analyze
            
        Returns:
            AIAnalysisResult with Vision analysis
        """
        images = vehicle_data.get('images', [])
        
        if not images or len(images) == 0:
            logger.warning(f"No images for vehicle {vehicle_data.get('source_id')}")
            # Return neutral analysis if no images
            return self._get_neutral_vision_analysis()
        
        try:
            start_time = datetime.utcnow()
            
            # Download and encode images
            encoded_images = self._download_and_encode_images(images[:max_images])
            
            if not encoded_images:
                logger.error("Failed to download any images")
                return self._get_neutral_vision_analysis()
            
            # Build prompt
            prompt = self._build_prompt(vehicle_data)
            
            # Call Vision API
            response = self._call_vision_api(prompt, encoded_images)
            
            if not response:
                logger.error("Vision AI returned no response")
                return self._get_neutral_vision_analysis()
            
            # Parse response
            analysis = self._parse_response(response)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create result with placeholder LLM fields (will be filled by LLM analyzer)
            result = AIAnalysisResult(
                llm_red_flags=[],
                llm_value_adding_features=[],
                llm_market_position="fair",
                llm_risk_score=5.0,
                llm_recommendation="CAUTION",
                llm_confidence=0.0,
                llm_reasoning="Vision analysis completed. Condition assessed from images.",
                vision_exterior_damage=analysis.get('exterior_damage', []),
                vision_accident_indicators=analysis.get('accident_indicators', []),
                vision_tire_condition=analysis.get('tire_condition', 'fair'),
                vision_interior_condition=analysis.get('interior_condition', 'fair'),
                vision_condition_score=analysis.get('condition_score', 6.0),
                vision_major_concerns=analysis.get('major_concerns', []),
                vision_confidence=analysis.get('confidence', 0.5),
                processing_time_llm=0.0,
                processing_time_vision=processing_time,
                models_used={"vision": self.model},
                created_at=datetime.utcnow()
            )
            
            logger.info(f"Vision analysis completed for vehicle {vehicle_data.get('source_id')}")
            return result
            
        except Exception as e:
            logger.error(f"Vision analysis failed for vehicle {vehicle_data.get('source_id')}: {e}")
            return self._get_neutral_vision_analysis()
    
    def _download_and_encode_images(self, image_urls: List[str]) -> List[str]:
        """Download images and encode as base64"""
        encoded_images = []
        
        for url in image_urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    base64_image = base64.b64encode(response.content).decode('utf-8')
                    encoded_images.append(base64_image)
            except Exception as e:
                logger.warning(f"Failed to download image {url}: {e}")
                continue
        
        return encoded_images
    
    def _build_prompt(self, vehicle_data: Dict[str, Any]) -> str:
        """Build prompt for Vision analysis"""
        return f"""Analyze these images of a vehicle:

Brand: {vehicle_data.get('brand')}
Model: {vehicle_data.get('model')}
Year: {vehicle_data.get('year')}
KM: {vehicle_data.get('km')}
Price: €{vehicle_data.get('price')}

Examine the images carefully for damage, condition, and accident indicators.
Provide your analysis in the specified JSON format."""
    
    def _call_vision_api(self, prompt: str, encoded_images: List[str]) -> Optional[str]:
        """Call Vision API (Ollama with vision capability)"""
        try:
            headers = {"Content-Type": "application/json"}
            
            # Build content with images
            data = {
                "model": self.model,
                "prompt": f"{self.system_prompt}\n\n{prompt}",
                "images": encoded_images,
                "stream": False,
                "format": "json"
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                logger.error(f"Vision API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Vision API: {e}")
            return None
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Vision AI JSON response"""
        try:
            # Try to extract JSON from response
            if isinstance(response, str):
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group(0)
            
            data = json.loads(response)
            
            # Normalize list fields: ensure they are lists of strings
            for list_field in ['exterior_damage', 'accident_indicators', 'major_concerns']:
                value = data.get(list_field, [])
                if isinstance(value, dict):
                    value = [f"{k}: {v}" for k, v in value.items() if v]
                elif not isinstance(value, list):
                    value = [str(value)] if value else []
                data[list_field] = [str(item) for item in value if item]
            
            # Normalize condition_score to float
            try:
                data['condition_score'] = float(data.get('condition_score', 6.0))
            except (ValueError, TypeError):
                data['condition_score'] = 6.0
            
            # Normalize confidence to float
            try:
                data['confidence'] = float(data.get('confidence', 0.5))
            except (ValueError, TypeError):
                data['confidence'] = 0.5
            
            return data
        except Exception as e:
            logger.error(f"Failed to parse Vision response: {e}")
            return self._get_neutral_vision_dict()
    
    def _get_neutral_vision_analysis(self) -> AIAnalysisResult:
        """Return neutral vision analysis when Vision AI fails"""
        return AIAnalysisResult(
            llm_red_flags=[],
            llm_value_adding_features=[],
            llm_market_position="fair",
            llm_risk_score=5.0,
            llm_recommendation="CAUTION",
            llm_confidence=0.0,
            llm_reasoning="Vision analysis failed - unable to assess vehicle condition from images",
            vision_exterior_damage=[],
            vision_accident_indicators=[],
            vision_tire_condition="fair",
            vision_interior_condition="fair",
            vision_condition_score=6.0,
            vision_major_concerns=[],
            vision_confidence=0.0,
            processing_time_llm=0.0,
            processing_time_vision=0.0,
            models_used={},
            created_at=datetime.utcnow()
        )
    
    def _get_neutral_vision_dict(self) -> Dict[str, Any]:
        """Return neutral vision analysis as dict"""
        return {
            "exterior_damage": [],
            "accident_indicators": [],
            "tire_condition": "fair",
            "interior_condition": "fair",
            "condition_score": 6.0,
            "major_concerns": [],
            "confidence": 0.0
        }


# Singleton instance
vision_analyzer = VisionAnalyzer()
