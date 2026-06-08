"""
Code Reviewer Agent - Revisa código Python procurando bugs, smells e oportunidades de melhoria
"""
from __future__ import annotations
import ast
import logging
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field

from .multi_ai_router import MultiAIRouter
from .orchestrator import AgentTask, AgentResult

logger = logging.getLogger(__name__)


@dataclass
class CodeIssue:
    file: str
    line: int
    severity: str  # critical, high, medium, low
    category: str  # security, performance, style, bug, architecture
    message: str
    suggestion: str


class CodeReviewerAgent:
    """
    Agente de revisão de código que combina análise estática (AST) com IA.
    """
    
    CRITICAL_PATTERNS = [
        ("f-string SQL", "execute(f\"SELECT", "critical", "security", "SQL Injection via f-string"),
        ("eval usage", "eval(", "critical", "security", "Uso de eval() é perigoso"),
        ("exec usage", "exec(", "critical", "security", "Uso de exec() é perigoso"),
        ("hardcoded secret", "password = ", "high", "security", "Possível secret hardcoded"),
        ("bare except", "except:", "high", "bug", "Except bare captura KeyboardInterrupt e SystemExit"),
        ("print debug", "print(", "low", "style", "Usar logging em vez de print"),
    ]
    
    def __init__(self, ai: MultiAIRouter):
        self.ai = ai
        self.issues: List[CodeIssue] = []
    
    def run(self, task: AgentTask) -> AgentResult:
        """Executa revisão de código no projeto"""
        target = task.context.get("target", ".")
        files = task.context.get("files", self._find_python_files(target))
        
        logger.info(f"[CodeReviewer] Analisando {len(files)} ficheiros em {target}")
        
        all_issues: List[CodeIssue] = []
        for fpath in files[:20]:  # Limitar a 20 ficheiros por execução
            issues = self._analyze_file(Path(fpath))
            all_issues.extend(issues)
        
        # Usar IA para análise semântica dos ficheiros mais críticos
        ai_suggestions = self._ai_review(files[:5])
        
        report = self._generate_report(all_issues, ai_suggestions)
        
        return AgentResult(
            task_id=task.id,
            success=True,
            output=report,
            artifacts={
                "issues_count": len(all_issues),
                "critical_count": sum(1 for i in all_issues if i.severity == "critical"),
                "high_count": sum(1 for i in all_issues if i.severity == "high"),
            },
            suggestions=[i.suggestion for i in all_issues if i.severity in ("critical", "high")],
            metrics={"files_analyzed": len(files), "issues_found": len(all_issues)},
        )
    
    def _find_python_files(self, target: str) -> List[str]:
        """Encontra todos os ficheiros Python no target"""
        root = Path(target)
        if root.is_file() and root.suffix == ".py":
            return [str(root)]
        return [str(f) for f in root.rglob("*.py") if ".venv" not in str(f) and "__pycache__" not in str(f)]
    
    def _analyze_file(self, path: Path) -> List[CodeIssue]:
        """Análise AST + pattern matching de um ficheiro"""
        issues = []
        try:
            source = path.read_text(encoding="utf-8")
            lines = source.splitlines()
        except Exception as e:
            return [CodeIssue(str(path), 0, "medium", "bug", f"Não foi possível ler: {e}", "Verificar encoding")]
        
        # Pattern matching simples
        for lineno, line in enumerate(lines, 1):
            for pattern_name, pattern, severity, category, message in self.CRITICAL_PATTERNS:
                if pattern in line:
                    # Evitar falsos positivos em comentários/docstrings
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    issues.append(CodeIssue(
                        file=str(path),
                        line=lineno,
                        severity=severity,
                        category=category,
                        message=f"{pattern_name}: {message}",
                        suggestion=f"Revisar linha {lineno}: {message}",
                    ))
        
        # Análise AST
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        if handler.type is None:
                            issues.append(CodeIssue(
                                file=str(path),
                                line=handler.lineno,
                                severity="high",
                                category="bug",
                                message="Except bare captura todas as exceções",
                                suggestion="Especificar exceções concretas (e.g., except Exception:)",
                            ))
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                        issues.append(CodeIssue(
                            file=str(path),
                            line=node.lineno,
                            severity="critical",
                            category="security",
                            message=f"Uso de {node.func.id}() detectado",
                            suggestion=f"Evitar {node.func.id}(). Usar ast.literal_eval ou json.loads",
                        ))
        except SyntaxError:
            pass
        
        return issues
    
    def _ai_review(self, files: List[str]) -> List[str]:
        """Usa IA para revisão semântica de código"""
        suggestions = []
        
        for fpath in files[:3]:  # Limitar para economizar tokens
            try:
                source = Path(fpath).read_text(encoding="utf-8")[:4000]  # Primeiros 4k chars
                prompt = f"""Analise este código Python e identifique:
1. Bugs potenciais
2. Problemas de performance
3. Violações de PEP8 graves
4. Problemas de segurança
5. Sugestões de refatoração

Código (primeiras 100 linhas):
```python
{source}
```

Responda em português de Portugal com bullets concisos."""
                
                response = self.ai.generate(prompt, temperature=0.3)
                if response.success:
                    suggestions.append(f"=== {fpath} ===\n{response.content}")
            except Exception as e:
                logger.warning(f"[CodeReviewer] Falha na análise IA de {fpath}: {e}")
        
        return suggestions
    
    def _generate_report(self, issues: List[CodeIssue], ai_suggestions: List[str]) -> str:
        """Gera relatório formatado"""
        lines = ["# Relatório de Revisão de Código", ""]
        
        if issues:
            lines.append(f"## Issues Encontradas: {len(issues)}")
            for sev in ["critical", "high", "medium", "low"]:
                sev_issues = [i for i in issues if i.severity == sev]
                if sev_issues:
                    lines.append(f"\n### {sev.upper()} ({len(sev_issues)})")
                    for i in sev_issues[:10]:  # Limitar por severidade
                        lines.append(f"- `{i.file}:{i.line}` — {i.message}")
        else:
            lines.append("Nenhum issue crítico encontrado na análise estática.")
        
        if ai_suggestions:
            lines.append("\n## Análise Semântica (IA)\n")
            lines.extend(ai_suggestions)
        
        return "\n".join(lines)