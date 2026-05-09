"""
Stage 6 — Estimate Engine (SKU-level line items)

Takes measurement output → returns a structured quote payload with three
tiers (good / better / best). Each tier emits a list of SKU-level line items
(architectural shingles in bundles, drip edge in linear feet, tear-off labor
in squares, etc.) — the level of detail a roofer actually quotes from.

Pure function — no I/O. Pricing loaded from config/catalog.json at import time.

Why SKU-level instead of bucket totals:
  Bucket totals ($X material / $Y labor) tell a homeowner what to pay,
  but they don't tell a contractor what to ORDER. Roofers quote at the
  SKU level: "63 bundles of architectural shingles, 7 rolls of synthetic
  underlayment, 280 LF of drip edge." This module emits both — the
  itemized list a contractor uses for procurement, and a roll-up by
  category for the homeowner-facing summary.

Inputs (signature back-compatible — all new args optional):
  - roof_sqft       (float)
  - pitch_x_12      (int)
  - state           (str, default "national") — for regional labor factor
  - waste_factor    (float | None) — if None, computed from pitch + complexity
  - perimeter_lf    (float | None) — if provided, exact LF math; else estimated
  - num_segments    (int) — Solar facet count, drives roof-style heuristic
  - roofer_profile  (dict | None) — branding info for the quote
"""

import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from pipeline.linear_measurements import estimate_linear_measurements

CONFIG_PATH = Path(__file__).parent.parent / "config" / "catalog.json"


# ──────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────
def generate_estimate(
    roof_sqft: float,
    pitch_x_12: int,
    state: str = "national",
    waste_factor: Optional[float] = None,
    perimeter_lf: Optional[float] = None,
    num_segments: int = 0,
    roofer_profile: Optional[dict] = None,
) -> dict:
    catalog = _load_catalog()
    regional = catalog["regional_factors"].get(state.upper(), 1.0)
    pitch_labor_factor = _pitch_labor_factor(pitch_x_12)

    # Linear measurements (eaves, ridge, hip, valley, rake) — derived once,
    # consumed by every tier's line items.
    lin = estimate_linear_measurements(
        roof_sqft=roof_sqft,
        pitch_x_12=pitch_x_12,
        num_segments=num_segments,
        perimeter_lf=perimeter_lf,
    )

    # Waste % — auto-computed from pitch + complexity unless caller overrides.
    if waste_factor is None:
        waste_factor = _compute_waste_factor(pitch_x_12, num_segments)

    squares = roof_sqft / 100.0
    squares_with_waste = squares * (1 + waste_factor)

    valid_until = (date.today() + timedelta(days=30)).isoformat()

    tiers = {}
    for tier_id, tier_def in catalog["tiers"].items():
        items = _generate_line_items(
            tier_def=tier_def,
            roof_sqft=roof_sqft,
            squares=squares,
            squares_with_waste=squares_with_waste,
            lin=lin,
            pitch_labor_factor=pitch_labor_factor,
            regional=regional,
            catalog=catalog,
        )
        subtotals = _by_category(items)
        subtotal_raw = sum(subtotals.values())
        subtotal = round(subtotal_raw / 100) * 100  # round to nearest $100
        low = round(subtotal_raw * 0.92 / 100) * 100
        high = round(subtotal_raw * 1.10 / 100) * 100

        tiers[tier_id] = {
            "label": tier_def["label"],
            "warranty": tier_def["warranty"],
            "line_items": items,
            "subtotals_by_category": subtotals,
            "subtotal": subtotal,
            "range_low": low,
            "range_high": high,
            # legacy bucket fields kept so older UI/clients don't break
            "material_cost": subtotals.get("materials", 0),
            "supplementary": 0,
            "labor_cost": subtotals.get("labor", 0),
            "tearoff": _line_subtotal(items, "tearoff"),
            "disposal": _line_subtotal(items, "disposal"),
            "permit": subtotals.get("permit", 0),
        }

    return {
        "tiers": tiers,
        "roof_sqft": round(roof_sqft),
        "pitch_x_12": pitch_x_12,
        "linear_measurements": lin,
        "waste_factor": round(waste_factor, 3),
        "waste_rationale": _waste_rationale(pitch_x_12, num_segments, waste_factor),
        "regional_factor": regional,
        "valid_until": valid_until,
        "roofer": roofer_profile or catalog.get("default_roofer", {}),
    }


