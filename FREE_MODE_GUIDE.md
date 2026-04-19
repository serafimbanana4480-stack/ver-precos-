# AutoDeal IA Hunter - Modo 100% Gratuito (Ollama)

Guia completo para usar o AutoDeal IA Hunter completamente gratis usando Ollama (IA local) no seu PC.

## Resumo

Este modo usa **Ollama** para rodar modelos de IA localmente no seu PC, sem necessidade de:
- ❌ API keys pagas (Grok, OpenAI, etc.)
- ❌ Servicos de scraping pagos (ZenRows, ScraperAPI)
- ❌ GPUs caras - funciona com CPU!

## Requisitos Minimos

- Windows 10/11
- 8GB RAM (16GB recomendado)
- 10GB espaco em disco
- Conexao internet (apenas para baixar modelos 1 vez)

## Instalacao Rápida (3 Passos)

### Passo 1: Instalar Ollama

```powershell
# Opcao A: Via winget (recomendado)
winget install Ollama.Ollama

# Opcao B: Download manual
# Acesse: https://ollama.com/download
```

**Importante:** Reinicie o terminal/IDE apos instalar Ollama.

### Passo 2: Configurar AutoDeal

```powershell
# Execute o script de setup
.\venv\Scripts\python setup_ollama.py
```

Este script vai:
- Verificar se Ollama esta rodando
- Baixar um modelo de IA (se necessario)
- Configurar o arquivo `.env` para modo gratuito

### Passo 3: Verificar Instalacao

```powershell
# Teste se tudo esta funcionando
.\venv\Scripts\python check_ollama.py
```

Se aparecer "TUDO PRONTO!", pode comecar a usar.

## Uso

```powershell
# Iniciar o sistema
.\start.bat

# Escolha as opcoes:
# 1 - Inicializar banco de dados (primeira vez)
# 3 - Rodar scrapers
# 2 - Abrir dashboard
```

## Modelos Recomendados

| Modelo | Tamanho | Uso | Comando |
|--------|---------|-----|---------|
| **qwen2.5-coder:7b** | 4.5GB | Melhor para scraping | `ollama pull qwen2.5-coder:7b` |
| llama3.1:8b | 4.7GB | Boa escolha geral | `ollama pull llama3.1:8b` |
| mistral:7b | 4.1GB | Rapido | `ollama pull mistral:7b` |
| gemma2:9b | 5.4GB | Boa extracao | `ollama pull gemma2:9b` |

## Comandos Uteis do Ollama

```bash
# Listar modelos instalados
ollama list

# Baixar novo modelo
ollama pull qwen2.5-coder:7b

# Remover modelo
ollama rm qwen2.5-coder:7b

# Iniciar Ollama manualmente
ollama serve
```

## Solucao de Problemas

### "Ollama not running"

1. Clique no icone do Ollama no menu Iniciar
2. Aguarde 10 segundos
3. Execute: `python check_ollama.py`

### "No suitable model found"

Baixe um modelo:
```powershell
ollama pull qwen2.5-coder:7b
```

### "Out of memory" / PC lento

Use um modelo menor:
```powershell
ollama pull mistral:7b  # 4.1GB - mais leve
```

Ou limite o uso de RAM no `.env`:
```env
AI_SCRAPER_MODEL=mistral:7b
```

### Timeout ou demora

Modelos grandes demoram na primeira execucao. Seja paciente!
- Primeira chamada: ~30-60 segundos
- Chamadas seguintes: ~5-15 segundos

## Comparacao: Gratuito vs Pago

| Recurso | Gratuito (Ollama) | Pago (APIs) |
|---------|-------------------|-------------|
| Custo | R$ 0 | R$ 50-200/mes |
| Velocidade | ~5-15s/listing | ~1-3s/listing |
| Precisao | Boa | Excelente |
| OLX (bloqueado) | Usa regex fallback | Usa APIs pagas |
| Setup | Mais complexo | Simples |
| Privacidade | 100% local | Dados na nuvem |

## Limitacoes do Modo Gratuito

1. **OLX**: Pode ser bloqueado occasionalmente (usamos regex fallback)
2. **Velocidade**: Mais lento que APIs pagas (mas gratis!)
3. **RAM**: Consome mais memoria do PC
4. **CPU**: PC pode ficar lento durante scraping

## Dicas de Performance

1. **Feche outros programas** durante scraping
2. **Use modelos menores** se PC for lento
3. **Reduza MAX_LISTINGS** no `.env`:
   ```env
   MAX_LISTINGS_PER_SOURCE=30  # Em vez de 100
   ```
4. **Aumente delay** para evitar bloqueios:
   ```env
   REQUEST_DELAY_SECONDS=5.0
   ```

## Arquitetura do Sistema Gratuito

```
Standvirtual → Playwright → AI Extraction (Ollama) → Database
OLX → Playwright → Regex Fallback (sem IA) → Database
  ↓ (se falhar)
  → AI Scraper (Ollama) → Database
```

## Suporte

Se tiver problemas:

1. Execute diagnostico:
   ```powershell
   .\venv\Scripts\python check_ollama.py
   ```

2. Verifique logs em `logs/autodeal.log`

3. Reinstale Ollama se necessario

4. Reporte issues no GitHub

---

**Versao**: 2.0 - Modo 100% Gratuito
**Atualizado**: 2024
