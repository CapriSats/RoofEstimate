#!/usr/bin/env python3
"""
Regenerate SUBMISSION.csv + SUBMISSION.json from the 5 hackathon test properties.

Runs the pipeline live against each property, captures full per-property output
(measurements + estimate with SKU line items), and writes both submission files
to the repo root.

Idempotent. Safe to re-run. Saves partial output if interrupted.
"""

import csv
import json
import sys
import time
import traceback
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file to get API keys
load_dotenv()

from pipeline.measurement import measure_roof
from pipeline.estimate import generate_estimate

REPO = Path(__file__).parent.parent

TEST_PROPERTIES = [
    ("t1", "3561 E 102nd Ct, Thornton, CO 80229",      "CO"),
    ("t2", "1612 S Canton Ave, Springfield, MO 65802", "MO"),
    ("t3", "6310 Laguna Bay Court, Houston, TX 77041", "TX"),
    ("t4", "3820 E Rosebrier St, Springfield, MO 65809","MO"),
    ("t5", "1261 20th Street, Newport News, VA 23607",  "VA"),
]


def run_one(pid: str, addr: str, state: str) -> dict:
    print(f"  → {pid}: {addr}", flush=True)
    t0 = time.time()
    m = measure_roof(addr, state)
    f = m["final"]
    est = generate_estimate(
        f["roof_sqft"],
        f["pitch_x_12"],
        state=state,
        perimeter_lf=f.get("perimeter_lf"),
        num_segments=f.get("num_segments", 0),
    )
    elapsed = round(time.time() - t0, 1)
    print(f"     ✓ sqft={f['roof_sqft']} pitch={f['pitch_x_12']}:12 method={f.get('method')} ({elapsed}s)", flush=True)
    return {
        "id": pid,
        "address": addr,
        "state": state,
        "roof_sqft": f["roof_sqft"],
        "footprint_sqft": f.get("footprint_sqft"),
        "pitch_x_12": f.get("pitch_x_12"),
        "perimeter_lf": f.get("perimeter_lf"),
        "num_segments": f.get("num_segments", 0),
        "confidence": f.get("confidence"),
        "method": f.get("method"),
        "final_source": f.get("source"),
        "cross_check": f.get("cross_check"),
        "sources_summary": m.get("sources"),
        "estimate": est,
    }


def main():
    print("=" * 72)
    print("Regenerating SUBMISSION artifacts (5 test properties)")
    print("=" * 72)

    out: list[dict] = []
    for idx, (pid, addr, state) in enumerate(TEST_PROPERTIES):
        try:
            out.append(run_one(pid, addr, state))
        except Exception as exc:
            print(f"     ✗ FAILED on {pid}: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
            # Save what we have so far and continue
            out.append({"id": pid, "address": addr, "state": state, "error": str(exc)})

        # Add 3-second delay between properties to avoid rate limiting
        if idx < len(TEST_PROPERTIES) - 1:
            print(f"     ⏳ Waiting 3 seconds before next property...", flush=True)
            time.sleep(3)

    # ── Write SUBMISSION.json (full per-property output) ────────────────
    submission_json_path = REPO / "SUBMISSION.json"
    submission_json_path.write_text(json.dumps({
        "submission": {
            "hackathon": "JobNimbus AI Hackathon 2026",
            "team": "CapriSats",
            "mode": "validated_build",
            "policy": (
                "Each property is computed two ways: BUILD PATH (Microsoft Building "
                "Footprints polygon × Vision LLM-derived pitch) and SOLAR cross-check "
                "(Google Solar API). When the two agree within 15%, the build path is "
                "submitted. When they diverge by more than 15%, Solar acts as a "
                "documented tiebreaker. Solar is a configurable provider "
                "(SOLAR_MODE=off|fusion|primary); pipeline runs without Solar when off."
            ),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "properties": out,
        }
    }, indent=2))
    print(f"\n✓ Wrote {submission_json_path.relative_to(REPO)}")

    # ── Write SUBMISSION.csv (just the 5 sqft values judges score) ──────
    submission_csv_path = REPO / "SUBMISSION.csv"
    with open(submission_csv_path, "w", newline="") as f:
        w = csv.writer(f)
        for p in out:
            w.writerow([p["id"], p["address"], p.get("roof_sqft", "ERROR")])
    print(f"✓ Wrote {submission_csv_path.relative_to(REPO)}")

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("SUMMARY — paste these into the submission form")
    print("=" * 72)
    for p in out:
        sqft = p.get("roof_sqft", "ERROR")
        method = p.get("method", "—")
        print(f"  {p['id']}  {p['address'][:45]:45s}  sqft={sqft:>5}  ({method})")
    print()


if __name__ == "__main__":
    main()
