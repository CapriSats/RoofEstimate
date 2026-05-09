# RoofEstimate — AI-Powered Roof Measurement System

> Get accurate roof measurements and cost estimates from just an address. Multi-source data fusion with transparent provenance for every calculation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 Overview

RoofEstimate is an AI-powered system that provides accurate roof measurements and cost estimates using multi-source data fusion. It combines:

- **Google Solar API** - 3D building segments and pitch data
- **Microsoft Building Footprints** - Open ML-derived building polygons
- **OpenStreetMap** - Community-mapped building data
- **Claude Vision AI** - Aerial image analysis for pitch estimation
- **Custom Computer Vision** - Grounded-SAM for footprint detection

The system transparently shows which data source was used and validates results through cross-checking multiple sources.

---

## ✨ Features

### Core Capabilities
- ⚡ **Fast Estimates** - Full measurement in under 5 seconds
- 🎯 **High Accuracy** - Typically within 10% of actual measurements
- 🔍 **Multi-Source Validation** - Cross-checks between multiple data sources
- 📊 **Transparent Provenance** - Shows exactly where each number came from
- 💰 **Tiered Pricing** - Good/Better/Best material options with cost ranges

### Technical Features
- 🌐 **Multi-Mode Operation**
  - **Fusion Mode**: Combines all sources with weighted scoring
  - **Solar Primary**: Uses Google Solar API with OSM fallback
  - **Build-Only**: Pure open-source computation without external APIs
- 🔄 **Real-Time Streaming** - Server-Sent Events for live progress updates
- 🎨 **Modern UI** - React + Vite with shadcn/ui components
- ☁️ **AWS Ready** - Complete EC2 deployment scripts with SSM secrets management

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20.19+ or 22+
- API Keys (at least one):
  - [Anthropic API](https://console.anthropic.com/) (for Claude Vision)
  - [Google AI API](https://makersuite.google.com/app/apikey) (for Gemini)
  - [Google Vision/Solar API](https://console.cloud.google.com/apis/credentials) (for Solar API)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/RoofEstimate.git
   cd RoofEstimate
   ```

2. **Set up Python environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure API keys**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Install UI dependencies**
   ```bash
   cd ui
   npm install
   cd ..
   ```

5. **Start the servers**
   ```bash
   # Terminal 1 - API Server
   PYTHONPATH=. venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

   # Terminal 2 - UI Dev Server
   cd ui
   npm run dev
   ```

6. **Open the application**
   - UI: http://localhost:3000 (or the port shown in terminal)
   - API: http://localhost:8000

---

## 📖 How It Works

### Data Fusion Pipeline

```
Address Input
    ↓
Geocoding (Nominatim)
    ↓
Aerial Imagery (ESRI/Mapbox)
    ↓
Multi-Source Measurement:
  ├─ Google Solar API (3D segments)
  ├─ OpenStreetMap (building footprints)
  ├─ MS Buildings (ML footprints)
  └─ Claude Vision (pitch from imagery)
    ↓
Fusion Algorithm (weighted by confidence)
    ↓
Cross-Validation
    ↓
Final Estimate with Provenance
```

### Measurement Modes

**Fusion Mode** (default)
- Queries all available sources
- Weights results by confidence scores
- Cross-validates build vs. external APIs
- Most accurate and transparent

**Solar Primary Mode**
- Uses Google Solar API as primary source
- Falls back to OSM if Solar unavailable
- Fastest for areas with Solar coverage

**Build-Only Mode**
- No external paid APIs
- Uses only open-source data (OSM, MS Buildings)
- Completely independent computation

---

## 🏗️ Architecture

### Backend (FastAPI)
- `api/main.py` - REST API with Server-Sent Events
- `pipeline/measurement.py` - Multi-source fusion orchestrator
- `pipeline/solar.py` - Google Solar API integration
- `pipeline/footprint.py` - Building footprint detection cascade
- `pipeline/pitch.py` - Roof pitch estimation (Vision LLM)
- `pipeline/estimate.py` - Cost estimation engine

### Frontend (React + Vite)
- Real-time progress tracking
- Interactive aerial imagery display
- Per-source breakdown visualization
- Tiered material pricing

### Computer Vision
- `pipeline/footprint_grounded_sam.py` - Grounding DINO + SAM for pixel-perfect segmentation
- `pipeline/footprint_grounding_dino.py` - Object detection for aerial imagery
- Geometric validation and multi-criteria ranking

---

## ☁️ AWS Deployment

Complete EC2 deployment with one command:

```bash
# 1. Launch EC2 instance
./launch-ec2.sh

# 2. Deploy code
./deploy-to-ec2.sh <EC2_PUBLIC_IP>

# 3. SSH and run setup
ssh -i roofestimate-key.pem ubuntu@<EC2_PUBLIC_IP>
cd ~/RoofEstimate
bash setup-ec2.sh
```

See [.aws-setup.md](.aws-setup.md) for detailed deployment guide.

---

## 📊 Accuracy

Tested on diverse property types across the US:

- **Average Error**: ~10% MAPE (Mean Absolute Percentage Error)
- **Best Case**: 3.2% error (Cape Coral, FL)
- **Cross-Validation**: Build path vs. Solar API typically within 10%

Results vary based on:
- Building complexity (simple gable vs. complex hip-and-valley)
- Data source coverage (Solar API available in ~60% of US)
- Image quality and resolution

---

## 🛠️ Configuration

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...      # Claude Vision for pitch
GOOGLE_AI_API_KEY=AIzaSy...       # Gemini Vision (alternative)
GOOGLE_VISION_API_KEY=AIzaSy...   # Google Solar API + imagery

# Optional
MAPBOX_TOKEN=...                  # Alternative imagery source
BING_MAPS_KEY=...                 # Alternative imagery source
```

### Runtime Configuration

Set measurement mode via API:

```bash
curl -X POST http://localhost:8000/settings \
  -H "Content-Type: application/json" \
  -d '{"solar_mode": "fusion"}'  # or "primary" or "off"
```

---

## 🧪 Testing

```bash
# Test measurement pipeline
PYTHONPATH=. python scripts/estimate.py "1600 Amphitheatre Parkway, Mountain View, CA"

# Test Grounded-SAM computer vision
PYTHONPATH=. python test_grounded_sam.py

# Run calibration tests
PYTHONPATH=. python scripts/calibrate.py
```

---

## 📁 Project Structure

```
RoofEstimate/
├── api/                    # FastAPI backend
├── pipeline/              # Measurement pipeline
│   ├── measurement.py     # Multi-source orchestrator
│   ├── solar.py          # Google Solar API
│   ├── footprint.py      # Building footprint cascade
│   ├── pitch.py          # Pitch estimation
│   └── estimate.py       # Cost calculation
├── ui/                   # React frontend
├── scripts/              # CLI tools and testing
├── data/                 # Calibration data
├── deploy/               # AWS deployment configs
├── .aws-setup.md         # Deployment guide
├── setup-ssm-secrets.sh  # AWS secrets management
├── launch-ec2.sh         # EC2 instance creation
└── deploy-to-ec2.sh      # Deployment automation
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **Google Solar API** - High-quality 3D building data
- **Microsoft Building Footprints** - Open ML-derived building polygons
- **OpenStreetMap** - Community-mapped building data
- **Anthropic Claude** - Vision AI for pitch estimation
- **Meta SAM** - Segment Anything Model for computer vision
- **IDEA Research** - Grounding DINO for object detection

---

## 📮 Contact

For questions or feedback, please open an issue on GitHub.
