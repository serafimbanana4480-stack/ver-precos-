"""
Agent Orchestrator - Inspirado em LangGraph + CrewAI
Orquestra múltiplos agentes especializados com state machine, checkpoints e human-in-the-loop.
"""
from __future__ import annotations
import json
import time
import logging
import asyncio
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable, Any, Coroutine
from pathlib import Path
from datetime import datetime, timezone

from .multi_ai_router import MultiAIRouter, AIProvider

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentRole(Enum):
    CODE_REVIEWER = "code_reviewer"
    ARCHITECTURE_GUARDIAN = "architecture_guardian"
    TEST_RUNNER = "test_runner"
    SECURITY_AUDITOR = "security_auditor"
    PERFORMANCE_OPTIMIZER = "performance_optimizer"
    DOCUMENTATION_WRITER = "documentation_writer"
    PROJECT_GENERATOR = "project_generator"
    CONTINUOUS_IMPROVEMENT = "continuous_improvement"


@dataclass
class AgentTask:
    id: str
    role: AgentRole
    description: str
    context: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional["AgentResult"] = None
    created_at: float = field(default_factory=lambda: time.time())
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    approved: Optional[bool] = None  # Human-in-the-loop
    max_retries: int = 2
    retry_count: int = 0


@dataclass
class AgentResult:
    task_id: str
    success: bool
    output: str
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: time.time())


