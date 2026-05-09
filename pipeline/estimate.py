"""
Stage 6 — Estimate Engine
roof_sqft + pitch + state → { tiers: [good, better, best], measurements }

Pure function — no I/O. Takes measurements, returns a structured quote payload.
Pricing loaded from config/catalog.json at import time.
"""

import json
from pathlib import Path
from datetime import date, timedelta

CONFIG_PATH = Path(__file__).parent.parent / "config" / "catalog.json"


def _load_catalog() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return _default_catalog()


def generate_estimate(
    roof_sqft: float,
    pitch_x_12: int,
    state: str = "national",
    waste_factor: float = 0.12,
    roofer_profile: dict | None = None,
) -> dict:
    """
    Returns a full estimate payload with three tiers (good / better / best).
    """
    catalog = _load_catalog()
    regional = catalog["regional_factors"].get(state.upper(), 1.0)
    pitch_labor_factor = _pitch_labor_factor(pitch_x_12)
    billable_sqft = roof_sqft * (1 + waste_factor)
    valid_until = (date.today() + timedelta(days=30)).isoformat()

    tiers = {}
    for tier_name, mat in catalog["tiers"].items():
        material_cost  = billable_sqft * mat["material_per_sqft"]
        supplementary  = roof_sqft * catalog["supplementary_per_sqft"]
        labor_cost     = roof_sqft * catalog["base_labor_per_sqft"] * pitch_labor_factor * regional
        tearoff        = roof_sqft * catalog["tearoff_per_sqft"]
        disposal       = roof_sqft * catalog["disposal_per_sqft"]
        permit         = catalog["permit_allowance"]

        subtotal = material_cost + supplementary + labor_cost + tearoff + disposal + permit
        low      = round(subtotal * 0.92 / 100) * 100
        mid      = round(subtotal / 100) * 100
        high     = round(subtotal * 1.10 / 100) * 100

        tiers[tier_name] = {
            "label":           mat["label"],
            "warranty":        mat["warranty"],
            "material_cost":   round(material_cost),
            "supplementary":   round(supplementary),
            "labor_cost":      round(labor_cost),
            "tearoff":         round(tearoff),
            "disposal":        round(disposal),
            "permit":          permit,
            "subtotal":        mid,
            "range_low":       low,
            "range_high":      high,
        }

    return {
        "tiers":          tiers,
        "roof_sqft":      round(roof_sqft),
        "pitch_x_12":     pitch_x_12,
        "waste_factor":   waste_factor,
        "regional_factor": regional,
        "valid_until":    valid_until,
        "roofer":         roofer_profile or catalog.get("default_roofer", {}),
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _pitch_labor_factor(pitch: int) -> float:
    """NRCA pitch difficulty multiplier for labor."""
    if pitch <= 6:  return 1.00
    if pitch <= 8:  return 1.15
    if pitch <= 10: return 1.40
    if pitch <= 12: return 1.65
    return 1.90


def _default_catalog() -> dict:
    return {
        "tiers": {
            "good": {
                "label": "Good — 3-Tab Asphalt",
                "material_per_sqft": 1.20,
                "warranty": "25 year",
            },
            "better": {
                "label": "Better — Architectural",
                "material_per_sqft": 1.80,
                "warranty": "30–50 year",
            },
            "best": {
                "label": "Best — Designer / Impact",
                "material_per_sqft": 3.50,
                "warranty": "Lifetime",
            },
        },
        "supplementary_per_sqft": 0.65,
        "base_labor_per_sqft":    1.75,
        "tearoff_per_sqft":       1.20,
        "disposal_per_sqft":      0.60,
        "permit_allowance":       350,
        "regional_factors": {
            "TX": 0.95, "FL": 1.05, "CA": 1.30, "NY": 1.35,
            "CO": 1.05, "MO": 0.90, "VA": 1.00, "IL": 1.05,
        },
        "default_roofer": {
            "name":    "Acme Roofing",
            "phone":   "(555) 000-0000",
            "license": "ROC-000000",
            "logo":    None,
        },
    }


if __name__ == "__main__":
    import sys, pprint
    sqft  = float(sys.argv[1]) if len(sys.argv) > 1 else 2500
    pitch = int(sys.argv[2])   if len(sys.argv) > 2 else 6
    state = sys.argv[3]        if len(sys.argv) > 3 else "TX"
    pprint.pprint(generate_estimate(sqft, pitch, state))
