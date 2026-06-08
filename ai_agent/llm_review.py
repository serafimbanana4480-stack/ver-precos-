"""
LLM-based review of vehicle descriptions
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone

from config import settings
from validation.ai_models import LLMReviewResponse
from database.models import Vehicle, AIReview
from database.db import get_db_context
from utils.retry import retry_ai_api

logger = logging.getLogger(__name__)


class LLMReviewer:
    """Review vehicle descriptions using LLM"""
    
    def __init__(self) -> None:
        self.api_key = settings.grok_api_key
        # Check if grok_api_url is available in settings (package config) or fallback to root config alias
        self.api_url = getattr(settings, 'grok_api_url', 'https://api.x.ai/v1')
        self.use_ollama = settings.use_ollama
        self.ollama_url = settings.ollama_url
        self.model = settings.ai_model
        
        self.system_prompt = """You are an expert automotive analyst specializing in the Portuguese used car market. Your task is to analyze vehicle listings and identify:

1. **Red Flags / Hidden Issues:**
   - Accident history indicators (mentions of "batida", "sinistro", "dano", "reparação")
   - Mechanical problems (motor, caixa, embraiagem, travões)
   - Odometer tampering suspicions
   - Missing documentation issues
   - Seller credibility concerns

2. **Value-Adding Features:**
   - Recent maintenance (revisões, mudança de óleo, correia dentada)
   - Premium extras (teto de abrir, navegação, câmeras, sensores)
   - Low owner count
   - Garage kept
   - Non-smoker

3. **Market Position Assessment:**
   - Is the price realistic for the condition described?
   - How does it compare to typical market values?
   - Is this a good deal opportunity?

4. **Overall Recommendation:**
   - APPROVED: Good deal, proceed
   - REJECTED: High risk, avoid
   - CAUTION: Investigate further

Provide your analysis in Portuguese with specific evidence from the description."""
    
    async def analyze(self, description: str) -> Optional[Dict[str, object]]:
        """Analyze free-text listing description (legacy/test API)."""
        prompt = f"Analyze this vehicle listing description:\n\n{description}"
        response = self._call_llm(prompt)
        if not response:
            return {
                "recommendation": "Neutral",
                "confidence": 0.0,
                "issues": [],
                "reasoning": "AI unavailable",
            }
        try:
            import json
            data = json.loads(response) if isinstance(response, str) else response
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"recommendation": "Neutral", "confidence": 0.5, "analysis": response}

    def review_vehicle(self, vehicle: Vehicle) -> Optional[AIReview]:
        """
        Review a vehicle using LLM
        
        Args:
            vehicle: Vehicle to review
        
        Returns:
            AIReview object or None if review fails
        """
        if not vehicle.description:
            logger.warning(f"No description to review for vehicle {vehicle.id}")
            return None
        
        try:
            # Build prompt with vehicle information
            prompt = self._build_prompt(vehicle)
            
            # Get LLM response
            response = self._call_llm(prompt)
            
            if not response:
                return None
            
            # Parse response for approval and score
            approval, score = self._parse_response(response)
            
            # Create AI review record
            review = AIReview(
                vehicle_id=vehicle.id,
                review_type="description",
                model_used=self.model,
                prompt_used=prompt,
                analysis=response,
                score=score,
                approval=approval,
                confidence=0.8,  # Default confidence
                created_at=datetime.now(timezone.utc)
            )
            
            # Update vehicle with review
            with get_db_context() as db:
                vehicle.ai_review = response
                vehicle.ai_approved = approval
                vehicle.ai_confidence = 0.8
                vehicle.ai_review_date = datetime.now(timezone.utc)
                db.add(review)
                db.commit()
            
            logger.info(f"Completed LLM review for vehicle {vehicle.id}")
            return review
            
        except Exception as e:
            logger.error(f"Error reviewing vehicle {vehicle.id}: {e}")
            return None
    
    def _build_prompt(self, vehicle: Vehicle) -> str:
        """Build prompt for LLM"""
        prompt = f"""Analyze this vehicle listing:

