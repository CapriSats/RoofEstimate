#!/usr/bin/env bash
#
# RoofEstimate — one-shot EC2 setup
#
# Run as the default user (ubuntu) on a fresh Ubuntu 24.04 instance:
#   curl -O https://raw.githubusercontent.com/CapriSats/RoofEstimate/main/deploy/setup.sh
#   bash setup.sh
#
# Or after cloning:
#   cd RoofEstimate && bash deploy/setup.sh
#
# What it installs:
#   - Python 3.11 + venv with pipeline dependencies
#   - Node.js 20 + UI build dependencies (built once into ./ui/dist)
#   - nginx (reverse proxy: /api/ → uvicorn, / → UI build)
#   - systemd unit for the FastAPI backend (auto-restart, journald logs)
#
# Idempotent — safe to re-run.

set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/RoofEstimate}"
SERVICE_USER="${SERVICE_USER:-$USER}"

log() { printf '\n\e[1;36m== %s ==\e[0m\n' "$*"; }

# ── 1. System packages ───────────────────────────────────────────────────────
log "Installing system packages"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3.11 python3.11-venv python3.11-dev \
  build-essential pkg-config \
  libgeos-dev libproj-dev \
  nginx git curl ca-certificates

# ── 2. Node.js 20 (for the UI build only — not runtime) ──────────────────────
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v)" != v20* ]]; then
  log "Installing Node.js 20"
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

# ── 3. Repo ──────────────────────────────────────────────────────────────────
if [ ! -d "$REPO_DIR/.git" ]; then
  log "Repo missing at $REPO_DIR — clone it first, then re-run this script"
  echo "    git clone https://github.com/CapriSats/RoofEstimate.git $REPO_DIR"
  exit 1
fi
cd "$REPO_DIR"

# ── 4. Python venv + pipeline deps ───────────────────────────────────────────
log "Setting up Python venv"
if [ ! -d venv ]; then
  python3.11 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# ── 5. UI production build ───────────────────────────────────────────────────
log "Building UI"
cd ui
if [ ! -d node_modules ]; then
  npm install --no-audit --no-fund
fi
# Tell Vite to call /api/* (nginx-rewritten to uvicorn) in the production build.
# Dev mode keeps using http://localhost:8000 from the unset default.
echo 'VITE_API_URL=/api' > .env.production
npm run build
cd ..

# ── 6. .env scaffold ─────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  log "Creating .env from template — EDIT THIS NEXT"
  cp deploy/.env.template .env
  echo "  Now run:  nano $REPO_DIR/.env"
fi

# ── 7. systemd service for the API ───────────────────────────────────────────
log "Installing systemd unit roof-api"
sudo tee /etc/systemd/system/roof-api.service >/dev/null <<UNIT
[Unit]
Description=RoofEstimate FastAPI backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${REPO_DIR}/.env
ExecStart=${REPO_DIR}/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable roof-api

# ── 8. nginx reverse proxy ───────────────────────────────────────────────────
log "Installing nginx config"
sudo cp deploy/nginx.conf /etc/nginx/sites-available/roof
sudo ln -sf /etc/nginx/sites-available/roof /etc/nginx/sites-enabled/roof
sudo rm -f /etc/nginx/sites-enabled/default
# Substitute the actual repo path into the nginx config
sudo sed -i "s|__UI_BUILD_DIR__|${REPO_DIR}/ui/dist|g" /etc/nginx/sites-available/roof
sudo nginx -t

log "Setup complete."
cat <<EOF

Next steps:

  1. Edit .env with your API keys:
       nano ${REPO_DIR}/.env
     Required: ANTHROPIC_API_KEY, GOOGLE_VISION_API_KEY
     Optional: MAPBOX_TOKEN, BING_MAPS_KEY

  2. Start the services:
       sudo systemctl start roof-api
       sudo systemctl restart nginx

  3. Tail logs to verify:
       sudo journalctl -u roof-api -f

  4. Visit  http://<EC2-public-ip>/  in a browser.

EOF
