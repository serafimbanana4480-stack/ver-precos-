# 🚗 AutoDeal IA Hunter

> **O caçador inteligente de ofertas de veículos em Portugal** — Automatiza a procura, valorização e análise de veículos usados com IA e Machine Learning.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Educational-orange.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](Dockerfile)

---

## 🎯 Visão Geral

O **AutoDeal IA Hunter** é um sistema automatizado que:

1. **Rastreia** dezenas de milhares de anúncios de veículos em Portugal (OLX, Standvirtual, AutoSapo)
2. **Avalia** o preço justo usando Machine Learning (XGBoost) treinado em dados reais
3. **Analisa** a descrição e imagens com IA (LLM + Vision AI)
4. **Pontua** as melhores ofertas (deal score) com base em económico e mercado
5. **Notifica** via Discord, Email ou Telegram quando encontra uma "peek deal"

---

## ✨ Funcionalidades Principais

| Funcionalidade | Descrição | Estado |
|----------------|-------------|--------|
| **Multi-Source Scraping** | OLX.pt, Standvirtual, AutoSapo.pt com Playwright + Rust | ✅ Ativo |
| **ML Valuation** | Modelo XGBoost com 15+ features (ano, km, cilindrada, combustible, etc.) | ✅ Ativo (R²=0.59) |
| **IA Análise** | LLM (Grok/Ollama) + Vision AI para condição do veículo | ✅ Ativo |
| **Deal Scoring** | Algoritmo proprietário que cruza preço previsto vs. preço anúncio | ✅ Ativo |
| **Dashboard Streamlit** | Interface web com filtros, gráficos e exportação CSV | ✅ Ativo (localhost:8501) |
| **Scheduler Autónomo** | Execução diária automática com APScheduler | ✅ Ativo |
| **Notificações** | Discord Webhook, Email SMTP, Telegram Bot | ✅ Ativo |
| **Docker Ready** | Deploy completo com Docker Compose | ✅ Ativo |

---

## 🏗️ Arquitetura

```
AutoDeal IA Hunter
├── Scrapers (Playwright + Rust)
│   ├── OLX.pt (✅ integrado)
│   ├── Standvirtual (✅ integrado)
│   └── AutoSapo (✅ integrado)
├── Database (SQLite / PostgreSQL)
├── ML Valuation (XGBoost)
│   ├── Treino (train_model.py)
│   └── Predição (predict.py)
├── AI Agent
│   ├── LLM Review (Grok API / Ollama)
│   └── Vision Analysis (condição do veículo)
├── Scheduler (APScheduler)
└── Dashboard (Streamlit)
```

---

## 🚀 Quick Start

### Opção 1: Docker (Recomendado)

```bash
# 1. Clonar o repositório
git clone https://github.com/serafimbanana4480-stack/ver-precos-.git
cd ver-precos-

# 2. Configurar ambiente
cp .env.example .env
# Editar .env com as tuas configurações

# 3. Iniciar com Docker Compose
docker-compose up -d

# 4. Aceder ao dashboard
https://localhost:8501
```

### Opção 2: Instalação Local

```bash
# 1. Instalar dependências Python
pip install -r requirements.txt

# 2. Instalar browsers Playwright
playwright install chromium
playwright install-deps chromium

# 3. Configurar ambiente
cp .env.example .env
# Editar .env (ou usar SQLite por defeito)

# 4. Inicializar base de dados
py -3 main.py init
py -3 main.py health-check

# 5. Executar scrapers
python main.py scrape --source all --vehicle-type carros --max-listings 50

# 6. Treinar modelo ML
python main.py train --force

# 7. Atualizar avaliações
python main.py valuate --batch-size 100

# 8. Encontrar ofertas
python main.py find-deals --limit 20 --min-profit 1500

# 9. Iniciar dashboard
python main.py dashboard --port 8501
```

---

## 📖 Guia de Uso

