#!/bin/bash
# 👾 Pixora 2.0 Real-Time Arcade Launcher
# Usage:
#   ./run.sh           -> Starts Flask Web Platform (default)
#   ./run.sh worker    -> Starts Redis Streams Ingestion Worker (worker.py)
#   ./run.sh gateway   -> Starts FastAPI Real-Time WebSocket Gateway (gateway.py)
#   ./run.sh frontend  -> Starts Next.js 15 App Router Frontend
#   ./run.sh test      -> Runs pytest test suite (47 tests)
#   ./run.sh loadtest  -> Runs Locust 10k req/sec benchmark

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# Activate virtual environment if present
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

MODE="${1:-web}"

case "$MODE" in
    worker)
        echo "⚡ Launching Pixora 2.0 Distributed Telemetry Ingestion Worker..."
        exec python3 worker.py --worker-name=worker-1 --batch-size=50
        ;;
    gateway)
        echo "⚡ Launching FastAPI Real-Time & WebSocket Gateway on http://localhost:8000..."
        exec uvicorn gateway:app --host 0.0.0.0 --port 8000 --reload
        ;;
    frontend)
        echo "⚡ Launching Next.js 15 Client on http://localhost:3000..."
        cd "$PROJECT_DIR/frontend"
        exec npm run dev
        ;;
    test)
        echo "⚡ Running Pytest Test Suite..."
        exec pytest
        ;;
    loadtest)
        echo "⚡ Launching High-Throughput Locust Benchmark..."
        exec locust -f load_tests/locustfile.py --host=http://127.0.0.1:5000
        ;;
    web|*)
        echo "⚡ Booting Pixora 2.0 Simulation Core..."
        python3 -m app.utils.migrate_data
        python3 -m app.utils.seed_games
        echo "⚡ Starting web platform on http://localhost:5000..."
        exec python3 app.py
        ;;
esac