# ──────────────────────────────────────────────────────────────────────
# Line item generation
# ──────────────────────────────────────────────────────────────────────
def _generate_line_items(
    tier_def: dict,
    roof_sqft: float,
    squares: float,
    squares_with_waste: float,
    lin: dict,
    pitch_labor_factor: float,
    regional: float,
    catalog: dict,
) -> list[dict]:
    items: list[dict] = []

    # ── Materials ─────────────────────────────────────────────────────

    # Primary shingle — bundles per square varies by tier (designer = thicker)
    bundles = math.ceil(squares_with_waste * tier_def["bundles_per_square"])
    items.append(_li(
        "materials", tier_def["sku"], tier_def["label"],
        bundles, "bundle", tier_def["bundle_price"],
    ))

    # Synthetic underlayment — 1 roll per ~10 squares (10 sq @ 1000 sqft)
    underlayment = max(1, math.ceil(squares_with_waste / 10.0))
    items.append(_li(
        "materials", "underlayment_synthetic", "Synthetic underlayment",
        underlayment, "roll", catalog["underlayment_per_roll"],
    ))

    # Ice & water shield — eave courses; 1 roll covers ~70 LF in 36" course
    iws_rolls = max(1, math.ceil(lin["eaves_lf"] / 70.0))
    items.append(_li(
        "materials", "ice_water_shield", "Ice & water shield (eave courses)",
        iws_rolls, "roll", catalog["ice_water_shield_per_roll"],
    ))

    # Drip edge — eaves + rakes
    drip_lf = lin["eaves_lf"] + lin["rakes_lf"]
    items.append(_li(
        "materials", "drip_edge", "Drip edge — eaves + rakes",
        drip_lf, "linear ft", catalog["drip_edge_per_lf"],
    ))

    # Starter strip — eaves + rakes
    items.append(_li(
        "materials", "starter_strip", "Starter strip",
        drip_lf, "linear ft", catalog["starter_per_lf"],
    ))

    # Ridge cap shingles — ridge + hip
    ridge_cap_lf = lin["ridge_lf"] + lin["hip_lf"]
    if ridge_cap_lf > 0:
        items.append(_li(
            "materials", "ridge_cap_shingles", "Ridge cap shingles (ridge + hip)",
            ridge_cap_lf, "linear ft", catalog["ridge_cap_per_lf"],
        ))

    # Valley flashing — only if valleys present
    if lin["valley_lf"] > 0:
        items.append(_li(
            "materials", "valley_flashing", "Valley flashing (W-style metal)",
            lin["valley_lf"], "linear ft", catalog["valley_flashing_per_lf"],
        ))

    # Pipe boots / vents (typical residence)
    items.append(_li(
        "materials", "pipe_boots", "Pipe boots & vent flashings",
        3, "ea", catalog["pipe_boot_each"],
    ))

    # Roofing nails (1 box covers ~4 squares)
    nail_boxes = max(1, math.ceil(squares_with_waste / 4.0))
    items.append(_li(
        "materials", "roofing_nails", "Roofing nails (5 lb boxes)",
        nail_boxes, "box", catalog["nails_per_box"],
    ))

    # ── Labor ─────────────────────────────────────────────────────────
    items.append(_li(
        "labor", "tearoff", "Tear-off existing roof",
        round(squares, 1), "square",
        round(catalog["tearoff_per_square"] * regional, 2),
    ))

    items.append(_li(
        "labor", "install",
        f"Install new roof (pitch-adjusted, ×{pitch_labor_factor:.2f})",
        round(squares, 1), "square",
        round(catalog["install_per_square"] * pitch_labor_factor * regional, 2),
    ))

    items.append(_li(
        "labor", "disposal", "Dumpster + dump fees",
        1, "job", catalog["disposal_flat"],
    ))

    # ── Permit ────────────────────────────────────────────────────────
    items.append(_li(
        "permit", "permit_allowance", "Permit + inspection allowance",
        1, "job", catalog["permit_allowance"],
    ))

    return items


