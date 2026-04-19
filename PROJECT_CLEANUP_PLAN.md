# Plano de Organização do Projeto AutoDeal IA Hunter

## Objetivo
Organizar o projeto removendo arquivos desnecessários e estruturando de forma limpa e eficiente.

## Análise de Uso - Módulos Realmente Necessários

### Core (Essencial)
- `main.py` - Entry point principal
- `config.py` - Configurações centralizadas
- `start.bat` - Script de inicialização Windows
- `requirements.txt` - Dependências Python
- `requirements-minimal.txt` - Dependências mínimas

### Database (Essencial)
- `database/db.py` - Conexão e operações do banco
- `database/models.py` - Modelos SQLAlchemy
- `database/__init__.py`

### Scrapers (Essencial - 3 principais)
- `scrapers/olx_scraper.py` - Scraper OLX (principal)
- `scrapers/standvirtual_scraper.py` - Scraper Standvirtual (principal)
- `scrapers/autosapo_scraper.py` - Scraper AutoSapo (principal)
- `scrapers/__init__.py`
- `scrapers/olx_scraper_final.py` - Wrapper para main.py
- `scrapers/standvirtual_scraper_final.py` - Wrapper para main.py
- `scrapers/autosapo_scraper_final.py` - Wrapper para main.py

### Valuation (Essencial)
- `valuation/train_model.py` - Treino ML
- `valuation/predict.py` - Predição de preços
- `valuation/__init__.py`

### AI Agent (Essencial)
- `ai_agent/deal_finder.py` - Encontra melhores deals
- `ai_agent/llm_review.py` - Review com LLM
- `ai_agent/__init__.py`

### Dashboard (Essencial)
- `dashboard/app.py` - Interface Streamlit
- `dashboard/__init__.py`

### Validation (Essencial)
- `validation/scraped_models.py` - Modelos Pydantic
- `validation/cli_models.py` - Modelos CLI
- `validation/__init__.py`

### Utils (Essencial - mínimo)
- `utils/logging_config.py` - Configuração de logs
- `utils/production_safeguards.py` - Circuit breakers, etc
- `utils/health_check.py` - Health checks
- `utils/retry.py` - Retry logic
- `utils/data_validation.py` - Validação de dados
- `utils/__init__.py`

### Scheduler (Opcional)
- `scheduler/daily_job.py` - Agendador
- `scheduler/__init__.py`

## Arquivos para REMOVER (Não utilizados ou duplicados)

### Scrapers duplicados/não usados
- `scrapers/hybrid_scraper.py` - Complexo, não usado diretamente
- `scrapers/ai_scraper.py` - Não usado diretamente
- `scrapers/ai_extractor.py` - Não usado diretamente
- `scrapers/camoufox_client.py` - Cliente alternativo não usado
- `scrapers/custojusto_scraper.py` - Scraper não prioritário
- `scrapers/managed_client.py` - Complexo, não essencial
- `scrapers/ollama_direct.py` - Duplicado com ai_agent
- `scrapers/pipeline.py` - Não usado
- `scrapers/regex_extractor.py` - Não usado
- `scrapers/schema.py` - Não usado
- `scrapers/session_manager.py` - Não usado
- `scrapers/simplified_olx_scraper.py` - Duplicado
- `scrapers/standvirtual_scraper_v2.py` - Versão antiga
- `scrapers/unified_scraper.py` - Não usado
- `scrapers/vision_analyzer.py` - Movido para ai_agent
- `scrapers/base_scraper.py` - Não usado
- `scrapers/api_clients.py` - Não usado diretamente

### Arquivos de teste fora do lugar
- `test_new_architecture.py` - Mover para tests/
- `test_olx_cat_id.py` - Mover para tests/
- `test_system.py` - Mover para tests/
- `test_*.py` (na raiz) - Mover todos para tests/

### Scripts/utilitários não essenciais
- `run_hunter.py` - Script duplicado
- `setup_ollama.py` - Setup específico, pode manter em scripts/
- `check_ollama.py` - Verificação específica
- `validate_final.py` - Validação, mover para scripts/
- `verify_project.py` - Verificação, mover para scripts/
- `debug_raw_olx.py` - Debug específico
- `run_simple_scraper.py` - Script antigo
- `run_with_fallback.py` - Script antigo

