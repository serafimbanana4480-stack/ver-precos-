"""
Project Generator Agent - Gera projetos completos do zero com estrutura profissional
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .multi_ai_router import MultiAIRouter
from .orchestrator import AgentTask, AgentResult

logger = logging.getLogger(__name__)


@dataclass
class ProjectBlueprint:
    name: str
    description: str
    language: str
    framework: Optional[str]
    features: List[str]
    structure: Dict[str, Any]


class ProjectGeneratorAgent:
    """
    Agente gerador de projetos que cria:
    - Estrutura de diretórios completa
    - Ficheiros de configuração
    - Código base (main, models, services)
    - Testes iniciais
    - Docker setup
    - CI/CD workflows
    - README profissional
    """
    
    def __init__(self, ai: MultiAIRouter):
        self.ai = ai
    
    def run(self, task: AgentTask) -> AgentResult:
        spec = task.context.get("specification", task.description)
        output_dir = Path(task.context.get("output_dir", "./generated_project"))
        
        logger.info(f"[ProjectGenerator] Gerando projeto: {spec[:80]}...")
        
        # 1. Gerar blueprint com IA
        blueprint = self._generate_blueprint(spec)
        
        # 2. Criar estrutura física
        self._create_structure(blueprint, output_dir)
        
        # 3. Gerar código base
        self._generate_code(blueprint, output_dir)
        
        # 4. Gerar configurações
        self._generate_configs(blueprint, output_dir)
        
        # 5. Gerar tests
        self._generate_tests(blueprint, output_dir)
        
        # 6. Gerar docs
        self._generate_docs(blueprint, output_dir)
        
        return AgentResult(
            task_id=task.id,
            success=True,
            output=f"Projeto '{blueprint.name}' gerado em {output_dir}",
            artifacts={
                "blueprint": {
                    "name": blueprint.name,
                    "language": blueprint.language,
                    "framework": blueprint.framework,
                    "features": blueprint.features,
                },
                "output_dir": str(output_dir),
                "files_created": self._count_files(output_dir),
            },
            suggestions=[
                f"Executar 'cd {output_dir} && python -m venv venv' para criar ambiente virtual",
                f"Instalar dependências: 'pip install -r requirements.txt'",
                f"Executar testes: 'pytest tests/'",
            ],
        )
    
    def _generate_blueprint(self, spec: str) -> ProjectBlueprint:
        """Usa IA para gerar o blueprint do projeto"""
        prompt = f"""Analise esta especificação e gere um blueprint técnico detalhado:

Especificação: {spec}

Responda em JSON:
{{
  "name": "nome-do-projeto",
  "description": "Descrição curta",
  "language": "python|typescript|rust|go",
  "framework": "fastapi|django|flask|nextjs|etc",
  "features": ["feature1", "feature2"],
  "structure": {{
    "dirs": ["src", "tests", "docs"],
    "files": ["README.md", "Dockerfile"]
  }}
}}

