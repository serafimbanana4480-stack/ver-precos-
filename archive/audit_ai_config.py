"""
AI Configuration Audit - Check if AI is properly configured
"""
from pathlib import Path
import json

print("=" * 80)
print("AI CONFIGURATION AUDIT")
print("=" * 80)

# Check .env file
env_file = Path("d:/VER PRECOS/.env")
if env_file.exists():
    with open(env_file) as f:
        env_content = f.read()
    
    print("\n[.env Configuration]")
    print("-" * 80)
    
    ai_configs = []
    for line in env_content.split('\n'):
        if any(key in line.lower() for key in ['ollama', 'grok', 'ai', 'llm', 'vision']):
            # Mask sensitive values
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                if 'key' in key.lower() or 'token' in key.lower() or 'password' in key.lower():
                    value = '***MASKED***'
                ai_configs.append(f"{key}={value}")
    
    if ai_configs:
        for config in ai_configs:
            print(f"  {config}")
    else:
        print("  ❌ No AI configuration found in .env")
else:
    print("❌ .env file does not exist")

# Check config.py
config_file = Path("d:/VER PRECOS/config.py")
print("\n[config.py AI Settings]")
print("-" * 80)
with open(config_file) as f:
    config_content = f.read()

import re
ai_settings = []
for line in config_content.split('\n'):
    if any(key in line for key in ['use_ollama', 'ollama_url', 'grok_api_key', 'ai_model', 'vision_model']):
        if '=' in line and not line.strip().startswith('#'):
            ai_settings.append(line.strip())

if ai_settings:
    for setting in ai_settings:
        print(f"  {setting}")
else:
    print("  ❌ No AI settings in config.py")

# Check if Ollama is running
print("\n[Ollama Service Check]")
print("-" * 80)
try:
    import requests
    response = requests.get("http://localhost:11434/api/tags", timeout=2)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print(f"  ✓ Ollama is running")
        print(f"  Available models: {len(models)}")
        for model in models:
            print(f"    - {model.get('name')}")
    else:
        print(f"  ❌ Ollama returned status {response.status_code}")
except Exception as e:
    print(f"  ❌ Ollama not accessible: {e}")

# Check deal_finder.py to see if AI is actually called
print("\n[AI Execution Check in deal_finder.py]")
print("-" * 80)
deal_finder_file = Path("d:/VER PRECOS/ai_agent/deal_finder.py")
with open(deal_finder_file) as f:
    df_content = f.read()

if "llm_reviewer.review_vehicle" in df_content:
    print("  ✓ LLM review is called in deal_finder")
else:
    print("  ❌ LLM review NOT called in deal_finder")

if "vision_analyzer.analyze_vehicle_images" in df_content:
    print("  ✓ Vision analysis is called in deal_finder")
else:
    print("  ❌ Vision analysis NOT called in deal_finder")

if "perform_second_review" in df_content:
    print("  ✓ Second review function exists")
else:
    print("  ❌ Second review function missing")

print("\n" + "=" * 80)
