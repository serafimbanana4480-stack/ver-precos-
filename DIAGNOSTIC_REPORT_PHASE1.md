# Fase 1 — Diagnóstico Completo do Event Loop

**Data**: 2024-04-18  
**Foco**: Asyncio, Resource Leaks, Race Conditions  

---

## 1.1 Análise de Conflitos Asyncio

### ✅ Problemas ENCONTRADOS

#### 1. Uso de `asyncio.run()` em múltiplos arquivos
**Impacto**: Médio  
**Local**: 12 arquivos  

```
main.py:216               - asyncio.run(run_scraping()) - CORRETO (entry point)
run_hunter.py:25          - asyncio.run(start_hunter()) - CORRETO (entry point)
scrapers/demo_hybrid_scraper.py - ARQUIVO DE DEMO
scrapers/simplified_olx_scraper.py - ARQUIVO SIMPLIFICADO (não usado em prod)
scratch/test_*.py         - ARQUIVOS DE TESTE (5 arquivos)
scripts/bulk_import.py    - SCRIPT UTILITÁRIO
tests/test_*.py           - TESTES (2 arquivos)
```

**Avaliação**: ✅ Os únicos `asyncio.run()` no código de produção são em entry points (`main.py`, `run_hunter.py`), o que é correto. Não há aninhamento.

---

#### 2. ❌ Pass Statements Vazios em Except Blocks
**Impacto**: Alto  
**Local**: Múltiplos arquivos  

**Arquivos com problema (corrigidos parcialmente)**:
- `scrapers/standvirtual_scraper.py:227` - _handle_consent try/except pass
- `scrapers/autosapo_scraper.py:195` - Cookie consent handling  
- `scrapers/regex_extractor.py` - Múltiplos parsing errors silenciados

**Problema**: Erros silenciados dificultam debugging e escondem problemas reais.

**Status**: ✅ Corrigidos na última sessão (agora têm logger.debug)

---

#### 3. ❌ Uso de `time.sleep()` em código async
**Impacto**: Médio  
**Local**: `scrapers/standvirtual_scraper.py:234`, `autosapo_scraper.py`  

```python
# Código problemático:
for i in range(5):
    page.evaluate("window.scrollBy(0, 1000)")
    time.sleep(random.uniform(0.5, 1.0))  # ❌ Bloqueia event loop!
```

**Problema**: `time.sleep()` bloqueia o event loop asyncio inteiro. Deveria usar `await asyncio.sleep()`.

**Recomendação**: Substituir por `await asyncio.sleep()`.

---

### ✅ O que está CORRETO

| Aspecto | Status | Detalhes |
|---------|--------|----------|
| `asyncio.run()` aninhado | ✅ OK | Apenas entry points usam |
| `get_event_loop()` | ✅ OK | Não encontrado |
| `get_running_loop()` | ✅ OK | Não encontrado |
| Mix sync/async | ⚠️ OK | Boundary está claro em geral |
| Event loop em thread | ✅ OK | Não encontrado |
| Coroutines não awaited | ✅ OK | Não encontrado |

---

## 1.2 Análise de Resource Leaks

### ✅ Problemas ENCONTRADOS

#### 1. ❌ HTTP Clients sem Context Manager
**Impacto**: Médio  
**Local**: `utils/production_safeguards.py`  

```python
# Linha ~252
import httpx
resp = httpx.get(f"{settings.ollama_url}/api/tags", timeout=5)
```

**Problema**: Client httpx não é fechado explicitamente.

**Recomendação**: Usar `with httpx.Client() as client:` ou `async with httpx.AsyncClient() as client:`.

---

#### 2. ⚠️ Playwright Resources
**Impacto**: Baixo-Médio  
**Local**: `scrapers/managed_client.py:317-398`  

```python
# Código atual:
async with async_playwright() as p:
    browser = await p.chromium.launch(...)
    # ... operações ...
    await browser.close()  # ✅ Fecha browser
# Playwright context fecha automaticamente
```

**Avaliação**: ✅ Playwright é gerenciado corretamente com `async with` e `browser.close()`.

---

#### 3. ⚠️ Database Sessions
**Impacto**: Baixo  
**Local**: Múltiplos arquivos  

```python
# Em scrapers/standvirtual_scraper.py
with get_db_context() as db:
    # ... operações ...
```

