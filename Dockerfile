# =============================================================================
# QUANT TRADING IDX v7 — Multi-stage Dockerfile
# =============================================================================

# --- Stage 1: Build Dependencies ---
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build tools for native extensions (e.g. C++ compiler for LightGBM/XGBoost if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements & install dependencies into wheels
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt pytest pytest-cov

# --- Stage 2: Runtime Image ---
FROM python:3.11-slim-bookworm AS runner

WORKDIR /app

# Install runtime C libraries needed by LightGBM & Rich terminal
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels from builder stage
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Environment variables for terminal color, UTF-8, and Python behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TERM=xterm-256color \
    COLORTERM=truecolor \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Create non-root user for security
RUN groupadd -g 1000 quantuser && \
    useradd -u 1000 -g quantuser -m -s /bin/bash quantuser

# Copy application source code
COPY . /app

# Create persistent directories and set ownership
RUN mkdir -p /app/data /app/outputs/logs /app/outputs/backtest_results /app/outputs/models /app/.cache && \
    chown -R quantuser:quantuser /app

USER quantuser

# Default port for FastAPI Web API
EXPOSE 8000

# Default command: launch interactive master selector main.py
CMD ["python", "main.py"]