**Vehicle Details:**
- Brand: {vehicle.brand}
- Model: {vehicle.model}
- Year: {vehicle.year}
- KM: {vehicle.km}
- Price: €{vehicle.price}
- Location: {vehicle.location}

**Description:**
{vehicle.description}

**Images Available:** {vehicle.image_count} images

Please provide your analysis following the guidelines above. Be specific and cite evidence from the description."""
        
        return prompt
    
    @retry_ai_api(max_attempts=3, min_wait=2, max_wait=10)
    def _call_llm(self, prompt: str) -> Optional[str]:
        """
        Call LLM API (Grok or Ollama)
        
        Args:
            prompt: Prompt to send
        
        Returns:
            LLM response or None if call fails
        """
        if self.use_ollama:
            response = self._call_ollama(prompt)
        else:
            response = self._call_grok(prompt)
        
        # Validate LLM response using pydantic model
        if response:
            try:
                # Parse response as JSON for validation
                import json
                response_dict = json.loads(response) if isinstance(response, str) else response
                LLMReviewResponse(**response_dict)
            except Exception as e:
                logger.warning(f"LLM response validation failed: {e}")
                return None
        
        return response
    
    def _call_grok(self, prompt: str) -> Optional[str]:
        """Call Grok API"""
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
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return None
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call local Ollama API"""
        try:
            import requests
        except ImportError:
            logger.error("Requests library not installed")
            return None
        
        headers = {"Content-Type": "application/json"}
        
        data = {
            "model": self.model,
            "prompt": f"{self.system_prompt}\n\n{prompt}",
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
                return result.get("response", "")
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            return None
    
    def _parse_response(self, response: str) -> tuple[bool, float]:
        """
        Parse LLM response for approval and score
        
        Args:
            response: LLM response text
        
        Returns:
            Tuple of (approval: bool, score: float)
        """
        response_lower = response.lower()
        
        # Determine approval
        if "aprovado" in response_lower or "approved" in response_lower:
            approval = True
        elif "rejeitado" in response_lower or "rejected" in response_lower:
            approval = False
        elif "caution" in response_lower or "cautela" in response_lower:
            approval = True  # Caution means proceed with care, not reject
        else:
            approval = True  # Default to approve if unclear
        
        # Determine score (0-10) based on sentiment
        if approval:
            if "excelente" in response_lower or "excellent" in response_lower:
                score = 9.0
            elif "muito bom" in response_lower or "very good" in response_lower:
                score = 8.0
            elif "bom" in response_lower or "good" in response_lower:
                score = 7.0
            else:
                score = 6.0
        else:
            if "evitar" in response_lower or "avoid" in response_lower:
                score = 2.0
            elif "alto risco" in response_lower or "high risk" in response_lower:
                score = 3.0
            else:
                score = 4.0
        
        return approval, score
    
    def batch_review(self, vehicles: List[Vehicle], limit: int = 50) -> List[AIReview]:
        """
        Review multiple vehicles in batch
        
        Args:
            vehicles: List of vehicles to review
            limit: Maximum number to review
        
        Returns:
            List of AIReview objects
        """
        reviews = []
        
        for vehicle in vehicles[:limit]:
            review = self.review_vehicle(vehicle)
            if review:
                reviews.append(review)
        
        logger.info(f"Completed batch review: {len(reviews)} reviews")
        return reviews


if __name__ == "__main__":
    # Test reviewer
    from database.db import get_db_context
    
    reviewer = LLMReviewer()
    
    with get_db_context() as db:
        vehicle = db.query(Vehicle).filter(Vehicle.description.isnot(None)).first()
        if vehicle:
            review = reviewer.review_vehicle(vehicle)
            print(f"Review completed: {review}")
