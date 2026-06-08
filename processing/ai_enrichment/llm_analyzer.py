"""
LLM Analyzer for Vehicle Description Analysis
Production-grade LLM integration with structured output
"""
from __future__ import annotations
import logging
import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from validation.schemas import AIAnalysisResult

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """LLM analyzer for vehicle description reasoning"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.ollama_url = ollama_url
        self.model = model
        
        self.system_prompt = """You are an expert automotive analyst specializing in the Portuguese used car market.
Analyze vehicle listings and provide structured JSON output:

{
  "red_flags": ["accident history", "mechanical problems", "odometer tampering", "missing documentation"],
  "value_adding_features": ["recent maintenance", "premium extras", "low ownership", "garage kept"],
  "market_position": "underpriced | fair | overpriced",
  "risk_score": 0-10 (higher = more risky),
  "recommendation": "APPROVED | REJECTED | CAUTION",
  "confidence": 0-1,
  "reasoning": "detailed explanation in Portuguese"
}

Red flags to detect:
- "batida", "sinistro", "dano", "reparação" (accident indicators)
- "motor", "caixa", "embraiagem" problems (mechanical issues)
- Odómetro irregular
- Documentação em falta
- Credibilidade do vendedor

Value-adding features:
- Revisões recentes, mudança de óleo, correia dentada (maintenance)
- Teto de abrir, navegação, câmeras, sensores (extras)
- Baixo número de proprietários
- Garagem, não fumador

Provide analysis in Portuguese."""
    
    def analyze_vehicle(self, vehicle_data: Dict[str, Any]) -> Optional[AIAnalysisResult]:
        """
        Analyze vehicle description using LLM
        
        Args:
            vehicle_data: Vehicle data dictionary
            
        Returns:
            AIAnalysisResult with LLM analysis
        """
        if not vehicle_data.get('description'):
            logger.warning(f"No description for vehicle {vehicle_data.get('source_id')}")
            # Return neutral analysis if no description
            return self._get_neutral_analysis()
        
        try:
            start_time = datetime.utcnow()
            
            # Build prompt
            prompt = self._build_prompt(vehicle_data)
            
            # Call LLM
            response = self._call_ollama(prompt)
            
            if not response:
                logger.error("LLM returned no response")
                return self._get_neutral_analysis()
            
            # Parse response
            analysis = self._parse_response(response)
            
            reasoning = analysis.get('reasoning', '').strip()
            if not reasoning:
                reasoning = f"Análise automatizada para {vehicle_data.get('brand')} {vehicle_data.get('model')} ({vehicle_data.get('year')})."
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create result with placeholder Vision fields (will be filled by Vision analyzer)
            result = AIAnalysisResult(
                llm_red_flags=analysis.get('red_flags', []),
                llm_value_adding_features=analysis.get('value_adding_features', []),
                llm_market_position=analysis.get('market_position', 'fair'),
                llm_risk_score=analysis.get('risk_score', 5.0),
                llm_recommendation=analysis.get('recommendation', 'CAUTION'),
                llm_confidence=analysis.get('confidence', 0.5),
                llm_reasoning=reasoning,
                vision_exterior_damage=[],
                vision_accident_indicators=[],
                vision_tire_condition="fair",
                vision_interior_condition="fair",
                vision_condition_score=6.0,
                vision_major_concerns=[],
                vision_confidence=0.0,
                processing_time_llm=processing_time,
                processing_time_vision=0.0,
                models_used={"llm": self.model},
                created_at=datetime.utcnow()
            )
            
            logger.info(f"LLM analysis completed for vehicle {vehicle_data.get('source_id')}")
            return result
            
        except Exception as e:
            logger.error(f"LLM analysis failed for vehicle {vehicle_data.get('source_id')}: {e}")
            return self._get_neutral_analysis()
    
    def _build_prompt(self, vehicle_data: Dict[str, Any]) -> str:
        """Build prompt for LLM"""
        return f"""Analyze this vehicle listing:

Brand: {vehicle_data.get('brand')}
Model: {vehicle_data.get('model')}
Year: {vehicle_data.get('year')}
KM: {vehicle_data.get('km')}
Price: €{vehicle_data.get('price')}
Location: {vehicle_data.get('location')}
Description: {vehicle_data.get('description')}
Images: {len(vehicle_data.get('images', []))} available

Provide your analysis in the specified JSON format."""
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API"""
        try:
            headers = {"Content-Type": "application/json"}
            data = {
                "model": self.model,
                "prompt": f"{self.system_prompt}\n\n{prompt}",
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
                logger.error(f"Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return None
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response"""
        try:
            # Try to extract JSON from response
            if isinstance(response, str):
                # Look for JSON in the response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group(0)
            
            data = json.loads(response)
            
            # Normalize red_flags: ensure it's a list of strings
            red_flags = data.get('red_flags', [])
            if isinstance(red_flags, dict):
                # Convert dict to list of flag descriptions
                red_flags = [f"{k}: {v}" for k, v in red_flags.items() if v]
            elif not isinstance(red_flags, list):
                red_flags = [str(red_flags)] if red_flags else []
            # Ensure all items are strings
            red_flags = [str(item) for item in red_flags if item]
            data['red_flags'] = red_flags
            
            # Normalize value_adding_features similarly
            value_features = data.get('value_adding_features', [])
            if isinstance(value_features, dict):
                value_features = [f"{k}: {v}" for k, v in value_features.items() if v]
            elif not isinstance(value_features, list):
                value_features = [str(value_features)] if value_features else []
            value_features = [str(item) for item in value_features if item]
            data['value_adding_features'] = value_features
            
            return data
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._get_neutral_analysis_dict()
    
    def _get_neutral_analysis(self) -> AIAnalysisResult:
        """Return neutral analysis when LLM fails"""
        return AIAnalysisResult(
            llm_red_flags=[],
            llm_value_adding_features=[],
            llm_market_position="fair",
            llm_risk_score=5.0,
            llm_recommendation="CAUTION",
            llm_confidence=0.0,
            llm_reasoning="LLM analysis failed - using neutral values",
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
    
    def _get_neutral_analysis_dict(self) -> Dict[str, Any]:
        """Return neutral analysis as dict"""
        return {
            "red_flags": [],
            "value_adding_features": [],
            "market_position": "fair",
            "risk_score": 5.0,
            "recommendation": "CAUTION",
            "confidence": 0.0,
            "reasoning": "LLM analysis failed - using neutral values"
        }


# Singleton instance
llm_analyzer = LLMAnalyzer()