### Diretórios para limpar/reorganizar
- `.bg-shell/` - Cache/desenvolvimento
- `.claude/` - Cache/desenvolvimento
- `.claude-flow/` - Cache/desenvolvimento
- `.github/` - Opcional (se não usar CI/CD)
- `.gsd/` - Cache do GSD
- `.mypy_cache/` - Cache
- `.planning/` - Documentação antiga (mover para context/)
- `.pytest_cache/` - Cache
- `__pycache__/` - Cache Python
- `alembic/` - Migrações (opcional)
- `analysis/` - Análises antigas
- `data/` - Dados gerados (manter)
- `exports/` - Exports gerados (manter)
- `logs/` - Logs gerados (manter)
- `models/` - Modelos ML gerados (manter)
- `scratch/` - Scripts de teste (mover para tests/)
- `scripts/` - Scripts utilitários (organizar)
- `services/` - Não usado
- `sessions/` - Cache

## Estrutura Final Proposta

```
VER PRECOS/
├── main.py                     # Entry point
├── config.py                   # Configurações
├── start.bat                   # Script Windows
├── requirements.txt            # Dependências
├── requirements-minimal.txt    # Dependências mínimas
├── .env.example                # Exemplo de env
├── README.md                   # Documentação
├── .gitignore                  # Git ignore
│
├── core/                       # Módulos core
│   ├── __init__.py
│   └── ...
│
├── scrapers/                   # Apenas 3 scrapers principais + wrappers
│   ├── __init__.py
│   ├── olx_scraper.py
│   ├── standvirtual_scraper.py
│   ├── autosapo_scraper.py
│   ├── olx_scraper_final.py
│   ├── standvirtual_scraper_final.py
│   └── autosapo_scraper_final.py
│
├── database/                   # Banco de dados
│   ├── __init__.py
│   ├── db.py
│   └── models.py
│
├── valuation/                  # ML/Valuation
│   ├── __init__.py
│   ├── train_model.py
│   └── predict.py
│
├── ai_agent/                   # IA/LLM
│   ├── __init__.py
│   ├── deal_finder.py
│   └── llm_review.py
│
├── dashboard/                  # Interface
│   ├── __init__.py
│   └── app.py
│
├── validation/                 # Validação
│   ├── __init__.py
│   ├── scraped_models.py
│   └── cli_models.py
│
├── utils/                      # Utilitários essenciais
│   ├── __init__.py
│   ├── logging_config.py
│   ├── production_safeguards.py
│   ├── health_check.py
│   ├── retry.py
│   └── data_validation.py
│
├── scheduler/                  # Agendador (opcional)
│   ├── __init__.py
│   └── daily_job.py
│
├── tests/                      # Todos os testes
│   ├── __init__.py
│   ├── test_scrapers.py
│   ├── test_database.py
│   ├── test_valuation.py
│   └── ...
│
├── context/                    # Documentação e contexto
│   ├── README.md
│   ├── architecture.md
│   ├── api_reference.md
│   └── workflows/              # Workflows do Windsurf/GSD
│       └── ...
│
├── scripts/                    # Scripts utilitários
│   ├── setup_ollama.py
│   ├── validate_project.py
│   └── bulk_import.py
│
└── data/                       # Dados gerados (manter no .gitignore)
    ├── exports/
    ├── logs/
    └── models/
```

## Ações a Executar

### 1. Criar estrutura de pastas
```bash
mkdir core
mkdir context/workflows
```

### 2. Mover arquivos de teste
```bash
mv test_*.py tests/
mv scratch/test_*.py tests/
```

### 3. Mover documentação
```bash
mv .planning/* context/
rm -rf .planning/
```

### 4. Limpar caches
```bash
rm -rf .bg-shell/
rm -rf .claude/
rm -rf .claude-flow/
rm -rf .mypy_cache/
rm -rf .pytest_cache/
rm -rf __pycache__/
rm -rf sessions/
rm -rf services/
```

### 5. Remover scrapers não essenciais (backup primeiro)
```bash
mkdir -p backup/scrapers
mv scrapers/hybrid_scraper.py backup/scrapers/
mv scrapers/ai_scraper.py backup/scrapers/
...
```

### 6. Atualizar imports nos scrapers principais
Verificar e simplificar imports nos 3 scrapers principais.

## Testes Necessários Após Limpeza

1. Testar importações: `python -c "from config import settings; print('OK')"`
2. Testar scrapers: `python main.py scrape --source olx --max-listings 5`
3. Testar database: `python main.py init`
4. Testar dashboard: `python main.py dashboard`

## Notas Importantes

- **FAZER BACKUP** antes de remover qualquer arquivo
- Testar cada funcionalidade após remoção
- Manter arquivos que possam ser úteis no backup/
- Documentar todas as mudanças
- Atualizar README.md com nova estrutura
