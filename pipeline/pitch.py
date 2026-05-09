"""
Stage 4 — Pitch Estimator
aerial image + lat/lon → { pitch_x_12, pitch_multiplier, method, confidence }

Method hierarchy:
  1. Claude Vision LLM  — reads shadows / perspective from aerial tile
  2. Regional defaults  — state-level priors (last resort)
"""

import base64
import json
import os
from pathlib import Path


# Standard pitch → slope multiplier table (NRCA)
PITCH_MULTIPLIER: dict[int, float] = {
    2: 1.014, 3: 1.031, 4: 1.054, 5: 1.083,
    6: 1.118, 7: 1.158, 8: 1.202, 9: 1.250,
    10: 1.302, 11: 1.357, 12: 1.414,
}

# State-level pitch priors based on regional building norms
STATE_PITCH_DEFAULTS: dict[str, int] = {
    "TX": 6, "FL": 4, "CA": 5, "AZ": 4,
    "CO": 6, "UT": 6, "NM": 4,
    "MO": 7, "IL": 7, "OH": 7, "IN": 7,
    "VA": 7, "NC": 7, "GA": 6, "SC": 6,
    "NY": 8, "PA": 8, "MA": 9, "CT": 8,
    "WA": 7, "OR": 6,
}
DEFAULT_PITCH = 6


def estimate_pitch(image_bytes: bytes, lat: float, lon: float, state: str | None = None) -> dict:
    """
    Returns pitch estimate. Always succeeds — falls back to regional default.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and api_key != "paste-your-key-here" and image_bytes:
        result = _vision_llm(image_bytes, api_key)
        if result:
            return result

    return _regional_default(state, lat, lon)


# ── Vision LLM ────────────────────────────────────────────────────────────────

def _vision_llm(image_bytes: bytes, api_key: str) -> dict | None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Detect media type
        media_type = "image/jpeg"
        if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            media_type = "image/png"

        img_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        prompt = """You are a roofing expert analysing a top-down aerial satellite image of a residential property.

Estimate the dominant roof pitch (rise:12 run).

Look for:
- Shadow length cast by the roof ridge relative to the roof's visible width
- Apparent foreshortening of roof faces (steep roofs show less face area from above)
- Visible gable triangles at the ends of the house
- Ridge line compared to eave width

Common US residential pitches:
- 4:12  low slope (ranch / bungalow)
- 6:12  moderate (most common)
- 8:12  steep (colonial / craftsman)
- 10:12 very steep
- 12:12 extremely steep (rare)

Respond with ONLY valid JSON, no commentary:
{"pitch": 6, "confidence": 0.80, "reasoning": "brief one-sentence explanation"}

pitch must be an integer between 2 and 12."""

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=120,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        pitch = max(2, min(12, int(data["pitch"])))
        return {
            "pitch_x_12": pitch,
            "pitch_multiplier": PITCH_MULTIPLIER.get(pitch, 1.118),
            "method": "vision_llm",
            "confidence": float(data.get("confidence", 0.75)),
            "reasoning": data.get("reasoning", ""),
        }
    except Exception as e:
        return None


# ── Regional default ──────────────────────────────────────────────────────────

def _regional_default(state: str | None, lat: float, lon: float) -> dict:
    pitch = DEFAULT_PITCH
    if state:
        pitch = STATE_PITCH_DEFAULTS.get(state.upper(), DEFAULT_PITCH)
    else:
        # Crude lat-based heuristic: northern latitudes trend steeper
        if lat > 40:
            pitch = 8
        elif lat > 35:
            pitch = 7
        else:
            pitch = 6

    return {
        "pitch_x_12": pitch,
        "pitch_multiplier": PITCH_MULTIPLIER.get(pitch, 1.118),
        "method": "regional_default",
        "confidence": 0.45,
        "reasoning": f"Regional default for {'state ' + state if state else 'lat ' + str(round(lat, 1))}",
    }


if __name__ == "__main__":
    import sys
    img_path, lat, lon = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    with open(img_path, "rb") as f:
        img = f.read()
    r = estimate_pitch(img, lat, lon)
    print(f"pitch={r['pitch_x_12']}:12  multiplier={r['pitch_multiplier']}  method={r['method']}  confidence={r['confidence']:.2f}")
    print(f"reasoning: {r['reasoning']}")
