#!/usr/bin/env bash
# Start the RoofEstimate React frontend
# Usage: ./start-ui.sh   (from the repo root)

set -e
cd "$(dirname "$0")/ui"

# Install deps if node_modules is missing
if [ ! -d "node_modules" ] || [ ! -d "node_modules/@tanstack" ]; then
  echo "Installing frontend dependencies…"
  npm install
fi

echo ""
echo "  🏠  RoofEstimate UI"
echo "  App: http://localhost:3000"
echo "  Backend must be running on http://localhost:8000"
echo ""

npm run dev
