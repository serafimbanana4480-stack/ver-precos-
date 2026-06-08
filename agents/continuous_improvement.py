"""
Continuous Improvement Agent - Monitoriza o projeto em tempo real e sugere melhorias
"""
from __future__ import annotations
import time
import logging
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from .multi_ai_router import MultiAIRouter
from .orchestrator import AgentTask, AgentResult

logger = logging.getLogger(__name__)


@dataclass
class ImprovementSuggestion:
    id: str
    category: str  # performance, security, readability, architecture, testing
    file: Optional[str]
    line: Optional[int]
    description: str
    code_example: Optional[str]
    priority: int  # 1-10
    created_at: float = field(default_factory=lambda: time.time())
    applied: bool = False
    dismissed: bool = False


class ProjectWatcher(FileSystemEventHandler):
    """Watchdog handler para monitorizar alterações em ficheiros"""
    
    def __init__(self, callback: callable):
        self.callback = callback
        self._last_event = 0
        self._debounce_seconds = 2
    
    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".py"):
            now = time.time()
            if now - self._last_event > self._debounce_seconds:
                self._last_event = now
                self.callback(event.src_path)


class ContinuousImprovementAgent:
    """
    Agente de Melhoria Contínua que:
    1. Monitoriza alterações de ficheiros em tempo real
    2. Analisa código alterado com IA
    3. Mantém um backlog de sugestões priorizado
    4. Gera relatórios periódicos de saúde do projeto
    5. Alerta sobre regressões
    """
    
    def __init__(self, ai: MultiAIRouter, project_root: Path):
        self.ai = ai
        self.project_root = Path(project_root)
        self.suggestions: List[ImprovementSuggestion] = []
        self.suggestions_file = self.project_root / ".agents" / "suggestions.json"
        self.suggestions_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_suggestions()
        
        self._file_hashes: Dict[str, str] = {}
        self._observer: Optional[Observer] = None
        self._running = False
    
    def run(self, task: AgentTask) -> AgentResult:
        mode = task.context.get("mode", "batch")  # batch ou watch
        
        if mode == "watch":
            return self._run_watch_mode(task)
        else:
            return self._run_batch_analysis(task)
    
    def _run_batch_analysis(self, task: AgentTask) -> AgentResult:
        """Análise batch do projeto inteiro"""
        logger.info("[ImprovementAgent] Análise batch iniciada")
        
        # Analisar ficheiros recentemente modificados
        recent_files = self._get_recently_modified_files(hours=24)
        
        for fpath in recent_files[:10]:
            self._analyze_file(fpath)
        
        # Gerar relatório de saúde
        health_report = self._generate_health_report()
        
        # Salvar sugestões
        self._save_suggestions()
        
        top_suggestions = sorted(
            [s for s in self.suggestions if not s.applied and not s.dismissed],
            key=lambda x: x.priority,
            reverse=True,
        )[:20]
        
        return AgentResult(
            task_id=task.id,
            success=True,
            output=health_report,
            artifacts={
                "total_suggestions": len(self.suggestions),
                "pending_suggestions": len([s for s in self.suggestions if not s.applied and not s.dismissed]),
                "top_suggestions": [
                    {"id": s.id, "priority": s.priority, "category": s.category, "description": s.description}
                    for s in top_suggestions
                ],
            },
            suggestions=[s.description for s in top_suggestions[:10]],
            metrics={"files_analyzed": len(recent_files)},
        )
    
    def _run_watch_mode(self, task: AgentTask) -> AgentResult:
        """Inicia monitorização em tempo real (blocking)"""
        logger.info("[ImprovementAgent] Modo watch iniciado")
        
        self._running = True
        
        def on_file_changed(path: str):
            logger.info(f"[ImprovementAgent] Ficheiro alterado: {path}")
            self._analyze_file(Path(path))
            self._save_suggestions()
        
        handler = ProjectWatcher(on_file_changed)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.project_root), recursive=True)
        self._observer.start()
        
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self._observer.stop()
        
        self._observer.join()
        
        return AgentResult(
            task_id=task.id,
            success=True,
            output="Monitorização em tempo real terminada",
            metrics={"suggestions_generated": len(self.suggestions)},
        )
    
    def stop_watch(self) -> None:
        """Para o modo watch"""
        self._running = False
        if self._observer:
            self._observer.stop()
    
    def _analyze_file(self, path: Path) -> None:
        """Analisa um ficheiro individual com IA"""
        try:
            if ".venv" in str(path) or "__pycache__" in str(path):
                return
            if path.suffix != ".py":
                return
            
            content = path.read_text(encoding="utf-8")
            current_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Evitar re-analisar ficheiros iguais
            if str(path) in self._file_hashes and self._file_hashes[str(path)] == current_hash:
                return
            self._file_hashes[str(path)] = current_hash
            
            prompt = f"""Analise este ficheiro Python e sugira melhorias concretas:

Ficheiro: {path.name}

```python
{content[:3000]}
```

Responda APENAS com um JSON array no formato:
[{{"category": "performance|security|readability|architecture|testing", "description": "...", "priority": 1-10, "code_example": "..."}}]

Se não houver melhorias significativas, retorne []."""
            
            response = self.ai.generate(prompt, temperature=0.3, json_mode=True)
            if not response.success:
                return
            
            try:
                suggestions_data = json.loads(response.content)
                if not isinstance(suggestions_data, list):
                    return
                
                for item in suggestions_data:
                    if not isinstance(item, dict):
                        continue
                    suggestion = ImprovementSuggestion(
                        id=hashlib.md5(f"{path}:{item['description']}".encode()).hexdigest()[:12],
                        category=item.get("category", "general"),
                        file=str(path),
                        line=item.get("line"),
                        description=item["description"],
                        code_example=item.get("code_example"),
                        priority=min(10, max(1, int(item.get("priority", 5)))),
                    )
                    # Evitar duplicados
                    if not any(s.id == suggestion.id for s in self.suggestions):
                        self.suggestions.append(suggestion)
                        logger.info(f"[ImprovementAgent] Nova sugestão [{suggestion.priority}]: {suggestion.description[:80]}")
            except json.JSONDecodeError:
                logger.warning("[ImprovementAgent] Resposta IA não é JSON válido")
                
        except Exception as e:
            logger.warning(f"[ImprovementAgent] Erro ao analisar {path}: {e}")
    
    def _get_recently_modified_files(self, hours: int = 24) -> List[Path]:
        """Retorna ficheiros modificados nas últimas N horas"""
        cutoff = time.time() - (hours * 3600)
        files = []
        for f in self.project_root.rglob("*.py"):
            if ".venv" in str(f) or "__pycache__" in str(f):
                continue
            try:
                if f.stat().st_mtime > cutoff:
                    files.append(f)
            except Exception:
                continue
        return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def _generate_health_report(self) -> str:
        """Gera relatório de saúde do projeto"""
        lines = ["# Relatório de Saúde do Projeto", f"**Gerado:** {datetime.now(timezone.utc).isoformat()}", ""]
        
        # Estatísticas gerais
        py_files = [f for f in self.project_root.rglob("*.py") if ".venv" not in str(f) and "__pycache__" not in str(f)]
        total_lines = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in py_files)
        
        lines.append(f"- **Ficheiros Python:** {len(py_files)}")
        lines.append(f"- **Linhas de código:** {total_lines:,}")
        lines.append(f"- **Sugestões pendentes:** {len([s for s in self.suggestions if not s.applied and not s.dismissed])}")
        lines.append("")
        
        # Sugestões por categoria
        categories: Dict[str, List[ImprovementSuggestion]] = {}
        for s in self.suggestions:
            if not s.applied and not s.dismissed:
                categories.setdefault(s.category, []).append(s)
        
        if categories:
            lines.append("## Sugestões por Categoria")
            for cat, items in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
                lines.append(f"- **{cat.capitalize()}:** {len(items)} sugestões")
            lines.append("")
        
        # Top 10 sugestões
        top = sorted(
            [s for s in self.suggestions if not s.applied and not s.dismissed],
            key=lambda x: x.priority,
            reverse=True,
        )[:10]
        
        if top:
            lines.append("## Top 10 Sugestões Prioritárias")
            for s in top:
                lines.append(f"\n### [{s.priority}/10] {s.category.upper()}: {s.description[:100]}")
                if s.file:
                    lines.append(f"*Ficheiro:* `{s.file}`")
                if s.code_example:
                    lines.append(f"```python\n{s.code_example}\n```")
        
        return "\n".join(lines)
    
    def _load_suggestions(self) -> None:
        if self.suggestions_file.exists():
            try:
                data = json.loads(self.suggestions_file.read_text(encoding="utf-8"))
                self.suggestions = [ImprovementSuggestion(**item) for item in data]
            except Exception as e:
                logger.warning(f"[ImprovementAgent] Erro ao carregar sugestões: {e}")
    
    def _save_suggestions(self) -> None:
        try:
            data = [
                {
                    "id": s.id,
                    "category": s.category,
                    "file": s.file,
                    "line": s.line,
                    "description": s.description,
                    "code_example": s.code_example,
                    "priority": s.priority,
                    "created_at": s.created_at,
                    "applied": s.applied,
                    "dismissed": s.dismissed,
                }
                for s in self.suggestions
            ]
            self.suggestions_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[ImprovementAgent] Erro ao salvar sugestões: {e}")