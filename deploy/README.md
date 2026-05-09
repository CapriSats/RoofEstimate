# Deploying RoofEstimate to a public EC2 instance

A single-instance demo deploy. Total wall time ~15 minutes.

## Architecture

```
   Internet
       │  :80
       ▼
  ┌────────────┐
  │   nginx    │  (sites-available/roof)
  │            │
  │  /api/* ──►│ http://127.0.0.1:8000
  │            │       │
  │  /     ─►  │       ▼
  │  static    │  ┌──────────────┐
  │  /ui/dist  │  │  uvicorn     │
  └────────────┘  │  api.main:app│ ← systemd: roof-api.service
                  │  (Python 3.11│
                  │   venv)      │
                  └──────────────┘
```

UI is built once into `ui/dist` and served as static files.
API runs as a systemd service. nginx fronts everything on port 80.

## 1. Launch EC2

In the AWS Console (or `aws ec2 run-instances`):

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | `t3.medium` (4 GB RAM) — enough for demo. Bump to `t3.large` if MS tile cache grows. |
| Storage | 30 GB gp3 EBS |
| Key pair | Create or pick one you have the `.pem` for |
| VPC / subnet | Default VPC, any public subnet |
| Auto-assign public IP | **Yes** |
| Security group | New, with rules below |

**Security group inbound:**

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 22 | TCP | My IP | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP demo |
| 443 | TCP | 0.0.0.0/0 | (optional, for HTTPS later) |

After launch, allocate an **Elastic IP** and associate it with the instance,
so the URL doesn't change on stop/start.

## 2. SSH in and clone the repo

```bash
ssh -i ~/.ssh/<your-key>.pem ubuntu@<elastic-ip>
git clone https://github.com/CapriSats/RoofEstimate.git
cd RoofEstimate
```

(Public repo — no credentials needed.)

## 3. Run the setup script

```bash
bash deploy/setup.sh
```

This installs Python 3.11, Node.js 20, system libs (libgeos, libproj),
nginx, builds the UI, creates the venv, and installs the systemd service.
Idempotent — safe to re-run if anything goes wrong.

## 4. Configure secrets

```bash
nano .env
```

Paste at minimum:
```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_VISION_API_KEY=AIza...
SOLAR_MODE=fusion
```

The `GOOGLE_VISION_API_KEY` must have **Geocoding API**, **Solar API**, and
**Maps Static API** enabled in the GCP console (the project we tested
earlier already has all three enabled).

## 5. Start it

```bash
sudo systemctl start roof-api
sudo systemctl restart nginx
```

Check the API came up:
```bash
sudo journalctl -u roof-api -n 50 --no-pager
curl http://127.0.0.1:8000/health         # → {"status":"ok"}
curl http://127.0.0.1/health              # → {"status":"ok"} via nginx
```

Open `http://<elastic-ip>/` in a browser.

## 6. (Optional) HTTPS via Let's Encrypt

If you have a domain pointing at the Elastic IP:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d roof.example.com
```

certbot will edit the nginx config in place and set up auto-renewal.

## 7. Iteration loop

To deploy code changes:

```bash
cd ~/RoofEstimate
git pull
# Backend:
source venv/bin/activate
pip install -r requirements.txt --quiet
deactivate
sudo systemctl restart roof-api
# UI:
cd ui && npm install --no-audit --no-fund && npm run build && cd ..
sudo systemctl reload nginx
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `502 Bad Gateway` from nginx | uvicorn not running | `sudo systemctl status roof-api`; check `journalctl -u roof-api` |
| API returns 403 from Google | Solar / Geocoding API not enabled on the GCP project | Enable in console; takes a few minutes to propagate |
| `Could not geocode` | Address truly invalid, or all geocoders failed | Try a more canonical address format |
| UI loads but `/api/*` 404s | nginx upstream rewrite issue | Verify `/etc/nginx/sites-enabled/roof` has the `rewrite ^/api/(.*)$ /$1 break;` line |
| Out of memory during MS tile fetch | Large MS quadkey tile | Bump instance to `t3.large`, or pre-warm `data/ms_buildings_cache/` from a backup |

## Cost estimate (rough, us-east-1, May 2026)

| Item | Hourly | Monthly (24/7) |
|---|---|---|
| t3.medium | $0.0416 | $30 |
| 30 GB gp3 EBS | — | $2.40 |
| Elastic IP (when associated) | free | free |
| Data transfer out (10 GB) | — | $0.90 |
| **Total** | | **~$33/month** |

Stop the instance between demos and you pay only for EBS (~$2.50/month).
