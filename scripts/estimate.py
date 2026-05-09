#!/usr/bin/env python3
"""
RoofEstimate CLI — Single Property Estimator

Usage:
    python scripts/estimate.py "123 Main St, Houston, TX 77001"
    python scripts/estimate.py --file addresses.txt

Output:
    - JSON to stdout
    - Aerial image saved to outputs/
"""

import json
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.geocoder import geocode
from pipeline.imagery import fetch_imagery
from pipeline.footprint import get_footprint
from pipeline.pitch import estimate_pitch


def estimate_property(address: str, output_dir: Path = None) -> dict:
    """Run full pipeline for a single address."""

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "outputs" / "cli"
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📍 Geocoding: {address}", file=sys.stderr)
    start_time = time.time()

    try:
        # Step 1: Geocode
        geo = geocode(address)
        lat, lon = geo["lat"], geo["lon"]
        print(f"   → {lat:.6f}, {lon:.6f}", file=sys.stderr)

        # Step 2: Fetch imagery
        print("🛰️  Fetching aerial imagery...", file=sys.stderr)
        img = fetch_imagery(lat, lon)

        # Save image
        image_file = output_dir / f"{address.replace(' ', '_').replace(',', '')[:50]}.jpg"
        with open(image_file, "wb") as f:
            f.write(img["image_bytes"])
        print(f"   → Saved to {image_file}", file=sys.stderr)

        # Step 3: Get footprint
        print("🏠 Extracting building footprint...", file=sys.stderr)
        fp = get_footprint(lat, lon)
        print(f"   → {fp['footprint_sqft']:.0f} sqft ({fp['source']})", file=sys.stderr)

        # Step 4: Estimate pitch
        print("📐 Estimating roof pitch...", file=sys.stderr)
        pitch_result = estimate_pitch(img["image_bytes"], lat, lon, geo.get("state"))
        print(f"   → {pitch_result['pitch_x_12']}:12 ({pitch_result['method']})", file=sys.stderr)

        # Step 5: Calculate roof area
        pitch_x_12 = pitch_result["pitch_x_12"]
        pitch_multiplier = pitch_result.get("pitch_multiplier", 1.118)
        roof_sqft = int(fp["footprint_sqft"] * pitch_multiplier)

        print(f"📊 Roof area: {roof_sqft:,} sqft", file=sys.stderr)

        # Step 6: Cost estimate (simple)
        material_cost_per_sqft = 1.65  # Average architectural shingles
        labor_cost_per_sqft = 5.80     # Average labor

        materials = int(roof_sqft * material_cost_per_sqft)
        labor = int(roof_sqft * labor_cost_per_sqft)
        total = materials + labor

        print(f"💰 Estimate: ${total:,} (materials: ${materials:,}, labor: ${labor:,})", file=sys.stderr)

        elapsed = time.time() - start_time
        print(f"✅ Complete in {elapsed:.1f}s", file=sys.stderr)

        # Build result
        result = {
            "address": address,
            "coordinates": {
                "lat": lat,
                "lon": lon
            },
            "footprint": {
                "sqft": fp["footprint_sqft"],
                "source": fp["source"],
                "confidence": fp.get("confidence", 0.5)
            },
            "pitch": {
                "x_12": pitch_x_12,
                "degrees": pitch_result.get("pitch_deg"),
                "multiplier": pitch_multiplier,
                "method": pitch_result["method"],
                "confidence": pitch_result.get("confidence", 0.5)
            },
            "roof_area_sqft": roof_sqft,
            "estimate": {
                "materials": materials,
                "labor": labor,
                "total": total
            },
            "imagery": {
                "file": str(image_file),
                "meters_per_pixel": img.get("meters_per_pixel", 0.15)
            },
            "execution_time_s": round(elapsed, 2)
        }

        return result

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return {
            "address": address,
            "error": str(e)
        }


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="RoofEstimate — AI-powered roof measurement from aerial imagery",
        epilog="Example: python scripts/estimate.py '123 Main St, Houston, TX 77001'"
    )

    parser.add_argument(
        "address",
        nargs="?",
        help="Property address to estimate (use quotes)"
    )

    parser.add_argument(
        "--file",
        "-f",
        help="Read addresses from file (one per line)"
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output directory for images (default: outputs/cli/)"
    )

    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Pretty-print JSON output"
    )

    args = parser.parse_args()

    # Determine output directory
    output_dir = Path(args.output) if args.output else Path(__file__).parent.parent / "outputs" / "cli"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process addresses
    results = []

    if args.file:
        # Batch mode
        with open(args.file) as f:
            addresses = [line.strip() for line in f if line.strip()]

        print(f"Processing {len(addresses)} addresses from {args.file}...\n", file=sys.stderr)

        for i, address in enumerate(addresses, 1):
            print(f"\n[{i}/{len(addresses)}]", file=sys.stderr)
            result = estimate_property(address, output_dir)
            results.append(result)

    elif args.address:
        # Single mode
        result = estimate_property(args.address, output_dir)
        results.append(result)

    else:
        parser.print_help()
        sys.exit(1)

    # Output JSON
    print("\n" + "="*70 + "\n", file=sys.stderr)

    if args.pretty:
        print(json.dumps(results if len(results) > 1 else results[0], indent=2))
    else:
        print(json.dumps(results if len(results) > 1 else results[0]))


if __name__ == "__main__":
    main()
