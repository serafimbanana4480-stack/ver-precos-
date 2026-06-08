# 🤖 AutoDeal Multi-Agent System

Sistema de agentes inteligentes para desenvolvimento, monitorização e melhoria contínua do projeto AutoDeal IA Hunter.

## Arquitetura

Inspirado nos melhores frameworks do mundo (LangGraph, CrewAI, MetaGPT), o nosso sistema combina:

- **State-machine execution** (tipo LangGraph) — checkpoints, retries, dependências
- **Role-based agents** (tipo CrewAI) — cada agente tem um papel especializado
- **SOP-driven workflows** (tipo MetaGPT) — ciclos de melhoria estruturados

## Agentes Disponíveis

| Agente | Papel | Comando |
|--------|-------|---------|
| `code_reviewer` | Revisa código Python (AST + IA) | `python main.py agent run` |
| `architecture_guardian` | Valida estrutura e camadas | `python main.py agent run` |
| `test_runner` | Executa pytest e analisa coverage | `python main.py agent run` |
| `continuous_improvement` | Monitoriza e sugere melhorias | `python main.py agent watch` |
| `project_generator` | Gera projetos do zero | `python main.py agent generate` |

## Multi-AI Router

Suporta múltiplos providers de IA com fallback automático:

1. **Ollama** (local, grátis) — qwen2.5, llama3.1, deepseek, etc.
2. **Grok** (cloud) — via GROK_API_KEY
3. **OpenAI** (cloud) — via OPENAI_API_KEY
4. **Anthropic** (cloud) — via ANTHROPIC_API_KEY

O router seleciona automaticamente o melhor provider disponível e faz fallback se um falhar.

## CLI

```bash
# Ver status do sistema de agentes
python main.py agent status

# Executar ciclo de melhoria contínua (batch)
python main.py agent run

# Iniciar watcher em tempo real (monitoriza alterações de ficheiros)
python main.py agent watch

# Gerar novo projeto do zero
python main.py agent generate "Especificação do projeto" --output ./meu_projeto
```

## Prompts Otimizados

Os prompts em `agents/prompts.py` foram projetados para:
- Máxima eficácia com modelos locais (Ollama 7B-9B)
- Respostas estruturadas e acionáveis
- Português de Portugal como idioma padrão
- Foco em segurança, performance e arquitetura

## Estrutura

```
agents/
├── __init__.py              # Exports principais
├── orchestrator.py          # Motor de orquestração (LangGraph-style)
├── multi_ai_router.py       # Router multi-provider com fallback
├── code_reviewer.py         # Análise estática + IA
├── architecture_guardian.py # Validação arquitetural
├── test_runner.py           # Execução e análise de testes
├── continuous_improvement.py # Monitorização em tempo real
├── project_generator.py     # Geração de projetos do zero
└── prompts.py               # Biblioteca de prompts otimizados
```