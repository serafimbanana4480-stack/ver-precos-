"""
Vision AI analysis of vehicle images
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
import requests

from config import settings
from database.models import Vehicle, AIReview
from database.db import get_db_context
from utils.retry import retry_ai_api
from validation.ai_models import VisionAnalysisResponse

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Analyze vehicle images using vision AI"""
    
    def __init__(self) -> None:
        self.api_key = settings.grok_api_key
        # Check if grok_api_url is available in settings (package config) or fallback to root config alias
        self.api_url = getattr(settings, 'grok_api_url', 'https://api.x.ai/v1')
        self.use_ollama = settings.use_ollama
        self.ollama_url = settings.ollama_url
        self.model = getattr(settings, 'vision_model', settings.ai_model)
        
        self.system_prompt = """You are an expert automotive visual analyst. Analyze vehicle images to identify:

1. **Exterior Condition:**
   - Dents, scratches, paint damage
   - Rust or corrosion
   - Misaligned panels (accident indicators)
   - Windshield/Window damage
   - Light/Headlight condition

2. **Tire Condition:**
   - Tread depth
   - Uneven wear patterns
   - Age/cracking

3. **Interior Condition:**
   - Seat wear and tears
   - Dashboard condition
   - Steering wheel wear
   - Cleanliness/maintenance level

4. **Overall Assessment:**
   - Condition score (0-10)
   - Major concerns
   - Positive aspects

Provide detailed analysis in Portuguese with specific observations from the images."""
    
    def analyze_vehicle_images(self, vehicle: Vehicle, max_images: int = 3) -> Optional[AIReview]:
        """
        Analyze vehicle images using vision AI
        
        Args:
            vehicle: Vehicle to analyze
            max_images: Maximum number of images to analyze
        
        Returns:
            AIReview object or None if analysis fails
        """
        if not vehicle.images or len(vehicle.images) == 0:
            logger.warning(f"No images to analyze for vehicle {vehicle.id}")
            return None
        
        try:
            # Get first N images
            image_urls = vehicle.images[:max_images]
            
            # Build prompt
            prompt = self._build_prompt(vehicle)
            
            # Get vision analysis
            response = self._call_vision_api(prompt, image_urls)
            
            if not response:
                return None
            
            # Parse response for condition score
            condition_score = self._parse_condition_score(response)
            
            # Detect damages
            damages = self._detect_damages(response)
            
            # Create AI review record
            review = AIReview(
                vehicle_id=vehicle.id,
                review_type="vision",
                model_used=self.model,
                prompt_used=prompt,
                analysis=response,
                score=condition_score,
                approval=condition_score >= 6.0,
                confidence=0.7,
                issues=damages,
                created_at=datetime.now(timezone.utc)
            )
            
            # Update vehicle with analysis
            with get_db_context() as db:
                vehicle.condition_score = condition_score
                vehicle.damages_detected = damages
                vehicle.has_accident = self._detect_accident_indicators(response)
                db.add(review)
                db.commit()
            
            logger.info(f"Completed vision analysis for vehicle {vehicle.id}")
            return review
            
        except Exception as e:
            logger.error(f"Error analyzing vehicle {vehicle.id}: {e}")
            return None
    
    def _build_prompt(self, vehicle: Vehicle) -> str:
        """Build prompt for vision analysis"""
        prompt = f"""Analyze these images of a vehicle:

**Vehicle Details:**
- Brand: {vehicle.brand}
- Model: {vehicle.model}
- Year: {vehicle.year}
- KM: {vehicle.km}
- Price: €{vehicle.price}

Please examine the images carefully and provide a detailed condition assessment following the guidelines above. Pay special attention to any signs of accidents, rust, or poor maintenance."""
        
        return prompt
    
    def _call_vision_api(self, prompt: str, image_urls: List[str]) -> Optional[str]:
        """
        Call vision API (Grok Vision or Ollama)
        
        Args:
            prompt: Text prompt
            image_urls: List of image URLs
        
        Returns:
            Analysis response or None if call fails
        """
        if self.use_ollama:
            return self._call_ollama_vision(prompt, image_urls)
        else:
            return self._call_grok_vision(prompt, image_urls)
    
    @retry_ai_api(max_attempts=3, min_wait=2, max_wait=10)
    def _call_grok_vision(self, prompt: str, image_urls: List[str]) -> Optional[str]:
        """Call Grok Vision API"""
        try:
            import requests
        except ImportError:
            logger.error("Requests library not installed")
            return None
        
        if not self.api_key:
            logger.error("Grok API key not configured")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Build content with images
        content = [{"type": "text", "text": prompt}]
        
        for url in image_urls:
            # Try to download and encode image
            try:
                img_response = requests.get(url, timeout=10)
                if img_response.status_code == 200:
                    import base64
                    base64_image = base64.b64encode(img_response.content).decode('utf-8')
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    })
            except Exception as e:
                logger.warning(f"Failed to download image {url}: {e}")
                continue
        
        if len(content) == 1:  # No images loaded
            logger.warning("No images could be loaded for analysis")
            return None
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": content}
            ],
            "max_tokens": 1500,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=90
            )
            
            if response.status_code == 200:
                result = response.json()
                response_content = result["choices"][0]["message"]["content"]
                
                # Validate vision response using pydantic model
                try:
                    import json
                    response_dict = json.loads(response_content) if isinstance(response_content, str) else response_content
                    if isinstance(response_dict, dict):
                        VisionAnalysisResponse(**response_dict)
                except Exception as e:
                    logger.warning(f"Vision response validation failed: {e}, using text parse fallback")
                
                return response_content
            else:
                logger.error(f"Grok Vision API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Grok Vision API: {e}")
            return None
    
    @retry_ai_api(max_attempts=3, min_wait=2, max_wait=10)
    def _call_ollama_vision(self, prompt: str, image_urls: List[str]) -> Optional[str]:
        """Call Ollama Vision API"""
        try:
            import requests
        except ImportError:
            logger.error("Requests library not installed")
            return None
        
        # Ollama vision support varies by model
        # This is a basic implementation
        headers = {"Content-Type": "application/json"}
        
        # For Ollama, we need to provide images as base64 or local paths
        # This is a simplified version - adjust based on your Ollama setup
        data = {
            "model": self.model,
            "prompt": f"{self.system_prompt}\n\n{prompt}\n\nImages: {', '.join(image_urls)}",
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                response_content = result.get("response", "")
                
                # Validate vision response using pydantic model
                try:
                    import json
                    response_dict = json.loads(response_content) if isinstance(response_content, str) else response_content
                    if isinstance(response_dict, dict):
                        VisionAnalysisResponse(**response_dict)
                except Exception as e:
                    logger.warning(f"Vision response validation failed: {e}, using text parse fallback")
                
                return response_content
            else:
                logger.error(f"Ollama Vision API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Ollama Vision API: {e}")
            return None
    
    def _parse_condition_score(self, response: str) -> float:
        """
        Parse condition score from response
        
        Args:
            response: Vision analysis response
        
        Returns:
            Condition score (0-10)
        """
        response_lower = response.lower()
        
        # Look for explicit score mentions
        import re
        score_match = re.search(r'(\d+)/10', response_lower)
        if score_match:
            try:
                return float(score_match.group(1))
            except ValueError:
                pass
        
        # Infer from language
        if "excelente" in response_lower or "impecável" in response_lower:
            return 9.0
        elif "muito bom" in response_lower:
            return 8.0
        elif "bom" in response_lower:
            return 7.0
        elif "razoável" in response_lower or "aceitável" in response_lower:
            return 5.0
        elif "mau" in response_lower or "fraco" in response_lower:
            return 3.0
        else:
            return 6.0  # Default
    
    def _detect_damages(self, response: str) -> List[str]:
        """
        Detect damages mentioned in response
        
        Args:
            response: Vision analysis response
        
        Returns:
            List of detected damages
        """
        damages = []
        response_lower = response.lower()
        
        damage_keywords = {
            "amassado": "Amassados",
            "arranhão": "Arranhões",
            "ferrugem": "Ferrugem",
            "rust": "Ferrugem",
            "batida": "Batida",
            "painel desencaixado": "Painel desencaixado",
            "vidro partido": "Vidro partido",
            "para-choques danificado": "Para-choques danificado",
            "farol partido": "Farol partido",
            "pneu gasto": "Pneus gastos",
            "luz fundida": "Luz fundida",
            "corroded": "Corrosão"
        }
        
        for keyword, damage in damage_keywords.items():
            if keyword in response_lower:
                damages.append(damage)
        
        return damages
    
    def _detect_accident_indicators(self, response: str) -> bool:
        """
        Detect accident indicators in response
        
        Args:
            response: Vision analysis response
        
        Returns:
            True if accident indicators found
        """
        response_lower = response.lower()
        
        accident_indicators = [
            "painel desencaixado",
            "diferença de cor",
            "reparação de batida",
            "sinistro",
            "acidente",
            "chassi danificado"
        ]
        
        for indicator in accident_indicators:
            if indicator in response_lower:
                return True
        
        return False
    
    def batch_analyze(self, vehicles: List[Vehicle], limit: int = 50) -> List[AIReview]:
        """
        Analyze multiple vehicles in batch
        
        Args:
            vehicles: List of vehicles to analyze
            limit: Maximum number to analyze
        
        Returns:
            List of AIReview objects
        """
        reviews = []
        
        for vehicle in vehicles[:limit]:
            review = self.analyze_vehicle_images(vehicle)
            if review:
                reviews.append(review)
        
        logger.info(f"Completed batch vision analysis: {len(reviews)} reviews")
        return reviews


if __name__ == "__main__":
    # Test analyzer
    from database.db import get_db_context
    
    analyzer = VisionAnalyzer()
    
    with get_db_context() as db:
        vehicle = db.query(Vehicle).filter(Vehicle.images.isnot(None)).first()
        if vehicle:
            review = analyzer.analyze_vehicle_images(vehicle)
            print(f"Analysis completed: {review}")
