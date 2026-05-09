#!/usr/bin/env python3
"""
A/B Validation for SKU Line Items Patch

Validates that the patch:
1. Maintains roof area accuracy (no regression)
2. Produces sensible line items with reasonable quantities
3. Generates linear measurements that align with Reference A/B data

Usage:
    python scripts/validate_patch.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.measurement import measure_roof
from pipeline.estimate import generate_estimate

# Reference linear measurements from benchmark-measurements.md
REFERENCE_LINEAR = {
    "ex1": {"ridge_hip": 141, "valley": 40, "rake": 101, "eave": 175},
    "ex2": {"ridge_hip": 400, "valley": 197, "rake": 121, "eave": 270},
    "ex3": {"ridge_hip": 142, "valley": 22, "rake": 51, "eave": 175},
    "ex4": {"ridge_hip": 241, "valley": 78, "rake": 0, "eave": 255},
    "ex5": {"ridge_hip": 232, "valley": 113, "rake": 50, "eave": 211},
}

DATA_FILE = Path(__file__).parent.parent / "data" / "benchmarks.json"

def validate_one(prop: dict) -> dict:
    """Run full pipeline + estimate on one property and validate outputs."""
    pid = prop["id"]
    address = prop["address"]
    state = prop.get("state")

    print(f"\n{'='*70}")
    print(f"Property {pid}: {address}")
    print('='*70)

    # Run measurement pipeline
    m = measure_roof(address, state)
    final = m["final"]

    # Generate estimate with new line items
    est = generate_estimate(
        final["roof_sqft"],
        final["pitch_x_12"],
        state=state,
        perimeter_lf=final.get("perimeter_lf"),
        num_segments=final.get("num_segments", 0),
    )

    # ── Validation 1: Roof area accuracy (no regression) ─────────────────
    our_sqft = final["roof_sqft"]
    ref_a = prop["ref_a_sqft"]
    ref_b = prop["ref_b_sqft"]
    midpoint = prop["midpoint"]
    error_pct = round((our_sqft - midpoint) / midpoint * 100, 1)
    in_band = abs(error_pct) <= prop["tolerance_pct"]

    print(f"\n✓ ROOF AREA ACCURACY:")
    print(f"  Our sqft:     {our_sqft:,}")
    print(f"  Ref A:        {ref_a:,}")
    print(f"  Ref B:        {ref_b:,}")
    print(f"  Midpoint:     {midpoint:,}")
    print(f"  Error:        {error_pct:+.1f}%")
    print(f"  Status:       {'✓ PASS' if in_band else '✗ FAIL'} (tolerance ±{prop['tolerance_pct']}%)")

    # ── Validation 2: Linear measurements vs Reference A/B ───────────────
    lm = est.get("linear_measurements", {})
    ref = REFERENCE_LINEAR.get(pid, {})

    print(f"\n✓ LINEAR MEASUREMENTS:")
    print(f"  Eaves:        {lm.get('eaves_lf', 0)} LF  (Ref A: {ref.get('eave', '?')} LF)")
    print(f"  Rakes:        {lm.get('rakes_lf', 0)} LF  (Ref A: {ref.get('rake', '?')} LF)")
    print(f"  Ridge:        {lm.get('ridge_lf', 0)} LF  (Ref A: {ref.get('ridge_hip', '?')} LF ridge+hip)")
    print(f"  Hip:          {lm.get('hip_lf', 0)} LF")
    print(f"  Valley:       {lm.get('valley_lf', 0)} LF  (Ref A: {ref.get('valley', '?')} LF)")
    print(f"  Total perim:  {lm.get('total_perimeter_lf', 0)} LF")
    print(f"  Method:       {lm.get('method', '?')}")

    # Calculate LF accuracy
    lf_checks = []
    if ref:
        our_ridge_hip = lm.get('ridge_lf', 0) + lm.get('hip_lf', 0)
        ref_ridge_hip = ref.get('ridge_hip', 0)
        if ref_ridge_hip > 0:
            ridge_hip_err = abs(our_ridge_hip - ref_ridge_hip) / ref_ridge_hip * 100
            lf_checks.append(("Ridge+Hip", our_ridge_hip, ref_ridge_hip, ridge_hip_err))

        our_valley = lm.get('valley_lf', 0)
        ref_valley = ref.get('valley', 0)
        if ref_valley > 0:
            valley_err = abs(our_valley - ref_valley) / ref_valley * 100
            lf_checks.append(("Valley", our_valley, ref_valley, valley_err))

    lf_pass = all(err < 30 for _, _, _, err in lf_checks)  # 30% tolerance for LF

    if lf_checks:
        print(f"\n  LF Accuracy:")
        for name, ours, ref_val, err in lf_checks:
            status = "✓" if err < 30 else "✗"
            print(f"    {name:12} {ours:5.0f} vs {ref_val:5.0f} → {err:+5.1f}% {status}")

    # ── Validation 3: Line items sanity checks ───────────────────────────
    better = est["tiers"]["better"]
    line_items = better.get("line_items", [])

    print(f"\n✓ LINE ITEMS ({len(line_items)} items):")
    print(f"  Total:        ${better['subtotal']:,}")

    # Group by category
    by_cat = {}
    for item in line_items:
        cat = item["category"]
        by_cat.setdefault(cat, []).append(item)

    for cat in ["materials", "labor", "permit"]:
        items = by_cat.get(cat, [])
        cat_total = sum(i["subtotal_usd"] for i in items)
        print(f"\n  {cat.upper()} (${cat_total:,.0f}):")
        for item in items:
            print(f"    {item['qty']:>6.0f} {item['unit']:<10} {item['description']:<45} @ ${item['unit_price_usd']:<7.2f} = ${item['subtotal_usd']:>8,.0f}")

    # Sanity checks
    checks = []

    # Check: shingles should be ~roof_sqft/100 * 3 bundles (3 bundles per square for architectural)
    shingle_items = [i for i in line_items if "shingle" in i["description"].lower() or i["sku"] == "shingles"]
    if shingle_items:
        shingle_bundles = sum(i["qty"] for i in shingle_items)
        expected_bundles = (our_sqft / 100) * 3 * 1.1  # 3 bundles/sq + 10% waste
        bundle_err = abs(shingle_bundles - expected_bundles) / expected_bundles * 100
        checks.append(("Shingle bundles", shingle_bundles, expected_bundles, bundle_err, 20))

    # Check: tear-off should be ~roof_sqft/100 squares
    tearoff_items = [i for i in line_items if "tear-off" in i["description"].lower() or "tearoff" in i["description"].lower()]
    if tearoff_items:
        tearoff_sq = sum(i["qty"] for i in tearoff_items)
        expected_sq = our_sqft / 100
        tearoff_err = abs(tearoff_sq - expected_sq) / expected_sq * 100
        checks.append(("Tear-off squares", tearoff_sq, expected_sq, tearoff_err, 10))

    print(f"\n  Sanity Checks:")
    items_pass = all(err < tol for _, _, _, err, tol in checks)
    for name, ours, exp, err, tol in checks:
        status = "✓" if err < tol else "✗"
        print(f"    {name:20} {ours:>6.1f} vs {exp:>6.1f} → {err:+5.1f}% (tol ±{tol}%) {status}")

    # ── Overall verdict ───────────────────────────────────────────────────
    overall = in_band and (not lf_checks or lf_pass) and (not checks or items_pass)

    return {
        "id": pid,
        "address": address,
        "roof_area_pass": in_band,
        "roof_area_error_pct": error_pct,
        "lf_pass": lf_pass if lf_checks else None,
        "line_items_pass": items_pass if checks else None,
        "line_items_count": len(line_items),
        "estimate_total": better["subtotal"],
        "overall_pass": overall,
    }


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    print("=" * 70)
    print("A/B VALIDATION — SKU Line Items Patch")
    print("=" * 70)
    print("\nValidating:")
    print("  1. Roof area accuracy (no regression)")
    print("  2. Linear measurements vs Reference A/B")
    print("  3. Line item quantities (sanity checks)")

    results = []
    for prop in data["example_properties"]:
        try:
            r = validate_one(prop)
            results.append(r)
        except Exception as exc:
            print(f"\n✗ ERROR on {prop['id']}: {exc}")
            import traceback
            traceback.print_exc()
            results.append({"id": prop["id"], "error": str(exc), "overall_pass": False})

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("SUMMARY")
    print('='*70)

    passed = sum(1 for r in results if r.get("overall_pass", False))
    print(f"\n  Overall: {passed}/{len(results)} properties PASSED\n")

    print(f"{'Property':<8} {'Area':>6} {'LF':>5} {'Items':>6} {'Overall':>8}")
    print("-" * 70)
    for r in results:
        if "error" in r:
            print(f"{r['id']:<8} ERROR")
            continue

        area_s = "✓" if r["roof_area_pass"] else "✗"
        lf_s = "✓" if r.get("lf_pass") is True else ("✗" if r.get("lf_pass") is False else "-")
        items_s = "✓" if r.get("line_items_pass") is True else ("✗" if r.get("line_items_pass") is False else "-")
        overall_s = "✓ PASS" if r["overall_pass"] else "✗ FAIL"

        print(f"{r['id']:<8} {area_s:>6} {lf_s:>5} {items_s:>6} {overall_s:>8}")

    print("\n" + "="*70)

    if passed == len(results):
        print("✓ All validations PASSED — patch is ready to deploy!")
        return True
    else:
        print(f"✗ {len(results) - passed} validation(s) FAILED — review output above")
        return False


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
