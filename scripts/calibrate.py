#!/usr/bin/env python3
"""
Calibration harness — run the pipeline on all 5 example properties
and compare outputs against Reference A and Reference B.

Usage:
    python scripts/calibrate.py

Output: formatted table + outputs/calibration/results.json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.measurement import measure_roof
from pipeline.config      import SOLAR_MODE

DATA_FILE = Path(__file__).parent.parent / "data" / "benchmarks.json"
OUT_DIR   = Path(__file__).parent.parent / "outputs" / "calibration"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_one(prop: dict) -> dict:
    address = prop["address"]
    state   = prop.get("state")
    print(f"\n  → {address}")

    t0 = time.time()
    m = measure_roof(address, state)
    elapsed = round(time.time() - t0, 1)

    final = m["final"]
    our_sqft = final["roof_sqft"]
    sources = m["sources"]

    # Per-source summary line so we can compare in the terminal
    src_solar = sources.get("google_solar")
    src_osm   = sources.get("osm")
    src_pitch = sources.get("vision_llm_pitch")
    print(
        f"    final={our_sqft} ({final['source']})  "
        f"solar={src_solar['roof_sqft'] if src_solar else '—'}  "
        f"osm_fp={src_osm['footprint_sqft'] if src_osm else '—'}  "
        f"vision_pitch={src_pitch['pitch_x_12'] if src_pitch else '—'}:12"
    )

    ref_a      = prop["ref_a_sqft"]
    ref_b      = prop["ref_b_sqft"]
    midpoint   = prop["midpoint"]
    err_pct    = round((our_sqft - midpoint) / midpoint * 100, 1)
    in_band    = prop["ref_b_sqft"] <= our_sqft <= prop["ref_a_sqft"] or abs(err_pct) <= prop["tolerance_pct"]

    return {
        "id":            prop["id"],
        "address":       address,
        "our_sqft":      our_sqft,
        "footprint_sqft": final["footprint_sqft"],
        "ref_a":         ref_a,
        "ref_b":         ref_b,
        "midpoint":      midpoint,
        "error_pct":     err_pct,
        "in_band":       in_band,
        "pitch_our":     f"{final['pitch_x_12']}:12",
        "pitch_ref":     prop.get("ref_pitch", "?"),
        "pitch_method":  final.get("method", final["source"]),
        "fp_source":     final["source"],
        "fp_confidence": final["confidence"],
        "mode":          m["mode"],
        "sources":       sources,
        "elapsed_s":     elapsed,
    }


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    print("=" * 70)
    print(f"CALIBRATION RUN — Roof Estimator Pipeline   (SOLAR_MODE={SOLAR_MODE})")
    print("=" * 70)

    results = []
    for prop in data["example_properties"]:
        try:
            r = run_one(prop)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            r = {"id": prop["id"], "address": prop["address"], "error": str(exc)}
        results.append(r)

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n")
    print(f"{'Address':<45} {'Ours':>6} {'Ref A':>6} {'Ref B':>6} {'Err%':>6} {'Band':>5} {'Pitch':>6}")
    print("-" * 85)
    passed = 0
    for r in results:
        if "error" in r:
            print(f"{r['address'][:44]:<45}  ERROR: {r['error']}")
            continue
        status = "✓" if r["in_band"] else "✗"
        if r["in_band"]:
            passed += 1
        print(
            f"{r['address'][:44]:<45} "
            f"{r['our_sqft']:>6,} "
            f"{r['ref_a']:>6,} "
            f"{r['ref_b']:>6,} "
            f"{r['error_pct']:>+6.1f}% "
            f"{status:>5}  "
            f"{r['pitch_our']:>6}"
        )

    print("-" * 85)
    print(f"Passed: {passed}/{len(results)} within ±{data['example_properties'][0]['tolerance_pct']}% of reference midpoint\n")

    # ── Save ──────────────────────────────────────────────────────────────────
    out_path = OUT_DIR / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved → {out_path}")

    return passed == len(results)


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
