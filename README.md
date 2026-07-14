# 🚗 AutoDeal IA Hunter

> **O caçador inteligente de ofertas de veículos em Portugal** — Automatiza a procura, valorização e análise de veículos usados com IA e Machine Learning.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/serafimbanana4480-stack/ver-precos-app/actions/workflows/tests.yml/badge.svg)](https://github.com/serafimbanana4480-stack/ver-precos-app/actions)
[![Coverage](https://img.shields.io/badge/coverage-report-blue.svg)](https://github.com/serafimbanana4480-stack/ver-precos-app/actions)
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
| **ML Valuation** | Modelo segmentado 3 vias (XGBoost + CatBoost + LightGBM) com 18+ features (idade, km, HP, cilindrada, depreciación, prémios de mercado, etc.) | ✅ Ativo (R²=0.88 carros / 0.85 motos) |
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
git clone https://github.com/serafimbanana4480-stack/ver-precos-app.git
cd ver-precos-app

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

**Métricas do Modelo Atual (carros, 3.733 amostras):**
- **R²:** 0.8808 (explica 88% da variação de preço — modelo segmentado 3 vias)
- **MAE:** €4,376 (erro médio absoluto)
- **MAPE:** 14.7%
- **Features:** 18 (ano, km, HP, cilindrada, portas, idade, km/ano, combustível, caixa, marca, modelo, distrito, fator desvalorização, prémio combustível, prémio localização, log_km, km_excess, km_extreme)

> ⚠️ **Motos**: o modelo melhorou muito recentemente (R² 0.26 → **0.85** após limpeza de outliers com IsolationForest e re-treino XGBoost sobre 218 amostras). Ainda com MAPE ~29% (poucos dados), mas já fiável para filtrar deals grosseiros.

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
git clone https://github.com/serafimbanana4480-stack/ver-precos-app.git

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

## 🩺 Health Checks & Graceful Shutdown

O sistema foi desenhado para correr em produção de forma resiliente:

- **Health checks** (`utils/health_check.py`): verificam BD, configuração, logs graváveis e Ollama, agregando um status `healthy` / `degraded` / `unhealthy`.
- **API de health** (`api/routes/health.py`): endpoints prontos para orquestradores — `/health/live` (liveness), `/health/ready` (readiness), `/health/startup` (startup), `/health/metrics`, `/health/detailed`.
- **Docker**: o `Dockerfile` inclui `HEALTHCHECK` nativo (intervalo 30-60s) que usa estes endpoints.
- **Graceful shutdown** (`utils/production_safeguards.py`): `SIGINT`/`SIGTERM` disparam `graceful_shutdown()`, que encerra a fila de requests, liberta as ligações da BD (`engine.dispose()`), faz flush dos logs e sai de forma limpa — sem perder trabalho em curso.
- **Circuit breakers**: cada fonte de scraping (OLX, Standvirtual, AutoSapo, leiloeiras) tem um circuit breaker que abre após N falhas consecutivas e recupera após um timeout, evitando cascata de falhas.
- **Validação de ambiente em produção**: em `env=production`, o arranque recusa-se a iniciar se faltarem `DATABASE_URL`, `JWT_SECRET`, ou o Sentry DSN (com aviso).

```bash
# Verificação manual de saúde
python main.py health-check
```

---

## ⚠️ Limitações Conhecidas

- **Modelo de motos historicamente fraco**: estava em R²≈0.26 (233 amostras). Melhorado para **R²=0.85** após limpeza de outliers (IsolationForest) e re-treino XGBoost (218 amostras, MAPE ~29%). Ainda sensível à escassez de dados — novas amostras ajudam.
- **Scrapers bloqueados**: Facebook e PiscaPisca estão bloqueados por login/Cloudflare (0 resultados). AutoScout24 `.pt` está offline — usar `.com` com `cy=PT`.
- **Leilões não são mercado**: preços de leilão (LEILOSOC, VPAUTO, etc.) são ~8x inferiores ao mercado de retalho. O `HybridValuator` aplica um *auction adjustment* para não gerar "deals" falsos, mas continua a ser uma aproximação.
- **Scraping é frágil**: sites mudam de estrutura sem aviso; os parsers quebram periodicamente. Há fallback para `requests`+BeautifulSoup e `AutoUncle` (que agrega muitos sites) como fonte mais estável.
- **Scooters 125cc sobre-estimadas historicamente**: corrigidas com um *cap* por keywords; motos grandes (ex: BMW 1250 GS) não são afetadas.
- **CustoJusto KM=0**: corrigido com 3 níveis de fallback (params → regex do título → estimativa por ano), mas anúncios sem KM nem ano continuam imputados.

---

## ⚖️ Riscos Legais do Scraping

> ⚠️ **Aviso importante**: este projeto é para **fins educacionais e uso pessoal**. O scraping tem implicações legais e contratuais:

- **Termos de Serviço**: OLX, Standvirtual, AutoSapo e outros proíbem scraping automatizado nos seus ToS. Violar os ToS pode resultar em bloqueio de IP ou ações legais.
- **RGPD / Privacidade**: os anúncios podem conter dados de vendedores (nomes, contactos). Não armazenes nem reutilizes dados pessoais sem base legal.
- **Robots.txt**: respeita os ficheiros `robots.txt` de cada site e usa *delays* (configuráveis em `.env`) para não sobrecarregar os servidores.
- **Uso comercial**: revenda de dados extraídos ou decisões de negócio baseadas nas estimativas deste sistema são da tua responsabilidade.
- **Rate limiting / proxy**: o sistema suporta proxy e *circuit breakers*, mas és tu quem decide a agressividade. Sê ético.

**Recomendação**: usa apenas para análise pessoal, com *delays* conservadores, e nunca para spam ou contacto não solicitado de vendedores.

---

## 📝 Licença

Este projeto está licenciado sob a **MIT License** — vê o ficheiro [LICENSE](LICENSE).
É para fins **educacionais**. Respeita os termos de serviço dos websites ao fazer scraping.

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

- **Última atualização:** 2026-07-14
- **Branch:** `main`
- **Módulos Python:** 100+
- **Testes:** unitários + integração + e2e (CI com coverage report)
- **Modelo ML (carros):** segmentado 3 vias — XGBoost + CatBoost + LightGBM (R²=0.88, MAE=€4,376)
- **Modelo ML (motos):** XGBoost (R²=0.85, MAE=€4,818, MAPE=29% — 218 amostras, melhorado vs R²=0.26 anterior)
- **Fontes ativas:** AutoUncle (AUTOPT), Leilosoc, Carplus, CustoJusto, OLX, Standvirtual, AutoSapo

---

**Feito com ❤️ em Portugal** 🇵🇹
