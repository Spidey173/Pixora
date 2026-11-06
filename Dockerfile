# Pixora 2.0 Production Container
# Supports: Flask Platform Hub, FastAPI Real-Time Gateway, and Redis Stream Telemetry Worker
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

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
# 5000: Flask Platform Hub
# 8000: FastAPI Gateway / WebSockets
EXPOSE 5000 8000

# Default command runs the Flask Platform Hub via Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2"]

