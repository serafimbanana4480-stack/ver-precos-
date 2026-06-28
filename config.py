from __future__ import annotations
import warnings
from pathlib import Path
from core.settings import settings, Settings, BASE_DIR, DATA_DIR, MODELS_DIR, LOGS_DIR

warnings.warn(
    "config.py is deprecated. Import 'from core.settings import settings' instead.",
    DeprecationWarning,
    stacklevel=2,
)

use_sqlite = settings.use_sqlite
grok_api_key = settings.grok_api_key
grok_api_url = "https://api.x.ai/v1"
llm_model = settings.ai_model
vision_model = settings.vision_model
streamlit_port = settings.dashboard_port