**Avaliação**: ✅ Usa context manager `get_db_context()` que gerencia automaticamente.

---

### ✅ O que está CORRETO

| Recurso | Status | Detalhes |
|---------|--------|----------|
| Playwright browsers | ✅ OK | Fechados com `browser.close()` + `async with` |
| Database sessions | ✅ OK | Context managers usados |
| Arquivos | ✅ OK | Não identificados problemas |
| Subprocessos | ✅ OK | Não identificados problemas |

---

## 1.3 Análise de Race Conditions

### ✅ Problemas ENCONTRADOS

#### 1. ❌ Singletons Thread-Unsafe
**Impacto**: Alto  
**Local**: Múltiplos arquivos  

**AIScraper**:
```python
class AIScraper:
    _instance = None  # ❌ Race condition potencial
    
    def __new__(cls):
        if cls._instance is None:  # ❌ Check-then-act race
            cls._instance = super().__new__(cls)
        return cls._instance
```

**Problema**: Padrão singleton sem locks pode criar múltiplas instâncias em ambiente multi-thread/async.

**Arquivos afetados**:
- `scrapers/ai_scraper.py` - AIScraper singleton
- `scrapers/ai_extractor.py` - AIExtractor singleton
- `scrapers/managed_client.py` - ManagedScrapingClient singleton
- `utils/selector_manager.py` - SelectorManager singleton
- Múltiplos outros get_*_client() functions

**Recomendação**: 
1. Usar `asyncio.Lock()` para singletons
2. Ou usar `functools.lru_cache()` como decorator
3. Ou aceitar múltiplas instâncias (melhor para async)

---

#### 2. ❌ Semaphore sem bound checking
**Impacto**: Médio  
**Local**: `scrapers/ai_scraper.py:29`  

```python
self._semaphore = asyncio.Semaphore(1)  # Apenas 1 requisição simultânea
```

**Problema**: Muito conservador. Ollama pode processar múltiplas requisições.

**Recomendação**: Aumentar para 3-5 ou usar configuração dinâmica.

---

### ✅ O que está CORRETO

| Aspecto | Status | Detalhes |
|---------|--------|----------|
| Shared state com locks | ⚠️ Parcial | Alguns locks, não todos |
| Counters globais | ✅ OK | Não identificados |
| Cache | ✅ OK | Sem cache compartilhado crítico |

---

## Resumo Executivo

### 🔴 Problemas CRÍTICOS (Resolver na Fase 2)

1. **Singletons Thread-Unsafe** - Pode causar múltiplas instâncias de LLM clients
2. **`time.sleep()` em async** - Bloqueia event loop
3. **HTTP Client não fechado** - Leak de conexões

### 🟠 Problemas IMPORTANTES (Resolver na Fase 2)

4. **Semaphore muito conservador** - Limita performance
5. **Pass statements** - Já corrigidos na última sessão

### 🟡 Problemas MENORES (Quando houver tempo)

6. Documentar melhor boundaries sync/async
7. Adicionar mais logging de lifecycle

---

## Métricas

| Categoria | Encontrados | Críticos | Importantes | Menores |
|-----------|-------------|----------|-------------|---------|
| Asyncio | 3 | 1 | 1 | 1 |
| Resource Leaks | 1 | 0 | 1 | 0 |
| Race Conditions | 2 | 1 | 1 | 0 |
| **Total** | **6** | **2** | **3** | **1** |

---

## Priorização para Fase 2

### Ordem de Correção:

1. **Fix Singletons** - `scrapers/ai_scraper.py`, `ai_extractor.py`, `managed_client.py`
2. **Fix time.sleep() → asyncio.sleep()** - `standvirtual_scraper.py`, `autosapo_scraper.py`
3. **Fix HTTP client lifecycle** - `production_safeguards.py`
4. **Adjust Semaphore** - `ai_scraper.py`
5. **Test everything** - Verificar se correções funcionam

---

## Recomendação

**Status**: Diagnóstico completo. Pronto para Fase 2 (Correções).

**Risco**: Médio. Correções são localizadas e bem definidas.

**Esforço estimado**: 3-4 horas para todas as correções.

---

**Relatório gerado por**: Cascade AI  
**Ferramentas usadas**: grep, read_file, análise estática  
**Data**: 2024-04-18
