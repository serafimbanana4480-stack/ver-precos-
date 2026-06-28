Set-Location "C:\Users\rodri\Desktop\VER PRECOS"

Write-Host "=== Checking Python ==="
& ".venv\Scripts\python.exe" -c "print('hello')"
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED"; exit 1 }

Write-Host "`n=== STEP 1: Process scraped HTML ==="
& ".venv\Scripts\python.exe" scripts\process_scraped.py
if ($LASTEXITCODE -ne 0) { Write-Host "STEP 1 FAILED"; exit 1 }

Write-Host "`n=== STEP 2: Clean and normalize ==="
& ".venv\Scripts\python.exe" scripts\clean_data.py
if ($LASTEXITCODE -ne 0) { Write-Host "clean_data FAILED"; exit 1 }

& ".venv\Scripts\python.exe" scripts\normalize_brands.py
if ($LASTEXITCODE -ne 0) { Write-Host "normalize_brands FAILED"; exit 1 }

& ".venv\Scripts\python.exe" scripts\extract_features.py
if ($LASTEXITCODE -ne 0) { Write-Host "extract_features FAILED"; exit 1 }

Write-Host "`n=== STEP 3: Statistical pricer ==="
& ".venv\Scripts\python.exe" valuation\statistical_pricer.py
if ($LASTEXITCODE -ne 0) { Write-Host "STEP 3 FAILED"; exit 1 }

Write-Host "`n=== STEP 4: Train ML model ==="
& ".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'.'); from valuation.train import train_all_models; import logging; logging.basicConfig(level=logging.INFO,format='%(message)s'); r=train_all_models(force_retrain=True); [print(f'{k}: {v[\"model_type\"]} R2={v[\"metrics\"][\"r2\"]:.4f} MAE=EUR{v[\"metrics\"][\"mae\"]:.0f} n={v[\"n_samples\"]}') if v else print(f'{k}: FAILED') for k,v in r.items()]"
if ($LASTEXITCODE -ne 0) { Write-Host "STEP 4 FAILED"; exit 1 }

Write-Host "`n=== STEP 5: DB stats ==="
& ".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'.'); from database.db import get_db_context; from database.models import Vehicle; from sqlalchemy import func; db=next(get_db_context()); t=db.query(Vehicle).count(); a=db.query(Vehicle).filter(Vehicle.is_active==True).count(); hp=db.query(Vehicle).filter(Vehicle.horsepower.isnot(None),Vehicle.is_active==True).count(); cc=db.query(Vehicle).filter(Vehicle.engine_size.isnot(None),Vehicle.is_active==True).count(); print(f'TOTAL:{t} ACTIVE:{a} HP:{hp} CC:{cc}'); [print(f'  {s.value if hasattr(s,\"value\") else s}:{c}') for s,c in db.query(Vehicle.source,func.count(Vehicle.id)).filter(Vehicle.is_active==True).group_by(Vehicle.source).all()]"
if ($LASTEXITCODE -ne 0) { Write-Host "STEP 5 FAILED"; exit 1 }

Write-Host "=== STEP 6: Improved Market Model Training ==="
& ".venv\Scripts\python.exe" scripts\improved_train.py
if ($LASTEXITCODE -ne 0) { Write-Host "STEP 6 failed"; exit 1 }

Write-Host "`n=== ALL STEPS COMPLETE ==="
