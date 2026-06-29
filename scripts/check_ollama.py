"""
Diagnostic script for Ollama - Verifica se tudo esta configurado corretamente
"""

import sys
import subprocess

def main():
    print("=" * 60)
    print("Diagnostico Ollama - AutoDeal IA Hunter")
    print("=" * 60)

    # 1. Verifica se Ollama esta instalado
    print("\n[1/5] Verificando instalacao do Ollama...")
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"  ✓ Ollama instalado: {result.stdout.strip()}")
        else:
            print("  ✗ Ollama nao encontrado")
            print("\n  SOLUCAO: Instale Ollama de https://ollama.com/download")
            return False
    except FileNotFoundError:
        print("  ✗ Comando 'ollama' nao encontrado no PATH")
        print("\n  SOLUCAO:")
        print("  1. Instale Ollama: https://ollama.com/download")
        print("  2. Reinicie o terminal/IDE apos a instalacao")
        return False
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

    # 2. Verifica se Ollama esta rodando
    print("\n[2/5] Verificando se Ollama esta rodando...")
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            print("  ✓ Ollama esta rodando!")
        else:
            print(f"  ✗ Ollama respondeu com erro: {resp.status_code}")
    except Exception as e:
        print(f"  ✗ Ollama nao esta rodando: {e}")
        print("\n  SOLUCAO: Inicie Ollama:")
        print("  - Clique no icone do Ollama no menu Iniciar")
        print("  - Ou execute: ollama serve")
        return False

    # 3. Lista modelos disponiveis
    print("\n[3/5] Verificando modelos disponiveis...")
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
        models = resp.json().get("models", [])

        if models:
            print(f"  ✓ {len(models)} modelo(s) encontrado(s):")
            for m in models:
                name = m.get('name', 'unknown')
                size = m.get('size', 0) / (1024**3)  # GB
                print(f"    - {name} ({size:.1f}GB)")

            # Verifica se tem modelo recomendado
            model_names = [m.get('name', '') for m in models]
            recommended = ['qwen2.5-coder', 'llama3.1', 'mistral', 'gemma2']
            has_recommended = any(r in ' '.join(model_names) for r in recommended)

            if has_recommended:
                print("\n  ✓ Pelo menos um modelo recomendado encontrado!")
            else:
                print("\n  ⚠ Nenhum modelo recomendado encontrado")
                print("\n  SOLUCAO: Baixe um modelo recomendado:")
                print("    ollama pull qwen2.5-coder:7b")
        else:
            print("  ✗ Nenhum modelo encontrado")
            print("\n  SOLUCAO: Baixe um modelo:")
            print("    ollama pull qwen2.5-coder:7b")
            return False
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

    # 4. Verifica conectividade com Python
    print("\n[4/5] Testando integracao Python...")
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
        models = resp.json().get("models", [])
        if models:
            first_model = models[0].get('name')
            print(f"  ✓ Python conectou a Ollama")
            print(f"  ✓ Modelo disponivel: {first_model}")
        else:
            print("  ✗ Nenhum modelo disponivel")
    except Exception as e:
        print(f"  ✗ Erro na integracao: {e}")
        return False

    # 5. Testa uma chamada simples
    print("\n[5/5] Testando chamada ao modelo...")
    try:
        import httpx
        import json

        # Pega o primeiro modelo
        resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
        models = resp.json().get("models", [])
        if not models:
            print("  ✗ Nenhum modelo para testar")
            return False

        model_name = models[0].get('name')

        # Testa geracao
        test_resp = httpx.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": model_name,
                "prompt": "Say hello in one word",
                "stream": False
            },
            timeout=30
        )

        if test_resp.status_code == 200:
            result = test_resp.json()
            response = result.get('response', '')
            print(f"  ✓ Modelo respondeu: '{response.strip()}'")
            print("\n" + "=" * 60)
            print("TUDO PRONTO! Ollama esta configurado corretamente!")
            print("=" * 60)
            print("\nExecute agora:")
            print("  .\\start.bat")
            print("  Escolha opcao 3 (Run scrapers)")
        else:
            print(f"  ✗ Modelo retornou erro: {test_resp.status_code}")
            return False

    except Exception as e:
        print(f"  ✗ Erro no teste: {e}")
        return False

    print("\n" + "=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n" + "=" * 60)
        print("DIAGNOSTICO INCOMPLETO")
        print("=" * 60)
        print("\nExecute primeiro:")
        print("  python setup_ollama.py")
        print("\nOu configure manualmente:")
        print("  1. Instale Ollama: https://ollama.com/download")
        print("  2. Inicie Ollama (clique no icone)")
        print("  3. Baixe um modelo: ollama pull qwen2.5-coder:7b")
        sys.exit(1)
    sys.exit(0)