### 1. Scraping de Anúncios

```bash
# Portugal, carros, máximo 100 anúncios
python main.py scrape --country PT --vehicle-type carros --max-listings 100

# Múltiplas fontes
python main.py scrape --source olx,standvirtual --vehicle-type motos

# Com debug
python main.py scrape --source all --debug
```

### 2. Treino do Modelo ML

```bash
# Treino completo (apaga modelo anterior)
python main.py train --force

# Treino incremental (usa novos dados)
python main.py train --incremental
```

**Métricas do Modelo Atual:**
- **R²:** 0.5907 (expllica 59% da variação de preço)
- **MAE:** €8,528 (erro médio absoluto)
- **Features:** 15 (ano, km, cilindrada, combustible, marca, modelo, etc.)

### 3. Avaliação de Veículos

```bash
# Avaliar um veículo específico
python main.py valuate --listing-id 12345

# Avaliar todos os novos veículos
python main.py valuate --batch-size 100
```

### 4. Descoberta de Ofertas (Deal Finder)

```bash
# Encontrar as 20 melhores ofertas (lucro > €1,500)
python main.py find-deals --limit 20 --min-profit 1500

# Critérios:
# - deal_score ≥ 7.0
# - Diferença preço_previsto - preço_anúncio > €1,500
# - Análise LLM (se disponível): "Approved"
```

### 5. Dashboard Streamlit

Aceder a `http://localhost:8501` após iniciar o dashboard:

- **Visão Geral:** Métricas principais, gráfico de preços
- **Lista de Veículos:** Tabela filtrável e ordenável
- **Top Ofertas:** As melhores oportunidades (IA analisada)
- **Analytics:** Histórico de preços, tendências de mercado
- **Export:** Descarregar resultados em CSV

---

## 🤖 Funcionalidades de IA

### LLM Analysis (Grok ou Ollama)

O sistema usa LLM para analisar a descrição do veículo:

- ✅ **Problemas ocultos** (acidentes, problemas mecânicos)
- ✅ **Características valorizadoras** (histórico de manutenção, extras)
- ✅ **Posicionamento no mercado**
- ✅ **Recomendação final** (Approved/Rejected)

### Vision Analysis (Análise de Imagem)

A IA analisa as fotos do veículo para detetar:

- ✅ **Danos exteriores** (dentes, riscos, ferrugem)
- ✅ **Condição dos pneus**
- ✅ **Desgaste interior**
- ✅ **Pontuação geral de condição** (0-10)

---

## ⚙️ Configuração

### Ficheiro `.env`

| Variável | Descrição | Defeito |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite (autodeal.db) |
| `GROK_API_KEY` | Grok API key para LLM | - |
| `USE_OLLAMA` | Usar Ollama local em vez de Grok | `false` |
| `OLLAMA_URL` | URL da API Ollama | `http://localhost:11434` |
| `DISCORD_WEBHOOK_URL` | Discord webhook para notificações | - |
| `EMAIL_SMTP_*` | Configuração SMTP (Email) | - |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot token | - |
| `SCRAPING_INTERVAL_HOURS` | Frequência de scraping | `6` |
| `DEAL_SCORE_THRESHOLD` | Pontuação mínima de oferta | `7.0` |

---

## 📊 Scheduler Autónomo

O scheduler executa tarefas automáticas:

| Tarefa | Frequência | Descrição |
|--------|------------|-------------|
| Scraping diário | Configurável (6h) | Descarregar novos anúncios |
| Análise periódica | Configurável (12h) | Avaliar veículos novos |
| Descoberta de ofertas | Configurável (24h) | Executar deal finder |
| Envio de notificações | Após cada descoberta | Alertar sobre top deals |

```bash
# Iniciar scheduler (contínuo)
python main.py scheduler
```

---

## 🌐 Deploy

### Railway

1. Conectar repositório GitHub ao Railway
2. Adicionar variáveis de ambiente
3. Fazer deploy

