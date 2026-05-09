#!/usr/bin/env bash
#
# Build a clean tarball of the project for AirDrop / scp transfer to your
# personal laptop (or directly to EC2). Excludes secrets, virtual envs,
# node_modules, model weights, MS tile caches, and pipeline outputs.
#
# Usage (run from repo root):
#   bash deploy/make-transfer-archive.sh
#
# Result:
#   /Users/.../Sats/RoofEstimate-transfer.tgz   (~5–10 MB)

set -euo pipefail

REPO_NAME="$(basename "$PWD")"
PARENT_DIR="$(dirname "$PWD")"
OUTPUT="${PARENT_DIR}/${REPO_NAME}-transfer.tgz"

cd "$PARENT_DIR"

tar czf "$OUTPUT" \
  --exclude="${REPO_NAME}/venv" \
  --exclude="${REPO_NAME}/.venv" \
  --exclude="${REPO_NAME}/ui/node_modules" \
  --exclude="${REPO_NAME}/ui/dist" \
  --exclude="${REPO_NAME}/ui/.vite" \
  --exclude="${REPO_NAME}/ui/.tanstack" \
  --exclude="${REPO_NAME}/weights" \
  --exclude="${REPO_NAME}/data/ms_buildings_cache" \
  --exclude="${REPO_NAME}/data/footprints" \
  --exclude="${REPO_NAME}/data/ms_footprints" \
  --exclude="${REPO_NAME}/outputs/debug" \
  --exclude="${REPO_NAME}/outputs/calibration" \
  --exclude="${REPO_NAME}/outputs/integrated" \
  --exclude="${REPO_NAME}/outputs/test_results" \
  --exclude="${REPO_NAME}/outputs/test_vision" \
  --exclude="${REPO_NAME}/outputs/grounded_sam_visualizations" \
  --exclude="${REPO_NAME}/outputs/grounding_dino_test_results.json" \
  --exclude="${REPO_NAME}/outputs/grounded_sam_test_results.json" \
  --exclude="${REPO_NAME}/outputs/cli" \
  --exclude="${REPO_NAME}/outputs/visualizations" \
  --exclude="${REPO_NAME}/outputs/validation" \
  --exclude="${REPO_NAME}/outputs/validation_run.log" \
  --exclude="${REPO_NAME}/outputs/line_items_comparison.json" \
  --exclude="${REPO_NAME}/.env" \
  --exclude="${REPO_NAME}/.env.local" \
  --exclude="${REPO_NAME}/.DS_Store" \
  --exclude="${REPO_NAME}/.claude" \
  --exclude="${REPO_NAME}/.cursor" \
  --exclude="${REPO_NAME}/.vscode" \
  --exclude="${REPO_NAME}/.git" \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.swp' \
  "$REPO_NAME"

SIZE_HUMAN="$(du -h "$OUTPUT" | cut -f1)"
echo
echo "✓ Created: $OUTPUT  ($SIZE_HUMAN)"
echo
echo "Next:"
echo "  1. AirDrop $OUTPUT to your personal laptop"
echo "  2. On the laptop: tar xzf ${REPO_NAME}-transfer.tgz"
echo "  3. cd ${REPO_NAME} && git init && git add . && git commit -m 'Initial RoofEstimate commit'"
echo "  4. Create the empty repo on github.com/CapriSats/RoofEstimate (Safari)"
echo "  5. git remote add origin git@github.com:CapriSats/RoofEstimate.git"
echo "  6. git push -u origin main"
