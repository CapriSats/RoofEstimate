#!/usr/bin/env bash
# Start the RoofEstimate FastAPI backend
# Usage: ./start-backend.sh   (from the repo root)

set -e
cd "$(dirname "$0")"

# Activate venv if present, otherwise use system python
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Install / sync deps (fast no-op if already installed)
pip install -r requirements.txt -q

echo ""
echo "  🏠  RoofEstimate Backend"
echo "  API:  http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo ""

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
