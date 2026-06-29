"""
Deep ML Audit - Investigate the broken XGBoost model
"""
import json
from pathlib import Path

print("=" * 80)
print("DEEP ML AUDIT - Investigating R² = -0.4442 Model")
print("=" * 80)

models_dir = Path("d:/VER PRECOS/models")

# Read model metrics
metrics_file = models_dir / "model_metrics.json"
with open(metrics_file) as f:
    metrics = json.load(f)

print("\nModel Metrics:")
print(f"  Training date: {metrics.get('training_date')}")
print(f"  Samples: {metrics.get('n_samples')}")
print(f"  MAE: €{metrics.get('mae'):.2f}")
print(f"  RMSE: €{metrics.get('rmse'):.2f}")
print(f"  R²: {metrics.get('r2'):.4f}")
print(f"  Features: {metrics.get('features')}")
print(f"  Rejected: {metrics.get('rejected')}")
print(f"  Reason: {metrics.get('reason')}")

# Read feature names
feature_file = models_dir / "feature_names.json"
with open(feature_file) as f:
    features = json.load(f)

print(f"\nFeatures used ({len(features)}):")
for i, feat in enumerate(features, 1):
    print(f"  {i}. {feat}")

# CRITICAL: Check if model is actually being used
print("\n" + "=" * 80)
print("CHECKING IF BROKEN MODEL IS BEING USED IN PRODUCTION")
print("=" * 80)

# Check the predict.py code to see if it uses the model
predict_file = Path("d:/VER PRECOS/valuation/predict.py")
with open(predict_file, 'r') as f:
    predict_code = f.read()

# Check if load_model is called
if "load_model()" in predict_code or "load_model" in predict_code:
    print("⚠️  predict.py contains load_model() - may attempt to use XGBoost")
else:
    print("✓ predict.py does NOT contain load_model() - using statistical fallback")

# Check if statistical approach is primary
if "estimate_market_value" in predict_code and "statistical" in predict_code.lower():
    print("✓ Statistical market valuation is implemented")
    
if "comparables" in predict_code.lower():
    print("✓ Comparable-based valuation is implemented")

# Check the actual valuation logic
print("\n" + "=" * 80)
print("VALUATION LOGIC ANALYSIS")
print("=" * 80)

# Extract the key valuation function
import re
match = re.search(r'def estimate_market_value.*?(?=\ndef )', predict_code, re.DOTALL)
if match:
    function_code = match.group(0)
    print("First 500 chars of estimate_market_value:")
    print(function_code[:500])
    print("...")
    
    if "median" in function_code:
        print("\n✓ Uses median-based statistical approach")
    if "XGBoost" in function_code or "xgb" in function_code.lower():
        print("\n⚠️  May use XGBoost model")
    if "fallback" in function_code.lower():
        print("\n✓ Has fallback logic")

print("\n" + "=" * 80)