### Render

1. Fazer push do código para GitHub
2. Criar novo Web Service no Render
3. Configurar variáveis de ambiente
4. Fazer deploy

### VPS (Linux)

```bash
# 1. SSH para o servidor
ssh user@server-ip

# 2. Clonar repositório
git clone https://github.com/serafimbanana4480-stack/ver-precos-.git

# 3. Configurar `.env`
nano .env

# 4. Iniciar com Docker Compose
docker-compose up -d

# 5. Verificar logs
docker-compose logs -f
```

---

## 📂 Estrutura do Projeto

```
ver-precos-/
├── main.py                 # Ponto de entrada
├── config.py              # Configuração
├── requirements.txt       # Dependências
├── .env.example          # Template de ambiente
├── scrapers/             # Módulos de scraping
│   ├── olx_scraper.py
│   ├── standvirtual_scraper.py
│   └── autosapo_scraper.py
├── database/             # Camada de base de dados
│   ├── models.py
│   └── db.py
├── valuation/            # Avaliação ML
│   ├── train_model.py
│   └── predict.py
├── ai_agent/             # Análise IA
│   ├── llm_review.py
│   ├── vision_analysis.py
│   └── deal_finder.py
├── scheduler/            # Agendador de tarefas
│   └── daily_job.py
├── dashboard/            # Dashboard Streamlit
│   └── app.py
├── utils/                # Utilitários
│   ├── helpers.py
│   └── logging_config.py
├── data/                 # Diretório de dados
├── models/               # Modelos ML
├── logs/                 # Ficheiros de log
├── exports/              # Ficheiros exportados
├── Dockerfile            # Imagem Docker
├── docker-compose.yml    # Config Docker Compose
└── README.md            # Este ficheiro
```

---

## 🔍 Troubleshooting

### Problemas de Conexão à Base de Dados

Verificar se PostgreSQL está a correr:

```bash
docker-compose ps postgres
```

### Erros de Scraping

- Verificar conexão à internet
- Confirmar que os websites estão acessíveis
- Ajustar delays na configuração se houver rate-limiting

### Falha no Treino do Modelo

Garantir dados suficientes:

```bash
python main.py scrape --max-listings 200
```

### Funcionalidades de IA Não Funcionam

- Verificar se a API key está definida
- Confirmar que Ollama está a correr (se usar local)
- Rever logs em `logs/autodeal.log`

---

## 📝 Licença

Este projeto é para fins **educacionais**. Respeitar os termos de serviço dos websites ao fazer scraping.

---

## 🤝 Contribuições

Contribuições são bem-vindas! Por favor:

1. Fazer fork do repositório
2. Criar uma branch de funcionalidade
3. Fazer as tuas alterações
4. Submeter um Pull Request

---

## 📞 Suporte

Para problemas e questões:

- Consultar a seção de troubleshooting
- Rever logs em `logs/autodeal.log`
- Abrir uma issue no GitHub

---

## 🙏 Agradecimentos

- **OLX-tracker (Rust):** https://github.com/nikuscs/olx-tracker
- **Standvirtual scraper:** https://github.com/miguelneto/Standvirtual
- **Playwright:** https://playwright.dev
- **XGBoost:** https://xgboost.readthedocs.io
- **Streamlit:** https://streamlit.io

---

**Nota**: Esta ferramenta é para uso educacional e pessoal. Cumprir sempre os termos de serviço dos websites e leis locais ao fazer scraping de dados.

---

## 📈 Estatísticas do Projeto

- **Última atualização:** 2026-06-28
- **Branch:** `main`
- **Total de ficheiros:** ~200 (código fonte)
- **Módulos Python:** 25+
- **Cobertura de testes:** 85%+
- **Modelo ML:** XGBoost (R²=0.59, MAE=€8,528)

---

**Feito com ❤️ em Portugal** 🇵🇹
