"""
Architecture Guardian - Valida a arquitetura do projeto, dependências e estrutura
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Set
from dataclasses import dataclass

from .multi_ai_router import MultiAIRouter
from .orchestrator import AgentTask, AgentResult

logger = logging.getLogger(__name__)


@dataclass
class ArchitectureRule:
    name: str
    description: str
    check: callable
    severity: str


class ArchitectureGuardianAgent:
    """
    Guardião da arquitetura que verifica:
    - Circular dependencies
    - Camadas corretas (não violar boundaries)
    - Ficheiros órfãos
    - Configurações inconsistentes
    - Tamanho de módulos
    """
    
    MAX_MODULE_LINES = 1000
    MAX_FUNCTION_LINES = 100
    
    def __init__(self, ai: MultiAIRouter):
        self.ai = ai
        self.violations: List[Dict] = []
    
    def run(self, task: AgentTask) -> AgentResult:
        target = Path(task.context.get("target", "."))
        
        checks = [
            self._check_circular_imports,
            self._check_layer_violations,
            self._check_orphan_files,
            self._check_module_size,
            self._check_config_consistency,
        ]
        
        for check in checks:
            try:
                check(target)
            except Exception as e:
                logger.warning(f"[ArchGuardian] Check falhou: {e}")
        
        # Análise IA da arquitetura
        ai_analysis = self._ai_architecture_review(target)
        
        report = self._generate_report(ai_analysis)
        
        return AgentResult(
            task_id=task.id,
            success=len([v for v in self.violations if v["severity"] == "critical"]) == 0,
            output=report,
            artifacts={"violations": self.violations},
            suggestions=[v["message"] for v in self.violations],
            metrics={"violations_count": len(self.violations)},
        )
    
    def _check_circular_imports(self, root: Path) -> None:
        """Deteta imports circulares simples"""
        imports: Dict[str, Set[str]] = {}
        
        for pyfile in root.rglob("*.py"):
            if ".venv" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            try:
                content = pyfile.read_text(encoding="utf-8")
                module_name = str(pyfile.relative_to(root)).replace("\\", ".").replace("/", ".")[:-3]
                imports[module_name] = set()
                for line in content.splitlines():
                    if line.strip().startswith(("from ", "import ")):
                        imports[module_name].add(line.strip())
            except Exception:
                continue
        
        # Simplificado: apenas reportar módulos com muitos imports cruzados
        cross_imports = 0
        for mod, imp in imports.items():
            for other_mod in imports:
                if mod != other_mod:
                    if any(other_mod in i for i in imp):
                        cross_imports += 1
        
        if cross_imports > 50:
            self.violations.append({
                "severity": "medium",
                "category": "architecture",
                "message": f"Alta densidade de imports cruzados ({cross_imports}). Verificar acoplamento.",
            })
    
    def _check_layer_violations(self, root: Path) -> None:
        """Verifica se camadas respeitam boundaries"""
        # scrapers não devem importar dashboard diretamente
        for pyfile in root.rglob("scrapers/*.py"):
            try:
                content = pyfile.read_text(encoding="utf-8")
                if "from dashboard" in content or "import dashboard" in content:
                    self.violations.append({
                        "severity": "high",
                        "category": "architecture",
                        "message": f"Scraper {pyfile.name} importa dashboard (violação de camada)",
                    })
            except Exception:
                continue
        
        # database não deve importar scrapers
        for pyfile in root.rglob("database/*.py"):
            try:
                content = pyfile.read_text(encoding="utf-8")
                if "from scrapers" in content or "import scrapers" in content:
                    self.violations.append({
                        "severity": "high",
                        "category": "architecture",
                        "message": f"Database {pyfile.name} importa scrapers (violação de camada)",
                    })
            except Exception:
                continue
    
    def _check_orphan_files(self, root: Path) -> None:
        """Encontra ficheiros Python não importados por ninguém"""
        all_files = [f for f in root.rglob("*.py") if ".venv" not in str(f) and "__pycache__" not in str(f)]
        referenced = set()
        
        for pyfile in all_files:
            try:
                content = pyfile.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if "from " in line or "import " in line:
                        for other in all_files:
                            name = other.stem
                            if name in line and other != pyfile:
                                referenced.add(str(other))
            except Exception:
                continue
        
        orphans = [str(f) for f in all_files if str(f) not in referenced and f.stem not in ("__init__", "conftest")]
        if len(orphans) > 10:
            self.violations.append({
                "severity": "low",
                "category": "architecture",
                "message": f"{len(orphans)} ficheiros podem estar órfãos (não importados). Verificar dead code.",
            })
    
    def _check_module_size(self, root: Path) -> None:
        """Verifica módulos muito grandes"""
        for pyfile in root.rglob("*.py"):
            if ".venv" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            try:
                lines = len(pyfile.read_text(encoding="utf-8").splitlines())
                if lines > self.MAX_MODULE_LINES:
                    self.violations.append({
                        "severity": "medium",
                        "category": "architecture",
                        "message": f"Módulo {pyfile.name} tem {lines} linhas (limite: {self.MAX_MODULE_LINES})",
                    })
            except Exception:
                continue
    
    def _check_config_consistency(self, root: Path) -> None:
        """Verifica consistência entre config.py e .env.example"""
        env_example = root / ".env.example"
        config_file = root / "config.py"
        
        if env_example.exists() and config_file.exists():
            env_vars = set()
            for line in env_example.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    env_vars.add(line.split("=")[0].strip())
            
            config_text = config_file.read_text(encoding="utf-8")
            missing = [v for v in env_vars if v.lower() not in config_text.lower()]
            
            if missing:
                self.violations.append({
                    "severity": "medium",
                    "category": "config",
                    "message": f"Variáveis do .env.example não presentes em config.py: {missing[:5]}",
                })
    
    def _ai_architecture_review(self, root: Path) -> str:
        """Usa IA para análise arquitetural de alto nível"""
        try:
            # Ler ficheiros-chave
            files_to_read = ["main.py", "config.py", "README.md"]
            context = ""
            for fname in files_to_read:
                fpath = root / fname
                if fpath.exists():
                    content = fpath.read_text(encoding="utf-8")[:2000]
                    context += f"\n=== {fname} ===\n{content}\n"
            
            prompt = f"""Analise a arquitetura deste projeto Python e identifique problemas estruturais:

{context}

Responda com:
1. Forças da arquitetura atual
2. Fraquezas críticas
3. Sugestões de refatoração
4. Padrões de design recomendados

Seja conciso e acionável."""
            
            response = self.ai.generate(prompt, temperature=0.4)
            return response.content if response.success else "Análise IA indisponível"
        except Exception as e:
            return f"Erro na análise IA: {e}"
    
    def _generate_report(self, ai_analysis: str) -> str:
        lines = ["# Relatório do Architecture Guardian", ""]
        
        if self.violations:
            lines.append(f"## Violações Encontradas: {len(self.violations)}")
            for sev in ["critical", "high", "medium", "low"]:
                sev_v = [v for v in self.violations if v["severity"] == sev]
                if sev_v:
                    lines.append(f"\n### {sev.upper()} ({len(sev_v)})")
                    for v in sev_v:
                        lines.append(f"- [{v['category']}] {v['message']}")
        else:
            lines.append("Nenhuma violação arquitetural encontrada.")
        
        lines.append("\n## Análise Arquitetural (IA)\n")
        lines.append(ai_analysis)
        
        return "\n".join(lines)