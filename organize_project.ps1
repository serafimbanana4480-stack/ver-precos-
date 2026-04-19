#!/usr/bin/env powershell
# Script de organização do projeto AutoDeal IA Hunter
# Executa backup e limpeza de arquivos não essenciais

$ErrorActionPreference = "Stop"
$projectRoot = "d:\VER PRECOS"
$backupDir = "$projectRoot\backup"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AutoDeal IA Hunter - Project Organizer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Criar estrutura de backup
Write-Host "[1/6] Criando estrutura de backup..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$backupDir\scrapers" | Out-Null
New-Item -ItemType Directory -Force -Path "$backupDir\tests" | Out-Null
New-Item -ItemType Directory -Force -Path "$backupDir\utils" | Out-Null
New-Item -ItemType Directory -Force -Path "$backupDir\scripts" | Out-Null
Write-Host "  ✓ Pastas de backup criadas" -ForegroundColor Green

# 2. Backup dos scrapers não essenciais
Write-Host "`n[2/6] Fazendo backup de scrapers não essenciais..." -ForegroundColor Yellow

$scrapersToBackup = @(
    "ai_extractor.py",
    "ai_scraper.py",
    "api_clients.py",
    "base_scraper.py",
    "camoufox_client.py",
    "custojusto_scraper.py",
    "hybrid_scraper.py",
    "managed_client.py",
    "ollama_direct.py",
    "pipeline.py",
    "regex_extractor.py",
    "schema.py",
    "session_manager.py",
    "simplified_olx_scraper.py",
    "standvirtual_scraper_v2.py",
    "unified_scraper.py",
    "vision_analyzer.py"
)

foreach ($scraper in $scrapersToBackup) {
    $source = "$projectRoot\scrapers\$scraper"
    if (Test-Path $source) {
        Copy-Item -Path $source -Destination "$backupDir\scrapers\" -Force
        Write-Host "  ✓ Backup: $scraper" -ForegroundColor Green
    }
}

# 3. Mover arquivos de teste da raiz para tests/
Write-Host "`n[3/6] Movendo arquivos de teste..." -ForegroundColor Yellow

$testFiles = @(
    "test_system.py",
    "test_new_architecture.py",
    "test_olx_cat_id.py",
    "test_standvirtual_api.py",
    "verify_project.py",
    "validate_final.py"
)

foreach ($testFile in $testFiles) {
    $source = "$projectRoot\$testFile"
    if (Test-Path $source) {
        Move-Item -Path $source -Destination "$projectRoot\tests\" -Force
        Write-Host "  ✓ Movido: $testFile" -ForegroundColor Green
    }
}

# 4. Mover arquivos de scratch/tests para tests/
Write-Host "`n[4/6] Movendo testes de scratch/..." -ForegroundColor Yellow
if (Test-Path "$projectRoot\scratch") {
    $scratchFiles = Get-ChildItem -Path "$projectRoot\scratch" -Filter "test_*.py" -File
    foreach ($file in $scratchFiles) {
        Move-Item -Path $file.FullName -Destination "$projectRoot\tests\" -Force
        Write-Host "  ✓ Movido: $($file.Name)" -ForegroundColor Green
    }
}

# 5. Mover scripts utilitários para scripts/
Write-Host "`n[5/6] Organizando scripts..." -ForegroundColor Yellow

$scriptsToMove = @(
    "setup_ollama.py",
    "check_ollama.py",
    "debug_raw_olx.py",
    "run_hunter.py",
    "run_simple_scraper.py",
    "run_with_fallback.py",
    "bulk_import.py"
)

foreach ($script in $scriptsToMove) {
    $source = "$projectRoot\$script"
    if (Test-Path $source) {
        Move-Item -Path $source -Destination "$projectRoot\scripts\" -Force
        Write-Host "  ✓ Movido: $script" -ForegroundColor Green
    }
}

# 6. Limpar diretórios de cache
Write-Host "`n[6/6] Limpando caches..." -ForegroundColor Yellow

$cacheDirs = @(
    ".bg-shell",
    ".claude",
    ".claude-flow",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "sessions",
    "services"
)

foreach ($dir in $cacheDirs) {
    $path = "$projectRoot\$dir"
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force
        Write-Host "  ✓ Removido: $dir" -ForegroundColor Green
    }
}

# Limpar __pycache__ recursivamente
Write-Host "  Limpando __pycache__ recursivo..." -ForegroundColor Yellow
Get-ChildItem -Path $projectRoot -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Organização completa!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Resumo:" -ForegroundColor Yellow
Write-Host "  - Backup criado em: $backupDir" -ForegroundColor White
Write-Host "  - Scrapers mantidos (essenciais):" -ForegroundColor White
Write-Host "    * olx_scraper.py" -ForegroundColor White
Write-Host "    * standvirtual_scraper.py" -ForegroundColor White
Write-Host "    * autosapo_scraper.py" -ForegroundColor White
Write-Host "    * olx_scraper_final.py" -ForegroundColor White
Write-Host "    * standvirtual_scraper_final.py" -ForegroundColor White
Write-Host "    * autosapo_scraper_final.py" -ForegroundColor White
Write-Host "  - Testes organizados em: tests/" -ForegroundColor White
Write-Host "  - Caches limpos" -ForegroundColor White
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Yellow
Write-Host "  1. Verifique se os scrapers principais funcionam" -ForegroundColor White
Write-Host "  2. Teste: python main.py init" -ForegroundColor White
Write-Host "  3. Teste: python main.py scrape --source olx --max-listings 5" -ForegroundColor White