Seja específico e prático."""
        
        response = self.ai.generate(prompt, temperature=0.5, json_mode=True)
        
        if response.success:
            import json
            try:
                data = json.loads(response.content)
                return ProjectBlueprint(
                    name=data.get("name", "generated_project"),
                    description=data.get("description", ""),
                    language=data.get("language", "python"),
                    framework=data.get("framework"),
                    features=data.get("features", []),
                    structure=data.get("structure", {}),
                )
            except Exception as e:
                logger.warning(f"[ProjectGenerator] Erro ao parsear blueprint: {e}")
        
        # Fallback
        return ProjectBlueprint(
            name="generated_project",
            description=spec,
            language="python",
            framework="fastapi",
            features=["API REST", "Database", "Tests"],
            structure={"dirs": ["src", "tests", "docs"], "files": ["README.md"]},
        )
    
    def _create_structure(self, blueprint: ProjectBlueprint, root: Path) -> None:
        """Cria diretórios e ficheiros base"""
        root.mkdir(parents=True, exist_ok=True)
        
        for dirname in blueprint.structure.get("dirs", []):
            (root / dirname).mkdir(parents=True, exist_ok=True)
        
        for filename in blueprint.structure.get("files", []):
            fpath = root / filename
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.touch()
    
    def _generate_code(self, blueprint: ProjectBlueprint, root: Path) -> None:
        """Gera código base usando IA"""
        if blueprint.language.lower() == "python":
            self._generate_python_project(blueprint, root)
    
    def _generate_python_project(self, blueprint: ProjectBlueprint, root: Path) -> None:
        """Gera estrutura Python profissional"""
        src = root / "src"
        src.mkdir(exist_ok=True)
        
        # __init__.py
        (src / "__init__.py").write_text(f'"""{blueprint.description}"""\n__version__ = "0.1.0"\n')
        
        # main.py
        main_code = self._generate_with_ai(
            f"Gere um main.py em Python usando {blueprint.framework or 'FastAPI'} com:")
        (src / "main.py").write_text(main_code)
        
        # config.py
        config_code = """from pydantic_settings import BaseSettings\n\nclass Settings(BaseSettings):\n    app_name: str = \"App\"\n    debug: bool = False\n    \n    class Config:\n        env_file = \".env\"\n\nsettings = Settings()\n"""
        (src / "config.py").write_text(config_code)
        
        # models.py placeholder
        (src / "models.py").write_text("# SQLAlchemy models here\n")
        
        # requirements.txt
        reqs = ["pydantic>=2.0", "pydantic-settings>=2.0", "python-dotenv>=1.0"]
        if blueprint.framework and "fastapi" in blueprint.framework.lower():
            reqs.extend(["fastapi>=0.109", "uvicorn[standard]>=0.27"])
        elif blueprint.framework and "flask" in blueprint.framework.lower():
            reqs.extend(["flask>=3.0", "gunicorn>=21.0"])
        reqs.extend(["pytest>=8.0", "httpx>=0.26"])
        (root / "requirements.txt").write_text("\n".join(reqs))
    
    def _generate_configs(self, blueprint: ProjectBlueprint, root: Path) -> None:
        # .env.example
        (root / ".env.example").write_text("DEBUG=false\nDATABASE_URL=sqlite:///app.db\n")
        
        # .gitignore
        gitignore = "__pycache__/\n*.pyc\n.env\nvenv/\n.pytest_cache/\n"
        (root / ".gitignore").write_text(gitignore)
        
        # Dockerfile
        dockerfile = """FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY src/ ./src/\nCMD [\"python\", \"-m\", \"uvicorn\", \"src.main:app\", \"--host\", \"0.0.0.0\"]\n"""
        (root / "Dockerfile").write_text(dockerfile)
    
    def _generate_tests(self, blueprint: ProjectBlueprint, root: Path) -> None:
        tests = root / "tests"
        tests.mkdir(exist_ok=True)
        (tests / "__init__.py").touch()
        (tests / "test_main.py").write_text("""import pytest\n\ndef test_placeholder():\n    assert True\n""")
    
    def _generate_docs(self, blueprint: ProjectBlueprint, root: Path) -> None:
        readme = f"""# {blueprint.name}\n\n{blueprint.description}\n\n## Features\n"""
        for f in blueprint.features:
            readme += f"- {f}\n"
        readme += """\n## Quick Start\n\n```bash\npython -m venv venv\nsource venv/bin/activate  # Windows: venv\\Scripts\\activate\npip install -r requirements.txt\npython -m pytest tests/\n```\n"""
        (root / "README.md").write_text(readme)
    
    def _generate_with_ai(self, prompt: str) -> str:
        response = self.ai.generate(prompt, temperature=0.3)
        return response.content if response.success else "# TODO: Implementar\n"
    
    def _count_files(self, root: Path) -> int:
        return sum(1 for _ in root.rglob("*") if _.is_file())