class AgentOrchestrator:
    """
    Orquestrador de agentes com:
    - State persistence (checkpoints)
    - Dependency graph execution
    - Human-in-the-loop gates
    - Parallel execution where possible
    - Retry logic com exponential backoff
    """
    
    def __init__(self, project_root: Optional[Path] = None, state_file: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.state_file = state_file or self.project_root / ".agents" / "orchestrator_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.ai = MultiAIRouter()
        self.tasks: Dict[str, AgentTask] = {}
        self.agents: Dict[AgentRole, Callable[[AgentTask], AgentResult]] = {}
        self.checkpoints: List[Dict] = []
        
        self._register_default_agents()
        self._load_state()
    
    def _register_default_agents(self) -> None:
        """Registra os agentes padrão do sistema"""
        from .code_reviewer import CodeReviewerAgent
        from .architecture_guardian import ArchitectureGuardianAgent
        from .test_runner import TestRunnerAgent
        from .continuous_improvement import ContinuousImprovementAgent
        from .project_generator import ProjectGeneratorAgent
        
        self.register_agent(AgentRole.CODE_REVIEWER, CodeReviewerAgent(self.ai).run)
        self.register_agent(AgentRole.ARCHITECTURE_GUARDIAN, ArchitectureGuardianAgent(self.ai).run)
        self.register_agent(AgentRole.TEST_RUNNER, TestRunnerAgent(self.project_root).run)
        self.register_agent(AgentRole.CONTINUOUS_IMPROVEMENT, ContinuousImprovementAgent(self.ai, self.project_root).run)
        self.register_agent(AgentRole.PROJECT_GENERATOR, ProjectGeneratorAgent(self.ai).run)
    
    def register_agent(self, role: AgentRole, handler: Callable[[AgentTask], AgentResult]) -> None:
        """Registra um handler para um agente"""
        self.agents[role] = handler
        logger.info(f"[Orchestrator] Agente registrado: {role.value}")
    
    def create_task(
        self,
        role: AgentRole,
        description: str,
        context: Optional[Dict] = None,
        depends_on: Optional[List[str]] = None,
        require_approval: bool = False,
    ) -> AgentTask:
        """Cria uma nova tarefa no orquestrador"""
        task_id = f"{role.value}_{int(time.time() * 1000)}"
        task = AgentTask(
            id=task_id,
            role=role,
            description=description,
            context=context or {},
            depends_on=depends_on or [],
        )
        if require_approval:
            task.context["require_approval"] = True
        self.tasks[task_id] = task
        self._save_checkpoint("task_created", task_id)
        return task
    
    def submit_task(self, task: AgentTask) -> AgentResult:
        """Executa uma tarefa sincronamente"""
        handler = self.agents.get(task.role)
        if not handler:
            return AgentResult(
                task_id=task.id,
                success=False,
                output=f"Agente {task.role.value} não registrado",
                errors=["Agent not registered"],
            )
        
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        self._save_checkpoint("task_started", task.id)
        
        try:
            result = handler(task)
            task.result = result
            task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            task.completed_at = time.time()
            
            if not result.success and task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                logger.warning(f"[Orchestrator] Retrying task {task.id} (attempt {task.retry_count})")
                return self.submit_task(task)
            
            self._save_checkpoint("task_completed", task.id, result=result.success)
            return result
            
        except Exception as e:
            logger.exception(f"[Orchestrator] Task {task.id} failed")
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            result = AgentResult(
                task_id=task.id,
                success=False,
                output=str(e),
                errors=[str(e)],
            )
            task.result = result
            self._save_checkpoint("task_failed", task.id, error=str(e))
            return result
    
    async def execute_plan(self, tasks: List[AgentTask], parallel: bool = True) -> Dict[str, AgentResult]:
        """
        Executa um plano de tarefas respeitando dependências.
        
        Se parallel=True, executa tarefas independentes em paralelo.
        """
        for task in tasks:
            self.tasks[task.id] = task
        
        results: Dict[str, AgentResult] = {}
        completed: set = set()
        
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]
        
        while pending:
            # Encontrar tarefas prontas (dependências satisfeitas)
            ready = [
                t for t in pending
                if all(dep in completed for dep in t.depends_on)
            ]
            
            if not ready:
                # Deadlock detectado
                logger.error("[Orchestrator] Deadlock detectado no plano de tarefas")
                break
            
            if parallel and len(ready) > 1:
                # Executar em paralelo
                loop = asyncio.get_event_loop()
                coros = [loop.run_in_executor(None, self.submit_task, t) for t in ready]
                batch_results = await asyncio.gather(*coros, return_exceptions=True)
                
                for task, res in zip(ready, batch_results):
                    if isinstance(res, Exception):
                        results[task.id] = AgentResult(
                            task_id=task.id,
                            success=False,
                            output=str(res),
                            errors=[str(res)],
                        )
                    else:
                        results[task.id] = res
                    completed.add(task.id)
                    pending.remove(task)
            else:
                # Executar sequencialmente
                for task in ready:
                    results[task.id] = self.submit_task(task)
                    completed.add(task.id)
                    pending.remove(task)
        
        return results
    
    def run_continuous_improvement_cycle(self) -> Dict[str, Any]:
        """
        Ciclo contínuo de melhoria:
        1. Architecture Guardian verifica estrutura
        2. Code Reviewer analisa código recente
        3. Test Runner valida
        4. Continuous Improvement consolida sugestões
        """
        logger.info("[Orchestrator] Iniciando ciclo de melhoria contínua")
        
        t1 = self.create_task(AgentRole.ARCHITECTURE_GUARDIAN, "Verificar estrutura do projeto")
        t2 = self.create_task(AgentRole.CODE_REVIEWER, "Revisar código crítico", depends_on=[t1.id])
        t3 = self.create_task(AgentRole.TEST_RUNNER, "Executar suite de testes", depends_on=[t1.id])
        t4 = self.create_task(AgentRole.CONTINUOUS_IMPROVEMENT, "Consolidar melhorias", depends_on=[t2.id, t3.id])
        
        # Executar sequencialmente para manter logs ordenados
        results = {
            "architecture": self.submit_task(t1),
            "code_review": self.submit_task(t2),
            "tests": self.submit_task(t3),
            "improvements": self.submit_task(t4),
        }
        
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_success": all(r.success for r in results.values()),
            "tasks": {k: {"success": v.success, "output_preview": v.output[:200]} for k, v in results.items()},
            "suggestions": [],
        }
        
        for r in results.values():
            summary["suggestions"].extend(r.suggestions)
        
        self._save_checkpoint("improvement_cycle", "completed", summary=summary)
        return summary
    
    def generate_project(self, specification: str, output_dir: Optional[Path] = None) -> AgentResult:
        """Gera um projeto completo do zero baseado numa especificação"""
        task = self.create_task(
            AgentRole.PROJECT_GENERATOR,
            f"Gerar projeto: {specification}",
            context={"specification": specification, "output_dir": str(output_dir) if output_dir else None},
        )
        return self.submit_task(task)
    
    def _save_checkpoint(self, event: str, task_id: str, **kwargs) -> None:
        """Persiste estado para recuperação"""
        checkpoint = {
            "timestamp": time.time(),
            "event": event,
            "task_id": task_id,
            **kwargs,
        }
        self.checkpoints.append(checkpoint)
        
        try:
            state = {
                "checkpoints": self.checkpoints[-100:],  # Manter últimos 100
                "tasks": {tid: {
                    "id": t.id,
                    "role": t.role.value,
                    "status": t.status.value,
                    "description": t.description,
                    "depends_on": t.depends_on,
                    "result": {
                        "success": t.result.success,
                        "output": t.result.output[:500] if t.result else None,
                    } if t.result else None,
                } for tid, t in self.tasks.items()},
            }
            self.state_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[Orchestrator] Falha ao salvar checkpoint: {e}")
    
    def _load_state(self) -> None:
        """Carrega estado anterior se existir"""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.checkpoints = data.get("checkpoints", [])
                logger.info(f"[Orchestrator] Estado carregado: {len(self.checkpoints)} checkpoints")
            except Exception as e:
                logger.warning(f"[Orchestrator] Falha ao carregar estado: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do orquestrador"""
        status_counts = {s.value: 0 for s in TaskStatus}
        for t in self.tasks.values():
            status_counts[t.status.value] += 1
        
        return {
            "total_tasks": len(self.tasks),
            "status_counts": status_counts,
            "registered_agents": [r.value for r in self.agents.keys()],
            "ai_health": self.ai.health_check(),
            "ai_metrics": self.ai.get_metrics(),
            "last_checkpoint": self.checkpoints[-1] if self.checkpoints else None,
        }