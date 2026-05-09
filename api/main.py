"""
Roof Estimator API
POST /estimate         — full pipeline, streams progress via Server-Sent Events
GET  /estimate/{id}    — retrieve a stored result
GET  /settings         — read current pipeline settings (SOLAR_MODE)
POST /settings         — update pipeline settings (live, in-process)
GET  /health           — liveness check
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

# Make sure pipeline is importable when running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import config as pipeline_config
from pipeline.measurement import measure_roof
from pipeline.imagery import fetch_imagery, fetch_imagery_for_polygon
from pipeline.geocoder import geocode
from pipeline.estimate import generate_estimate
from pipeline.debug import annotate_polygon_on_image

app = FastAPI(title="Roof Estimator", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULTS: dict[str, dict] = {}


# ── request/response models ───────────────────────────────────────────────────

class EstimateRequest(BaseModel):
    address: str
    state: str | None = None
    waste_factor: float = 0.12
    roofer_profile: dict | None = None


class SettingsUpdate(BaseModel):
    solar_mode: Literal["off", "fusion", "primary"]


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/settings")
def get_settings():
    return {
        "solar_mode": pipeline_config.SOLAR_MODE,
        "solar_mode_options": ["off", "fusion", "primary"],
        "solar_mode_descriptions": {
            "off": "OSM polygon + Vision LLM pitch only. Pure 'build' path; lowest external dependence.",
            "fusion": "All sources (Solar API, OSM, Vision LLM) contribute; result is weighted-fused. Defensible build with multi-source computation.",
            "primary": "Solar API primary; OSM fallback. Highest accuracy, leans heavily on Google's data.",
        },
    }


@app.post("/settings")
def update_settings(update: SettingsUpdate):
    pipeline_config.SOLAR_MODE = update.solar_mode
    os.environ["SOLAR_MODE"] = update.solar_mode
    return {"solar_mode": pipeline_config.SOLAR_MODE}


@app.post("/estimate")
async def estimate(req: EstimateRequest):
    return StreamingResponse(
        _run_pipeline(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/estimate/{estimate_id}")
def get_estimate(estimate_id: str):
    result = RESULTS.get(estimate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return result


# ── pipeline orchestrator ─────────────────────────────────────────────────────

async def _run_pipeline(req: EstimateRequest) -> AsyncIterator[str]:

    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"

    estimate_id = str(uuid.uuid4())[:8]

    try:
        # ── Stage 1: Geocoding ──────────────────────────────────────────────
        yield event({"stage": "geocoding", "status": "running", "label": "Locating address…"})
        await asyncio.sleep(0)
        geo = await asyncio.to_thread(geocode, req.address)
        lat, lon = geo["lat"], geo["lon"]
        yield event({
            "stage": "geocoding", "status": "done",
            "detail": f"{lat:.5f}, {lon:.5f} via {geo['source']}",
            "lat": lat, "lon": lon,
        })

        # ── Stage 2: Imagery ────────────────────────────────────────────────
        yield event({"stage": "imagery", "status": "running", "label": "Fetching aerial image…"})
        await asyncio.sleep(0)
        img_data = await asyncio.to_thread(fetch_imagery, lat, lon)
        yield event({
            "stage": "imagery", "status": "done",
            "detail": f"{img_data['meters_per_pixel']:.2f} m/px via {img_data['source']}",
            "image_base64": _img_b64(img_data["image_bytes"]),
        })

        # ── Stage 3+4: Measurement (Solar / OSM / Vision LLM) ───────────────
        yield event({
            "stage": "footprint", "status": "running",
            "label": f"Measuring roof (mode={pipeline_config.SOLAR_MODE})…",
        })
        await asyncio.sleep(0)
        state = req.state or _state_from_address(req.address)
        m = await asyncio.to_thread(measure_roof, req.address, state)
        final = m["final"]
        sources = m["sources"]

        yield event({
            "stage": "footprint", "status": "done",
            "detail": (
                f"{final['footprint_sqft']:,} sqft footprint via {final['source']} "
                f"(confidence {final['confidence']:.0%})"
            ),
            "footprint_sqft": final["footprint_sqft"],
            "source": final["source"],
            "confidence": final["confidence"],
        })

        # Pitch as a separate UI stage even though measurement.py runs them together
        yield event({"stage": "pitch", "status": "running", "label": "Estimating roof pitch…"})
        await asyncio.sleep(0)
        yield event({
            "stage": "pitch", "status": "done",
            "detail": f"{final['pitch_x_12']}:12 via {final.get('method', final['source'])}",
            "pitch_x_12": final["pitch_x_12"],
        })

        # ── Stage 5: Area (already computed inside measure_roof) ────────────
        yield event({"stage": "area", "status": "running", "label": "Calculating roof area…"})
        await asyncio.sleep(0)
        yield event({
            "stage": "area", "status": "done",
            "detail": f"{final['roof_sqft']:,} sqft roof area",
            "roof_sqft": final["roof_sqft"],
        })

        # ── Sources panel: emit detailed per-source breakdown for UI transparency ──
        yield event({
            "stage": "sources", "status": "done",
            "mode": m["mode"],
            "sources": sources,
            "final_source": final["source"],
            "annotated_image": m.get("annotated_image"),
            "cropped_image": m.get("cropped_image"),
            "polygon_meta": m.get("polygon_meta"),
        })

        # ── Stage 6: Estimate ───────────────────────────────────────────────
        yield event({"stage": "estimate", "status": "running", "label": "Building your estimate…"})
        await asyncio.sleep(0)
        est = generate_estimate(
            final["roof_sqft"],
            final["pitch_x_12"],
            state=state or "national",
            waste_factor=req.waste_factor,
            roofer_profile=req.roofer_profile,
        )
        yield event({"stage": "estimate", "status": "done", "detail": "Estimate complete"})

        # ── Complete ────────────────────────────────────────────────────────
        result = {
            "id":         estimate_id,
            "address":    req.address,
            "geocode":    {"lat": lat, "lon": lon, "source": geo["source"]},
            "footprint":  {"sqft": final["footprint_sqft"], "source": final["source"], "confidence": final["confidence"]},
            "pitch":      {"x_12": final["pitch_x_12"], "method": final.get("method", final["source"])},
            "area":       {"roof_sqft": final["roof_sqft"]},
            "estimate":   est,
            "mode":       m["mode"],
            "sources":    sources,
            "final_source": final["source"],
            "method":     final.get("method"),
            "cross_check": final.get("cross_check"),
            "annotated_image": m.get("annotated_image"),
            "polygon_meta": m.get("polygon_meta"),
            "warning":    final.get("warning"),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        RESULTS[estimate_id] = result
        yield event({"stage": "complete", "id": estimate_id, "result": result})

    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield event({"stage": "error", "message": str(exc)})


# ── helpers ───────────────────────────────────────────────────────────────────

def _img_b64(image_bytes: bytes) -> str:
    import base64
    return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()


def _state_from_address(address: str) -> str | None:
    import re
    m = re.search(r"\b([A-Z]{2})\s+\d{5}", address)
    return m.group(1) if m else None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
