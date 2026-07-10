# =============================================================================
# AutoDeal IA Hunter — Multi-Stage Optimized Dockerfile
# =============================================================================
# Build stages:
#   1. builder     — Compile Python dependencies (heavy build tools)
#   2. playwright  — Install Playwright browsers (large binaries)
#   3. production  — Final minimal runtime image
#
# Size reduction: ~2.5GB → ~800MB (≈70% smaller)
# Security: Runs as non-root user, minimal attack surface
# =============================================================================

# -----------------------------------------------------------------------------
# STAGE 1: Builder — Compile wheels with build dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies (only needed for compiling packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and pre-compile wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# -----------------------------------------------------------------------------
# STAGE 2: Playwright Browser Downloader
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS playwright

WORKDIR /playwright

# Install minimal deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright package
COPY --from=builder /build/wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/playwright*.whl 2>/dev/null || \
    pip install --no-cache-dir playwright

# Download Chromium browser (only what we need)
RUN playwright install chromium && \
    playwright install-deps chromium

# -----------------------------------------------------------------------------
# STAGE 3: Production — Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS production

LABEL maintainer="AutoDeal IA Hunter"
LABEL description="Intelligent vehicle deal finder for Portugal"
LABEL version="3.0"

# Security: Create non-root user
RUN groupadd -r autodeal && useradd -r -g autodeal -s /bin/false autodeal

WORKDIR /app

# Install ONLY runtime system dependencies
# These are needed by: numpy(scipy), pandas, xgboost, playwright, Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Copy pre-built wheels from builder
COPY --from=builder /build/wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy Playwright browsers from playwright stage
COPY --from=playwright /root/.cache/ms-playwright /home/autodeal/.cache/ms-playwright
RUN chown -R autodeal:autodeal /home/autodeal/.cache

# Copy application code (respect .dockerignore)
COPY --chown=autodeal:autodeal . .

# Create runtime directories
RUN mkdir -p data models logs exports && chown -R autodeal:autodeal /app

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/home/autodeal/.cache/ms-playwright
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Copy entrypoint script
COPY --chown=autodeal:autodeal docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Switch to non-root user
USER autodeal

# Expose ports
EXPOSE 8501

# Entrypoint + Default command
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

# =============================================================================
# Alternative targets (use with: docker build --target <name>)
# =============================================================================

# -----------------------------------------------------------------------------
# STAGE 4: API — FastAPI backend only (no Streamlit)
# -----------------------------------------------------------------------------
FROM production AS api

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# -----------------------------------------------------------------------------
# STAGE 5: Scheduler — Background worker (autonomous: scrape+retrain+health)
# -----------------------------------------------------------------------------
FROM production AS scheduler

EXPOSE 8501

# O scheduler autónomo faz scrape diário, retrain semanal e relatório de saúde.
# Mantém-se vivo; o módulo faz o loop interno (schedule.run_pending).
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import subprocess,sys; sys.exit(0 if b'scheduler.autonomous' in subprocess.check_output(['pgrep','-af','scheduler'],stderr=subprocess.STDOUT) else 1)"

CMD ["python", "-m", "scheduler.autonomous"]

# -----------------------------------------------------------------------------
# STAGE 6: Development — Full dev environment with root access
# -----------------------------------------------------------------------------
FROM builder AS development

WORKDIR /app

# Install all deps editable
RUN pip install --no-cache-dir -r requirements.txt

# Install dev tools
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    black \
    isort \
    mypy \
    flake8

# Install Playwright browsers
RUN playwright install chromium && playwright install-deps chromium

# Copy code
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

EXPOSE 8501 8000

CMD ["/bin/bash"]