def _li(category: str, sku: str, description: str, qty, unit: str, unit_price: float) -> dict:
    """Build one line item with subtotal computed."""
    return {
        "category": category,
        "sku": sku,
        "description": description,
        "qty": qty,
        "unit": unit,
        "unit_price_usd": round(float(unit_price), 2),
        "subtotal_usd": round(float(qty) * float(unit_price), 2),
    }


def _by_category(items: list[dict]) -> dict[str, float]:
    cats: dict[str, float] = {}
    for it in items:
        cats[it["category"]] = round(cats.get(it["category"], 0.0) + it["subtotal_usd"], 2)
    return cats


def _line_subtotal(items: list[dict], sku: str) -> float:
    return round(sum(it["subtotal_usd"] for it in items if it["sku"] == sku), 2)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _pitch_labor_factor(pitch: int) -> float:
    """NRCA-style pitch difficulty multiplier for labor."""
    if pitch <= 6:
        return 1.00
    if pitch <= 8:
        return 1.15
    if pitch <= 10:
        return 1.40
    if pitch <= 12:
        return 1.65
    return 1.90


def _compute_waste_factor(pitch_x_12: int, num_segments: int) -> float:
    """
    Waste % derivation:
      - Base 10% (simple gable)
      - +1% per pitch level over 6:12   (steeper = harder cut alignment)
      - +1% per facet over 3            (more cuts at hips/valleys)
      Capped at 18%.
    """
    waste = 0.10
    if pitch_x_12 > 6:
        waste += min(0.04, (pitch_x_12 - 6) * 0.01)
    if num_segments > 3:
        waste += min(0.04, (num_segments - 3) * 0.01)
    return min(0.18, waste)


def _waste_rationale(pitch_x_12: int, num_segments: int, waste_factor: float) -> str:
    parts = ["base 10%"]
    if pitch_x_12 > 6:
        parts.append(f"+{min(4, pitch_x_12 - 6)}% pitch ({pitch_x_12}:12)")
    if num_segments > 3:
        parts.append(f"+{min(4, num_segments - 3)}% complexity ({num_segments} facets)")
    return " · ".join(parts) + f" → {round(waste_factor * 100)}%"


def _load_catalog() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return _default_catalog()


def _default_catalog() -> dict:
    return {
        "tiers": {
            "good": {
                "label": "Good — 3-Tab Asphalt",
                "sku": "shingles_3tab",
                "warranty": "25 year",
                "bundles_per_square": 3.0,
                "bundle_price": 28.00,
            },
            "better": {
                "label": "Better — Architectural (GAF Timberline HDZ)",
                "sku": "shingles_arch_gaf_hdz",
                "warranty": "30–50 year (Lifetime ltd)",
                "bundles_per_square": 3.0,
                "bundle_price": 38.00,
            },
            "best": {
                "label": "Best — Designer / Impact (CertainTeed Presidential)",
                "sku": "shingles_designer_ct_presidential",
                "warranty": "Lifetime",
                "bundles_per_square": 4.0,
                "bundle_price": 62.00,
            },
        },
        "underlayment_per_roll": 95.00,
        "ice_water_shield_per_roll": 78.00,
        "drip_edge_per_lf": 1.55,
        "starter_per_lf": 1.20,
        "ridge_cap_per_lf": 4.50,
        "valley_flashing_per_lf": 6.20,
        "pipe_boot_each": 32.00,
        "nails_per_box": 38.00,
        "tearoff_per_square": 65.00,
        "install_per_square": 95.00,
        "disposal_flat": 450.00,
        "permit_allowance": 350,
        "regional_factors": {
            "TX": 0.95, "FL": 1.05, "CA": 1.30, "NY": 1.35,
            "CO": 1.05, "MO": 0.90, "VA": 1.00, "IL": 1.05,
        },
        "default_roofer": {
            "name": "Acme Roofing",
            "phone": "(555) 000-0000",
            "license": "ROC-000000",
            "logo": None,
        },
    }


if __name__ == "__main__":
    import sys
    import pprint

    sqft = float(sys.argv[1]) if len(sys.argv) > 1 else 2500
    pitch = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    state = sys.argv[3] if len(sys.argv) > 3 else "TX"
    pprint.pprint(generate_estimate(sqft, pitch, state, num_segments=4))
