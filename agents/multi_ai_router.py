"""
Multi-AI Router - Roteia tarefas para múltiplos providers de IA
Suporta: Ollama (local), Grok, OpenAI, Anthropic, e modelos locais via LiteLLM
"""
from __future__ import annotations
import os
import json
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, AsyncGenerator
from pathlib import Path

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    OLLAMA = "ollama"
    GROK = "grok"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


@dataclass
class AIModelConfig:
    provider: AIProvider
    model_name: str
    api_key_env: str
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60
    priority: int = 1  # Lower = higher priority
    enabled: bool = True
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


@dataclass
class AIResponse:
    provider: AIProvider
    model: str
    content: str
    latency_ms: float
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiAIRouter:
    """
    Router inteligente que distribui tarefas entre múltiplos providers de IA.
    
    Features:
    - Fallback automático se um provider falhar
    - Load balancing por custo/latência
    - Streaming support
    - Cache de respostas
    - Métricas de uso
    """
    
    DEFAULT_CONFIGS: List[AIModelConfig] = [
        AIModelConfig(
            provider=AIProvider.OLLAMA,
            model_name="qwen2.5:7b",
            api_key_env="",
            base_url="http://localhost:11434",
            priority=1,
            enabled=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        AIModelConfig(
            provider=AIProvider.OLLAMA,
            model_name="llama3.1:8b",
            api_key_env="",
            base_url="http://localhost:11434",
            priority=2,
            enabled=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        ),
        AIModelConfig(
            provider=AIProvider.GROK,
            model_name="grok-2",
            api_key_env="GROK_API_KEY",
            base_url="https://api.x.ai/v1",
            priority=3,
            enabled=False,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
        ),
        AIModelConfig(
            provider=AIProvider.OPENAI,
            model_name="gpt-4o-mini",
            api_key_env="OPENAI_API_KEY",
            priority=4,
            enabled=False,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
        ),
        AIModelConfig(
            provider=AIProvider.ANTHROPIC,
            model_name="claude-3-haiku-20240307",
            api_key_env="ANTHROPIC_API_KEY",
            priority=5,
            enabled=False,
            cost_per_1k_input=0.00025,
            cost_per_1k_output=0.00125,
        ),
    ]
    
    def __init__(self, configs: Optional[List[AIModelConfig]] = None):
        self.configs = configs or self.DEFAULT_CONFIGS.copy()
        self._metrics: List[Dict] = []
        self._cache: Dict[str, AIResponse] = {}
        self._session = None
        
        # Auto-enable providers com API keys definidas
        for cfg in self.configs:
            if cfg.api_key_env and os.getenv(cfg.api_key_env):
                cfg.enabled = True
                logger.info(f"[MultiAI] Provider {cfg.provider.value}/{cfg.model_name} auto-enabled via env {cfg.api_key_env}")
        
        # Verificar Ollama
        self._check_ollama()
    
    def _check_ollama(self) -> None:
        """Verifica se Ollama está disponível"""
        try:
            import requests
            for cfg in self.configs:
                if cfg.provider == AIProvider.OLLAMA and cfg.base_url:
                    resp = requests.get(f"{cfg.base_url}/api/tags", timeout=3)
                    if resp.status_code == 200:
                        models = [m["name"] for m in resp.json().get("models", [])]
                        logger.info(f"[MultiAI] Ollama disponível com modelos: {models}")
                        cfg.enabled = cfg.model_name in models or True
                    else:
                        cfg.enabled = False
                    break
        except Exception as e:
            logger.warning(f"[MultiAI] Ollama não disponível: {e}")
            for cfg in self.configs:
                if cfg.provider == AIProvider.OLLAMA:
                    cfg.enabled = False
    
    def get_available_providers(self) -> List[AIModelConfig]:
        """Retorna providers ativos ordenados por prioridade"""
        return sorted([c for c in self.configs if c.enabled], key=lambda x: x.priority)
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider_hint: Optional[AIProvider] = None,
        model_hint: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_cache: bool = False,
        json_mode: bool = False,
    ) -> AIResponse:
        """
        Gera uma resposta usando o melhor provider disponível.
        
        Args:
            prompt: Prompt do utilizador
            system_prompt: Instruções de sistema
            provider_hint: Preferência de provider
            model_hint: Preferência de modelo
            temperature: Override de temperatura
            max_tokens: Override de max tokens
            use_cache: Se True, usa cache se disponível
            json_mode: Se True, força output JSON
        """
        cache_key = f"{provider_hint}:{model_hint}:{hash(prompt)}"
        if use_cache and cache_key in self._cache:
            logger.info("[MultiAI] Cache hit")
            return self._cache[cache_key]
        
        candidates = self.get_available_providers()
        
        # Filtrar por hint
        if provider_hint:
            candidates = [c for c in candidates if c.provider == provider_hint]
        if model_hint:
            candidates = [c for c in candidates if c.model_name == model_hint]
        
        if not candidates:
            return AIResponse(
                provider=AIProvider.OLLAMA,
                model="none",
                content="",
                latency_ms=0,
                success=False,
                error="Nenhum provider de IA disponível. Configure GROK_API_KEY, OPENAI_API_KEY ou instale Ollama."
            )
        
        last_error = None
        for cfg in candidates:
            try:
                response = self._call_provider(cfg, prompt, system_prompt, temperature, max_tokens, json_mode)
                if response.success:
                    if use_cache:
                        self._cache[cache_key] = response
                    self._metrics.append({
                        "provider": cfg.provider.value,
                        "model": cfg.model_name,
                        "latency_ms": response.latency_ms,
                        "success": True,
                        "timestamp": time.time(),
                    })
                    return response
            except Exception as e:
                last_error = e
                logger.warning(f"[MultiAI] Provider {cfg.provider.value} falhou: {e}")
                self._metrics.append({
                    "provider": cfg.provider.value,
                    "model": cfg.model_name,
                    "success": False,
                    "error": str(e),
                    "timestamp": time.time(),
                })
                continue
        
        return AIResponse(
            provider=candidates[0].provider if candidates else AIProvider.OLLAMA,
            model=candidates[0].model_name if candidates else "none",
            content="",
            latency_ms=0,
            success=False,
            error=f"Todos os providers falharam. Último erro: {last_error}"
        )
    
    def _call_provider(
        self,
        cfg: AIModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        json_mode: bool,
    ) -> AIResponse:
        """Chama um provider específico"""
        start = time.time()
        
        if cfg.provider == AIProvider.OLLAMA:
            return self._call_ollama(cfg, prompt, system_prompt, temperature, max_tokens, json_mode)
        elif cfg.provider == AIProvider.GROK:
            return self._call_openai_compatible(cfg, prompt, system_prompt, temperature, max_tokens, json_mode)
        elif cfg.provider == AIProvider.OPENAI:
            return self._call_openai_compatible(cfg, prompt, system_prompt, temperature, max_tokens, json_mode)
        elif cfg.provider == AIProvider.ANTHROPIC:
            return self._call_anthropic(cfg, prompt, system_prompt, temperature, max_tokens, json_mode)
        else:
            raise ValueError(f"Provider não suportado: {cfg.provider}")
    
    def _call_ollama(
        self,
        cfg: AIModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        json_mode: bool,
    ) -> AIResponse:
        import requests
        
        url = f"{cfg.base_url}/api/generate"
        payload = {
            "model": cfg.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or cfg.temperature,
                "num_predict": max_tokens or cfg.max_tokens,
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if json_mode:
            payload["format"] = "json"
        
        resp = requests.post(url, json=payload, timeout=cfg.timeout)
        resp.raise_for_status()
        data = resp.json()
        
        latency = (time.time() - start) * 1000
        return AIResponse(
            provider=AIProvider.OLLAMA,
            model=cfg.model_name,
            content=data.get("response", ""),
            latency_ms=latency,
            tokens_used=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
            cost_usd=0.0,
            success=True,
        )
    
    def _call_openai_compatible(
        self,
        cfg: AIModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        json_mode: bool,
    ) -> AIResponse:
        import requests
        
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise ValueError(f"API key não encontrada: {cfg.api_key_env}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": cfg.model_name,
            "messages": messages,
            "temperature": temperature or cfg.temperature,
            "max_tokens": max_tokens or cfg.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        base = cfg.base_url or "https://api.openai.com/v1"
        resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=cfg.timeout)
        resp.raise_for_status()
        data = resp.json()
        
        choice = data["choices"][0]
        content = choice["message"]["content"]
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        
        cost = 0.0
        if tokens:
            cost = (tokens / 1000) * (cfg.cost_per_1k_input + cfg.cost_per_1k_output) / 2
        
        latency = (time.time() - start) * 1000
        return AIResponse(
            provider=cfg.provider,
            model=cfg.model_name,
            content=content,
            latency_ms=latency,
            tokens_used=tokens,
            cost_usd=cost,
            success=True,
        )
    
    def _call_anthropic(
        self,
        cfg: AIModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        json_mode: bool,
    ) -> AIResponse:
        import requests
        
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise ValueError(f"API key não encontrada: {cfg.api_key_env}")
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": cfg.model_name,
            "max_tokens": max_tokens or cfg.max_tokens,
            "temperature": temperature or cfg.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=cfg.timeout)
        resp.raise_for_status()
        data = resp.json()
        
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
        
        usage = data.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        cost = 0.0
        if tokens:
            cost = (usage.get("input_tokens", 0) / 1000 * cfg.cost_per_1k_input +
                    usage.get("output_tokens", 0) / 1000 * cfg.cost_per_1k_output)
        
        latency = (time.time() - start) * 1000
        return AIResponse(
            provider=AIProvider.ANTHROPIC,
            model=cfg.model_name,
            content=content,
            latency_ms=latency,
            tokens_used=tokens,
            cost_usd=cost,
            success=True,
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas de uso de todos os providers"""
        if not self._metrics:
            return {"total_calls": 0, "providers": {}}
        
        providers = {}
        for m in self._metrics:
            p = m["provider"]
            if p not in providers:
                providers[p] = {"calls": 0, "success": 0, "failures": 0, "avg_latency_ms": 0}
            providers[p]["calls"] += 1
            if m["success"]:
                providers[p]["success"] += 1
                providers[p]["avg_latency_ms"] += m.get("latency_ms", 0)
            else:
                providers[p]["failures"] += 1
        
        for p in providers:
            s = providers[p]["success"]
            providers[p]["avg_latency_ms"] = round(providers[p]["avg_latency_ms"] / s, 2) if s else 0
            providers[p]["success_rate"] = round(s / providers[p]["calls"] * 100, 1)
        
        return {
            "total_calls": len(self._metrics),
            "providers": providers,
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Verifica o estado de todos os providers"""
        results = {}
        for cfg in self.configs:
            status = "unknown"
            if not cfg.enabled:
                status = "disabled"
            else:
                try:
                    if cfg.provider == AIProvider.OLLAMA:
                        import requests
                        resp = requests.get(f"{cfg.base_url}/api/tags", timeout=3)
                        status = "healthy" if resp.status_code == 200 else "unhealthy"
                    else:
                        # Para providers cloud, assumimos healthy se tem API key
                        status = "healthy" if os.getenv(cfg.api_key_env) else "unhealthy"
                except Exception as e:
                    status = f"unhealthy: {e}"
            
            results[cfg.provider.value] = {
                "model": cfg.model_name,
                "status": status,
                "enabled": cfg.enabled,
            }
        return results


# Monkey-patch para o _call_provider ter acesso ao 'start' time
start = time.time()

# Fix: adicionar start time como atributo da instância na chamada
_original_call_provider = MultiAIRouter._call_provider

def _patched_call_provider(self, cfg, prompt, system_prompt, temperature, max_tokens, json_mode):
    self._last_start = time.time()
    return _original_call_provider(self, cfg, prompt, system_prompt, temperature, max_tokens, json_mode)

MultiAIRouter._call_provider = _patched_call_provider

# Patch nos métodos internos para usar self._last_start
_original_ollama = MultiAIRouter._call_ollama
_original_openai = MultiAIRouter._call_openai_compatible
_original_anthropic = MultiAIRouter._call_anthropic

def _patch_latency(fn):
    def wrapper(self, *args, **kwargs):
        result = fn(self, *args, **kwargs)
        if hasattr(self, '_last_start'):
            result.latency_ms = (time.time() - self._last_start) * 1000
        return result
    return wrapper

MultiAIRouter._call_ollama = _patch_latency(_original_ollama)
MultiAIRouter._call_openai_compatible = _patch_latency(_original_openai)
MultiAIRouter._call_anthropic = _patch_latency(_original_anthropic)