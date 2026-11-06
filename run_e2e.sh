#!/usr/bin/env bash
# Pixora E2E Headless Browser Test Runner
set -e

echo "================================================================"
echo "🕹️  Pixora Platform: Playwright Headless Browser E2E Test Suite"
echo "================================================================"

# Verify Playwright is installed
if ! command -v playwright &> /dev/null && ! python -c "import playwright" 2>/dev/null; then
    echo "⚠️  Playwright not detected. Installing dependencies..."
    pip install playwright
    playwright install chromium
fi

echo "Running end-to-end tests against real sandboxed iframes & SDK v2..."
pytest tests/test_headless_browser_sdk.py -v -s
