#!/bin/bash
# 👾 Pixora Retro Arcade Server Launcher

# Exit on error
set -e

# Define project root and virtual environment path
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "⚡ Booting Pixora Simulation Core..."

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    echo "⚡ Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
else
    echo "⚠️  No local virtual environment (.venv) detected. Running with system python..."
fi

# Run data migration to populate tables from legacy database if needed
echo "⚡ Synchronizing database telemetry & game catalog..."
python3 -m app.utils.migrate_data
python3 -m app.utils.seed_games

# Launch the Flask application
echo "⚡ Starting web server on http://localhost:5000..."
python3 app.py
