# Pixora 2.0 Production Container
# Unified Tier S Async Engine: FastAPI + WebSockets + Mounted Platform Hub + Redis Telemetry Worker
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application source code
COPY . .

# Create non-root user and ensure runtime directories exist with appropriate permissions
RUN useradd -m -u 1000 pixora && \
    mkdir -p /app/instance && \
    chown -R pixora:pixora /app

USER pixora

# Expose ports:
# 8000: Unified Async Engine (FastAPI WebSockets + REST + Flask Platform Hub)
# 5000: Backward-compatible legacy web port
EXPOSE 8000 5000

# Default command runs the Unified Async Platform Engine via Uvicorn ASGI
CMD ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
