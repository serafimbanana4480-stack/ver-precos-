# Contexto do Projeto AutoDeal IA Hunter

Esta pasta contém documentação, workflows e contexto do projeto.

## Estrutura

```
context/
├── README.md                 # Este arquivo
├── ARCHITECTURE.md           # Arquitetura do sistema
├── API_REFERENCE.md          # Referência de APIs
├── CHANGELOG.md              # Histórico de mudanças
├── workflows/                # Workflows do Windsurf/GSD
│   ├── gsd-ecosystem.md
│   ├── gsd-quantum-commands.md
│   └── gsd-rules-engine.md
└── decisions/              # Registro de decisões arquiteturais
    └── ADR-001.md
```

## Visão Geral do Projeto

**AutoDeal IA Hunter** é um sistema inteligente de busca de ofertas de veículos para Portugal, combinando:

- **Web Scraping**: Coleta de dados de OLX, Standvirtual e AutoSapo
- **Machine Learning**: Predição de preços com XGBoost
- **Inteligência Artificial**: Análise de ofertas com LLM (GLM-5 via Ollama)
- **Dashboard**: Visualização de dados com Streamlit

## Arquitetura Simplificada

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scrapers  │────▶│   Database  │────▶│   Valuation │
│  (3 sites)  │     │  (SQLite)   │     │    (ML)     │
└─────────────┘     └─────────────┘     └─────────────┘
                            │                   │
                            ▼                   ▼
                     ┌─────────────┐     ┌─────────────┐
                     │   Dashboard │◀────│  AI Agent   │
                     │  (Streamlit)│     │   (Deals)   │
                     └─────────────┘     └─────────────┘
```

## Componentes Core

### 1. Scrapers (3 arquivos)
- `olx_scraper.py` + `olx_scraper_final.py`
- `standvirtual_scraper.py` + `standvirtual_scraper_final.py`
- `autosapo_scraper.py` + `autosapo_scraper_final.py`

### 2. Database
- `database/db.py` - Conexão SQLite
- `database/models.py` - Modelos SQLAlchemy

### 3. Valuation
- `valuation/train_model.py` - Treino XGBoost
- `valuation/predict.py` - Predição de preços

### 4. AI Agent
- `ai_agent/deal_finder.py` - Busca de deals
- `ai_agent/llm_review.py` - Análise LLM

### 5. Dashboard
- `dashboard/app.py` - Interface Streamlit

### 6. Utils Essenciais
- `utils/logging_config.py` - Logs
- `utils/production_safeguards.py` - Circuit breakers
- `utils/health_check.py` - Health checks
- `utils/retry.py` - Retry logic
- `utils/data_validation.py` - Validação

## Configuração

Arquivo `.env`:
```
DATABASE_URL=sqlite:///autodeal.db
OLLAMA_URL=http://localhost:11434
AI_MODEL=glm-5:latest
LOG_LEVEL=INFO
```

## Comandos Principais

```bash
# Inicializar
python main.py init

# Scraping
python main.py scrape --source olx --max-listings 50

# Treinar modelo
python main.py train

# Atualizar avaliações
python main.py valuate

# Encontrar deals
python main.py find-deals --limit 20

# Dashboard
python main.py dashboard
```

## Organização do Projeto

Após a limpeza, o projeto foi organizado em:

- **Core**: Apenas arquivos essenciais
- **tests/**: Todos os testes organizados
- **context/**: Documentação e workflows
- **backup/**: Arquivos removidos (preservados)

## Notas de Simplificação

A versão simplificada removeu:
- Scrapers alternativos e complexos
- Clientes de API pagos (ZenRows, ScraperAPI)
- AI scrapers complexos
- Pipeline de processamento pesado
- Múltiplas versões de scrapers

Mantendo apenas o essencial para funcionamento com:
- Playwright + stealth
- Ollama local (GLM-5)
- SQLite
- XGBoost
- Streamlit
