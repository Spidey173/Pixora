#!/bin/bash
# Run the Pixora application

set -e

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source ".venv/bin/activate"
fi

if [ "$1" = "test" ]; then
    pytest
else
    python app.py
fi
