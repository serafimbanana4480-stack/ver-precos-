"""
CORS middleware for API — reads origins from CORS_ORIGINS env var.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
import os
import logging

logger = logging.getLogger(__name__)


def setup_cors(app: FastAPI) -> None:
    """Configure CORS from environment variable CORS_ORIGINS."""
    origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://localhost:8080")
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

    app.add_middleware(
        FastAPICORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        max_age=86400,
    )

    logger.info(f"CORS configured with {len(origins)} origin(s): {origins[:3]}{'...' if len(origins) > 3 else ''}")
"
