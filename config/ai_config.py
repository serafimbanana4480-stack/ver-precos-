"""
AI configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class LLMConfig(BaseModel):
    """Configuration for LLM AI features."""
    
    enabled: bool = True
    provider: str = "ollama"  # ollama or grok
    model: str = "llama3"
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout_seconds: int = 60
    
    # Grok-specific
    grok_api_key: Optional[str] = None
    grok_model: str = "grok-1"
    
    # Ollama-specific
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    
    # Prompts
    analysis_prompt: str = "Analyze this vehicle listing for hidden issues and value-adding features."
    summary_prompt: str = "Summarize this vehicle listing in 2-3 sentences."
    recommendation_prompt: str = "Would you recommend this vehicle? Yes or No, with reasons."


class VisionConfig(BaseModel):
    """Configuration for Vision AI features."""
    
    enabled: bool = True
    provider: str = "ollama"  # ollama or local
    model: str = "llava"
    timeout_seconds: int = 30
    confidence_threshold: float = 0.7
    
    # Detection tasks
    detect_damage: bool = True
    detect_tire_condition: bool = True
    detect_interior_wear: bool = True
    detect_exterior_condition: bool = True
    
    # Image processing
    max_image_size_mb: int = 10
    supported_formats: list = ["jpg", "jpeg", "png", "webp"]


class AIConfig(BaseModel):
    """Configuration for all AI features."""
    
    llm: LLMConfig = LLMConfig()
    vision: VisionConfig = VisionConfig()
    
    # Global AI settings
    parallel_requests: int = 2
    cache_results: bool = True
    cache_ttl_seconds: int = 3600


ai_config = AIConfig()
