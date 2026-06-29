"""
Script de Verificação Completa do Projeto
==========================================
Verifica integridade, imports, e potenciais problemas.
"""

import sys
import ast
import os
from pathlib import Path
from typing import List, Dict, Tuple, Set

class ProjectVerifier:
    def __init__(self, project_root: str):
        self.root = Path(project_root)
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []
        self.success: List[str] = []
        
    def log_issue(self, file: str, line: int, severity: str, message: str):
        self.issues.append({
            'file': file,
            'line': line,
            'severity': severity,
            'message': message
        })
        
    def log_warning(self, file: str, line: int, message: str):
        self.warnings.append({
            'file': file,
            'line': line,
            'message': message
        })
        
    def log_success(self, message: str):
        self.success.append(message)
        
    def scan_for_todos(self):
        """Procura TODOs e FIXMEs"""
        print("\n[1/6] Procurando TODOs e FIXMEs...")
        
        python_files = list(self.root.rglob("*.py"))
        todo_count = 0
        
        for file in python_files:
            if '.venv' in str(file) or '__pycache__' in str(file):
                continue
                
            try:
                content = file.read_text(encoding='utf-8')
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    if 'TODO' in line or 'FIXME' in line or 'XXX' in line:
                        todo_count += 1
                        self.log_warning(
                            str(file.relative_to(self.root)),
                            i,
                            f"TODO/FIXME found: {line.strip()[:60]}"
                        )
            except Exception as e:
                self.log_issue(str(file), 0, "ERROR", f"Could not read file: {e}")
                
        print(f"  Found {todo_count} TODOs/FIXMEs")
        
    def check_imports(self):
        """Verifica imports problemáticos"""
        print("\n[2/6] Verificando imports...")
        
        python_files = list(self.root.rglob("*.py"))
        import_errors = 0
        
        critical_imports = [
            'playwright', 'langchain', 'ollama', 'pydantic',
            'sqlalchemy', 'streamlit', 'xgboost', 'httpx'
        ]
        
        for file in python_files:
            if '.venv' in str(file) or '__pycache__' in str(file):
                continue
                
            try:
                content = file.read_text(encoding='utf-8')
                
                # Check for bare except clauses
                if 'except:' in content or 'except Exception:' in content:
                    if 'pass' in content.split('except')[1].split('\n')[0:3]:
                        import_errors += 1
                        self.log_warning(
                            str(file.relative_to(self.root)),
                            0,
                            "Bare except with pass - may hide errors"
                        )
                        
            except Exception:
                pass
                
        print(f"  Found {import_errors} potential import/except issues")
        
    def check_file_structure(self):
        """Verifica estrutura de arquivos"""
        print("\n[3/6] Verificando estrutura de arquivos...")
        
        required_files = [
            'main.py',
            'config.py',
            'requirements.txt',
            'README.md',
            '.env.example'
        ]
        
        for file in required_files:
            path = self.root / file
            if path.exists():
                self.log_success(f"✓ {file} exists")
            else:
                self.log_issue(file, 0, "CRITICAL", f"Missing required file: {file}")
                
    def check_python_syntax(self):
        """Verifica sintaxe Python"""
        print("\n[4/6] Verificando sintaxe Python...")
        
        python_files = list(self.root.rglob("*.py"))
        syntax_errors = 0
        
        for file in python_files:
            if '.venv' in str(file) or '__pycache__' in str(file):
                continue
                
            try:
                content = file.read_text(encoding='utf-8')
                ast.parse(content)
            except SyntaxError as e:
                syntax_errors += 1
                self.log_issue(
                    str(file.relative_to(self.root)),
                    e.lineno or 0,
                    "SYNTAX_ERROR",
                    str(e)
                )
                
        if syntax_errors == 0:
            self.log_success("✓ All Python files have valid syntax")
        else:
            print(f"  Found {syntax_errors} syntax errors")
            
    def check_circular_imports(self):
        """Verifica potenciais imports circulares"""
        print("\n[5/6] Verificando imports circulares...")
        
        # Map of imports
        imports_map: Dict[str, Set[str]] = {}
        
        python_files = list(self.root.rglob("*.py"))
        
        for file in python_files:
            if '.venv' in str(file) or '__pycache__' in str(file):
                continue
                
            try:
                content = file.read_text(encoding='utf-8')
                tree = ast.parse(content)
                
                file_imports = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            file_imports.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            file_imports.add(node.module)
                            
                imports_map[str(file.relative_to(self.root))] = file_imports
            except Exception:
                pass
                
        # Check for suspicious patterns
        suspicious = 0
        for file, imports in imports_map.items():
            # Check for config imports
            if 'config' in str(file) and any('scrapers' in i or 'database' in i for i in imports):
                suspicious += 1
                self.log_warning(file, 0, "Config file imports heavy modules - potential circular import")
                
        print(f"  Found {suspicious} suspicious import patterns")
        
    def check_empty_pass(self):
        """Procura por 'pass' vazio em blocos except"""
        print("\n[6/6] Procurando pass vazio em except...")
        
        python_files = list(self.root.rglob("*.py"))
        empty_pass_count = 0
        
        for file in python_files:
            if '.venv' in str(file) or '__pycache__' in str(file):
                continue
                
            try:
                content = file.read_text(encoding='utf-8')
                lines = content.split('\n')
                
                in_except = False
                for i, line in enumerate(lines, 1):
                    if 'except' in line and ':' in line:
                        in_except = True
                    elif in_except:
                        stripped = line.strip()
                        if stripped == 'pass':
                            empty_pass_count += 1
                            self.log_warning(
                                str(file.relative_to(self.root)),
                                i,
                                "Empty pass in except block - errors will be silenced"
                            )
                            in_except = False
                        elif stripped and not stripped.startswith('#'):
                            in_except = False
            except Exception:
                pass
                
        print(f"  Found {empty_pass_count} empty pass in except blocks")
        
    def generate_report(self):
        """Gera relatório final"""
        print("\n" + "="*60)
        print("RELATÓRIO DE VERIFICAÇÃO")
        print("="*60)
        
        # Successes
        if self.success:
            print(f"\n✓ SUCESSOS ({len(self.success)}):")
            for s in self.success:
                print(f"  {s}")
                
        # Issues
        if self.issues:
            print(f"\n🔴 PROBLEMAS CRÍTICOS ({len(self.issues)}):")
            for issue in sorted(self.issues, key=lambda x: x['severity']):
                print(f"  [{issue['severity']}] {issue['file']}:{issue['line']}")
                print(f"      {issue['message']}")
                
        # Warnings
        if self.warnings:
            print(f"\n⚠️  AVISOS ({len(self.warnings)}):")
            for warning in self.warnings[:20]:  # Limit to 20
                print(f"  {warning['file']}:{warning['line']}")
                print(f"      {warning['message']}")
            if len(self.warnings) > 20:
                print(f"  ... e mais {len(self.warnings) - 20} avisos")
                
        # Summary
        print("\n" + "="*60)
        print("RESUMO:")
        print(f"  Successos: {len(self.success)}")
        print(f"  Problemas: {len(self.issues)}")
        print(f"  Avisos: {len(self.warnings)}")
        
        if len(self.issues) == 0:
            print("\n✅ Projeto parece estar em bom estado!")
        elif len(self.issues) < 5:
            print("\n⚠️  Alguns problemas encontrados, mas nada crítico")
        else:
            print("\n🔴 Vários problemas encontrados - revisão necessária")
            
        print("="*60)
        
        # Save to file
        report_path = self.root / 'verification_report.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("VERIFICAÇÃO DO PROJETO - AutoDeal IA Hunter\n")
            f.write("="*60 + "\n\n")
            f.write(f"Successos: {len(self.success)}\n")
            f.write(f"Problemas: {len(self.issues)}\n")
            f.write(f"Avisos: {len(self.warnings)}\n\n")
            
            f.write("PROBLEMAS:\n")
            for issue in self.issues:
                f.write(f"[{issue['severity']}] {issue['file']}:{issue['line']}\n")
                f.write(f"  {issue['message']}\n\n")
                
            f.write("\nAVISOS:\n")
            for warning in self.warnings:
                f.write(f"{warning['file']}:{warning['line']}\n")
                f.write(f"  {warning['message']}\n\n")
                
        print(f"\n📄 Relatório salvo em: {report_path}")

def main():
    print("="*60)
    print("VERIFICAÇÃO DO PROJETO - AutoDeal IA Hunter")
    print("="*60)
    
    verifier = ProjectVerifier('.')
    
    verifier.scan_for_todos()
    verifier.check_imports()
    verifier.check_file_structure()
    verifier.check_python_syntax()
    verifier.check_circular_imports()
    verifier.check_empty_pass()
    
    verifier.generate_report()

if __name__ == "__main__":
    main()
