"""
Test Runner Agent - Executa testes e analisa resultados
"""
from __future__ import annotations
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

from .orchestrator import AgentTask, AgentResult

logger = logging.getLogger(__name__)


class TestRunnerAgent:
    """
    Agente que:
    - Executa pytest e captura resultados
    - Analisa cobertura
    - Identifica testes flaky
    - Sugere testes em falta
    """
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
    
    def run(self, task: AgentTask) -> AgentResult:
        target = task.context.get("target", "tests/")
        coverage = task.context.get("coverage", True)
        
        logger.info(f"[TestRunner] A executar testes em {target}")
        
        result_data = self._run_pytest(target, coverage)
        suggestions = self._analyze_for_suggestions(result_data)
        
        success = result_data.get("exit_code", 1) == 0
        
        return AgentResult(
            task_id=task.id,
            success=success,
            output=self._format_report(result_data),
            artifacts=result_data,
            suggestions=suggestions,
            metrics={
                "tests_run": result_data.get("tests_run", 0),
                "tests_passed": result_data.get("tests_passed", 0),
                "tests_failed": result_data.get("tests_failed", 0),
                "coverage_pct": result_data.get("coverage_percent", 0),
            },
        )
    
    def _run_pytest(self, target: str, coverage: bool) -> Dict[str, Any]:
        """Executa pytest e parseia resultados"""
        cmd = ["python", "-m", "pytest", target, "-v", "--tb=short"]
        if coverage:
            cmd.extend(["--cov=.", "--cov-report=json", "--cov-report=term-missing"])
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return {"exit_code": 1, "error": "Timeout após 5 minutos", "tests_run": 0}
        except Exception as e:
            return {"exit_code": 1, "error": str(e), "tests_run": 0}
        
        # Parse output
        output = result.stdout + "\n" + result.stderr
        
        data = {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
        }
        
        # Extrair contagens do output
        for line in output.splitlines():
            if " passed" in line and "failed" in line:
                # Ex: "5 passed, 2 failed, 1 skipped"
                parts = line.split(",")
                for part in parts:
                    if "passed" in part:
                        data["tests_passed"] = int(part.strip().split()[0])
                    elif "failed" in part:
                        data["tests_failed"] = int(part.strip().split()[0])
                    elif "skipped" in part:
                        data["tests_skipped"] = int(part.strip().split()[0])
                    elif "error" in part:
                        data["tests_error"] = int(part.strip().split()[0])
                data["tests_run"] = data.get("tests_passed", 0) + data.get("tests_failed", 0) + data.get("tests_skipped", 0)
        
        # Ler coverage se existir
        cov_file = self.project_root / "coverage.json"
        if cov_file.exists():
            try:
                cov_data = json.loads(cov_file.read_text(encoding="utf-8"))
                totals = cov_data.get("totals", {})
                data["coverage_percent"] = round(totals.get("percent_covered", 0), 1)
                data["missing_lines"] = totals.get("missing_lines", 0)
            except Exception:
                data["coverage_percent"] = 0
        
        return data
    
    def _analyze_for_suggestions(self, data: Dict) -> List[str]:
        """Analisa resultados e sugere melhorias"""
        suggestions = []
        
        if data.get("tests_failed", 0) > 0:
            suggestions.append(f"Corrigir {data['tests_failed']} testes falhados")
        
        cov = data.get("coverage_percent", 0)
        if cov < 50:
            suggestions.append(f"Cobertura muito baixa ({cov}%). Adicionar mais testes unitários.")
        elif cov < 80:
            suggestions.append(f"Cobertura moderada ({cov}%). Alvo recomendado: 80%+.")
        
        if data.get("tests_skipped", 0) > 10:
            suggestions.append(f"{data['tests_skipped']} testes skipped. Revisar e reativar ou remover.")
        
        # Verificar módulos sem testes
        test_files = set(f.stem.replace("test_", "") for f in self.project_root.rglob("test_*.py"))
        source_files = [f.stem for f in self.project_root.rglob("*.py") 
                       if ".venv" not in str(f) and "__pycache__" not in str(f) 
                       and "test_" not in f.name and f.parent.name != "tests"]
        
        untested = [s for s in source_files if s not in test_files and s not in ("__init__", "conftest", "setup")]
        if len(untested) > 20:
            suggestions.append(f"{len(untested)} módulos sem ficheiros de teste correspondentes.")
        
        return suggestions
    
    def _format_report(self, data: Dict) -> str:
        lines = ["# Relatório de Testes", ""]
        lines.append(f"- **Exit Code:** {data.get('exit_code')}")
        lines.append(f"- **Passaram:** {data.get('tests_passed', 0)}")
        lines.append(f"- **Falharam:** {data.get('tests_failed', 0)}")
        lines.append(f"- **Skipped:** {data.get('tests_skipped', 0)}")
        lines.append(f"- **Cobertura:** {data.get('coverage_percent', 'N/A')}%")
        
        if data.get("tests_failed", 0) > 0:
            lines.append("\n## Falhas\n")
            lines.append("```")
            lines.append(data.get("stderr", "")[:2000])
            lines.append("```")
        
        return "\n".join(lines)