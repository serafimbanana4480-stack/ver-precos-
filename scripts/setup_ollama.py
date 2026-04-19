"""
Setup script for 100% FREE AutoDeal IA Hunter with Ollama
==========================================================

Este script configura o sistema para funcionar 100% gratuito
usando Ollama (IA local) sem necessidade de APIs pagas.

Requisitos:
1. Ollama instalado (https://ollama.com)
2. Pelo menos 8GB RAM livre
3. 10GB espaço em disco para modelos

Modelos recomendados (em ordem de preferencia):
- qwen2.5-coder:7b (melhor para scraping, ~4.5GB)
- llama3.1:8b (bom equilibrio, ~4.7GB)
- mistral:7b (rapido, ~4.1GB)
- gemma2:9b (bom para extracao, ~5.4GB)
"""

import subprocess
import sys
import time
import os

def check_ollama_installed():
    """Verifica se Ollama esta instalado"""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"✓ Ollama instalado: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False

def check_ollama_running():
    """Verifica se Ollama esta rodando"""
    import httpx
    try:
        resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            print(f"✓ Ollama rodando com {len(models)} modelo(s)")
            for m in models:
                print(f"  - {m.get('name', 'unknown')}")
            return True
    except Exception as e:
        print(f"✗ Ollama nao esta rodando: {e}")
    return False

def start_ollama():
    """Tenta iniciar Ollama"""
    print("\n→ Tentando iniciar Ollama...")
    try:
        # Tenta iniciar ollama (vai rodar em background)
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        time.sleep(3)  # Aguarda iniciar
        return check_ollama_running()
    except Exception as e:
        print(f"✗ Falha ao iniciar Ollama: {e}")
        return False

def pull_model(model_name):
    """Baixa um modelo do Ollama"""
    print(f"\n→ Baixando modelo {model_name} (pode demorar alguns minutos)...")
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos timeout
        )
        if result.returncode == 0:
            print(f"✓ Modelo {model_name} baixado com sucesso!")
            return True
        else:
            print(f"✗ Erro ao baixar modelo: {result.stderr}")
    except subprocess.TimeoutExpired:
        print(f"✗ Timeout ao baixar modelo. Tente manualmente: ollama pull {model_name}")
    except Exception as e:
        print(f"✗ Erro: {e}")
    return False

def main():
    print("=" * 60)
    print("Setup AutoDeal IA Hunter - Modo 100% Gratuito (Ollama)")
    print("=" * 60)

    # Verifica instalacao
    if not check_ollama_installed():
        print("\n✗ Ollama nao esta instalado!")
        print("\nPara instalar Ollama:")
        print("1. Acesse: https://ollama.com/download")
        print("2. Baixe e instale para Windows")
        print("3. Reinicie este script apos a instalacao")
        print("\nOu instale via wingot:")
        print("  winget install Ollama.Ollama")
        sys.exit(1)

    # Verifica se esta rodando
    if not check_ollama_running():
        print("\n→ Ollama esta instalado mas nao rodando.")
        if not start_ollama():
            print("\n✗ Nao foi possivel iniciar Ollama automaticamente.")
            print("Por favor, inicie manualmente:")
            print("  1. Abra o menu Iniciar")
            print("  2. Execute 'Ollama'")
            print("  3. Aguarde o icone aparecer na bandeja")
            print("  4. Execute este script novamente")
            sys.exit(1)

    # Lista modelos disponiveis
    print("\n" + "=" * 60)
    print("Verificando modelos disponiveis...")
    print("=" * 60)

    import httpx
    resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
    models = resp.json().get("models", [])
    model_names = [m.get("name", "") for m in models]

    # Modelos recomendados em ordem
    recommended = [
        ("qwen2.5-coder:7b", "Melhor para scraping (4.5GB)"),
        ("llama3.1:8b", "Bom equilibrio (4.7GB)"),
        ("mistral:7b", "Rapido (4.1GB)"),
        ("gemma2:9b", "Bom para extracao (5.4GB)"),
    ]

    has_model = False
    for model, desc in recommended:
        if any(model in m for m in model_names):
            print(f"✓ Modelo recomendado encontrado: {model} ({desc})")
            has_model = True
            break

    if not has_model:
        print("\n✗ Nenhum modelo recomendado encontrado!")
        print("\nDeseja baixar um modelo agora?")
        print("\nOpcoes:")
        for i, (model, desc) in enumerate(recommended, 1):
            print(f"  {i}. {model} - {desc}")
        print("  0. Pular (configurar manualmente depois)")

        try:
            choice = input("\nEscolha (0-4): ").strip()
            if choice in ["1", "2", "3", "4"]:
                model_idx = int(choice) - 1
                model_to_pull = recommended[model_idx][0]
                if pull_model(model_to_pull):
                    print(f"\n✓ Modelo {model_to_pull} pronto para uso!")
                else:
                    print("\n✗ Falha ao baixar modelo.")
        except (EOFError, KeyboardInterrupt):
            print("\n\nPulando download de modelos...")

    # Atualiza configuracao
    print("\n" + "=" * 60)
    print("Configurando AutoDeal para modo 100% gratuito...")
    print("=" * 60)

    # Verifica arquivo .env
    env_path = ".env"
    env_content = """
# ============================================
# AutoDeal IA Hunter - Configuracao 100% GRATUITA
# ============================================

# Deixe estas chaves VAZIAS para usar apenas Ollama (gratuito)
GROK_API_KEY=
SCRAPERAPI_KEY=
APIFY_API_KEY=
ZENROWS_KEY=

# Ollama (IA Local - 100% Gratuito)
USE_OLLAMA=true
OLLAMA_URL=http://localhost:11434
LLM_MODEL=qwen2.5-coder:7b
VISION_MODEL=qwen2.5-coder:7b
AI_SCRAPER_MODEL=qwen2.5-coder:7b

# AI Scraping
USE_HYBRID_SCRAPER=true
AI_SCRAPING_ENABLED=true
AI_SCRAPER_FALLBACK_ENABLED=true
AI_SCRAPER_PRIORITY=primary

# Scraping basico
SCRAPING_INTERVAL_HOURS=6
MAX_LISTINGS_PER_SOURCE=50
REQUEST_DELAY_SECONDS=3.0
MAX_RETRIES=3

# Banco de dados (SQLite - gratuito)
DATABASE_URL=sqlite:///autodeal.db

# Dashboard
DASHBOARD_PORT=8501
"""

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content.strip())
        print(f"✓ Arquivo {env_path} criado com configuracao gratuita!")
    except Exception as e:
        print(f"✗ Erro ao criar {env_path}: {e}")

    print("\n" + "=" * 60)
    print("Setup concluido!")
    print("=" * 60)
    print("\nProximos passos:")
    print("1. Certifique-se de que Ollama esta rodando")
    print("2. Execute: .\\start.bat")
    print("3. Escolha '3' para rodar os scrapers")
    print("\nComandos uteis:")
    print("  ollama list              # Listar modelos")
    print("  ollama pull qwen2.5-coder:7b  # Baixar modelo")
    print("  ollama rm <modelo>       # Remover modelo")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
