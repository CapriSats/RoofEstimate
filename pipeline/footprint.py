"""
Stage 3 — Footprint Resolver
lat/lon → { polygon, footprint_sqft, source, confidence }

Source priority:
  1. OpenStreetMap via Overpass API  (no key, global coverage)
  2. Microsoft Building Footprints   (highest accuracy, needs county GeoJSON in data/)
  3. Bounding-box fallback           (last resort — rough estimate from imagery scale)

The polygon closest to and containing the geocoded point wins.
"""

import json
import math
import os
import requests
from pathlib import Path
from shapely.geometry import Point, Polygon, shape
from shapely.ops import transform
import pyproj

DATA_DIR = Path(__file__).parent.parent / "data" / "ms_footprints"


# ── public API ───────────────────────────────────────────────────────────────

def get_footprint(lat: float, lon: float, radius_m: float = 250) -> dict:
    """
    Returns the best available building footprint for the property at lat/lon.
    Falls through sources until one succeeds.
    """
    # Try OSM first (free, fast, good coverage)
    result = _osm(lat, lon, radius_m)
    if result and result["confidence"] >= 0.6:
        return result

    # Try Grounded-SAM (Grounding DINO + SAM) for vision-based detection
    grounded_sam_result = _grounded_sam(lat, lon)
    if grounded_sam_result and grounded_sam_result["confidence"] >= 0.5:
        return grounded_sam_result

    # Try Google Vision API (Gemini) as alternative
    google_result = _google_vision(lat, lon)
    if google_result and google_result["confidence"] >= 0.7:
        return google_result

    # Try Microsoft footprints (requires local data files)
    ms_result = _ms_footprints(lat, lon)
    if ms_result:
        return ms_result

    # Accept lower-confidence Grounded-SAM result before Google
    if grounded_sam_result:
        return grounded_sam_result

    # Accept lower-confidence Google result before fallback
    if google_result:
        return google_result

    # Accept low-confidence OSM hit before fallback
    if result:
        return result

    return _bbox_fallback(lat, lon)


# ── area math ─────────────────────────────────────────────────────────────────

def polygon_area_sqft(polygon: Polygon) -> float:
    """Project to local UTM and compute area in sq ft."""
    centroid = polygon.centroid
    zone = int((centroid.x + 180) / 6) + 1
    hemisphere = "north" if centroid.y >= 0 else "south"
    utm = pyproj.CRS(f"+proj=utm +zone={zone} +{hemisphere} +datum=WGS84 +units=m +no_defs")
    wgs84 = pyproj.CRS("EPSG:4326")
    proj = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
    projected = transform(proj, polygon)
    return projected.area * 10.7639  # m² → ft²


# ── OSM via Overpass ──────────────────────────────────────────────────────────

def _osm(lat: float, lon: float, radius_m: float) -> dict | None:
    query = f"""
    [out:json][timeout:30];
    (
      way["building"](around:{radius_m},{lat},{lon});
      relation["building"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    try:
        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            headers={"User-Agent": "RoofEstimator/1.0"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"OSM Overpass error: {e}")
        return None

    nodes = {
        el["id"]: (el["lon"], el["lat"])
        for el in data["elements"]
        if el["type"] == "node"
    }

    point = Point(lon, lat)
    # Residential building sanity cap. Bigger polygons in OSM are typically
    # mislabeled subdivision boundaries, parking decks, commercial structures,
    # or townhome rows merged into a single polygon (saw 9,920 sqft polygon
    # for a 4-unit row in Thornton CO). Single-family residential rarely
    # exceeds 5,500 sqft footprint.
    MAX_RESIDENTIAL_FOOTPRINT_SQFT = 6_000
    # Excluded tag values — these aren't single-residence structures.
    EXCLUDED_BUILDING_TAGS = {"roof", "shed", "garage", "carport", "construction"}

    candidates = []
    for el in data["elements"]:
        if el["type"] != "way":
            continue
        tags = el.get("tags", {})
        building_tag = tags.get("building")
        if not building_tag or building_tag in EXCLUDED_BUILDING_TAGS:
            continue
        node_ids = el.get("nodes", [])
        coords = [nodes[n] for n in node_ids if n in nodes]
        if len(coords) < 4:
            continue
        try:
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            continue

        area = polygon_area_sqft(poly)
        if area > MAX_RESIDENTIAL_FOOTPRINT_SQFT:
            continue  # subdivision/lot boundary or commercial — skip
        if area < 400:
            continue  # too small to be a residence

        candidates.append({
            "poly": poly,
            "area": area,
            "contains": poly.contains(point),
            "dist": poly.distance(point),
            "tag": building_tag,
        })

    if not candidates:
        return None

    # Selection rules:
    # 1. If any polygon contains the point, pick the smallest (most-specific structure).
    # 2. Otherwise pick the closest polygon (geocoder offset is typical for US residential).
    containing = [c for c in candidates if c["contains"]]
    if containing:
        chosen = min(containing, key=lambda c: c["area"])
        confidence = 0.90
    else:
        chosen = min(candidates, key=lambda c: c["dist"])
        # Confidence drops with distance; ~50m is borderline.
        # 0.0005 deg ~= 55m at our latitudes
        confidence = 0.75 if chosen["dist"] < 0.0005 else 0.55

    return {
        "polygon": chosen["poly"],
        "footprint_sqft": round(chosen["area"]),
        "source": "osm",
        "confidence": confidence,
    }


# ── Microsoft Building Footprints ─────────────────────────────────────────────

def _ms_footprints(lat: float, lon: float) -> dict | None:
    """
    Searches any GeoJSON files in data/ms_footprints/ that cover this lat/lon.
    Download county-level files from:
      https://github.com/microsoft/USBuildingFootprints
    and save to data/ms_footprints/<state>/<county>.geojson
    """
    if not DATA_DIR.exists():
        return None

    point = Point(lon, lat)
    best, best_area = None, 0.0

    for geojson_path in DATA_DIR.rglob("*.geojson"):
        try:
            with open(geojson_path) as f:
                fc = json.load(f)
        except Exception:
            continue

        for feature in fc.get("features", []):
            try:
                poly = shape(feature["geometry"])
                if poly.distance(point) > 0.001:
                    continue
                area = polygon_area_sqft(poly)
                contains = poly.contains(point)
                score = area + (1e6 if contains else 0)
                if score > best_area:
                    best_area = score
                    best = (poly, area, contains)
            except Exception:
                continue

    if best is None:
        return None

    poly, area, contains = best
    return {
        "polygon": poly,
        "footprint_sqft": round(area),
        "source": "ms_footprints",
        "confidence": 0.92 if contains else 0.75,
    }


# ── Grounded-SAM (Grounding DINO + SAM) ──────────────────────────────────────

def _grounded_sam(lat: float, lon: float) -> dict | None:
    """
    Use Grounded-SAM (Grounding DINO + Segment Anything Model) for pixel-perfect
    building footprint detection from aerial imagery.
    """
    try:
        from pipeline.footprint_grounded_sam import get_grounded_sam_footprint
        return get_grounded_sam_footprint(lat, lon)
    except Exception as e:
        # Silently skip if Grounded-SAM not available
        print(f"Grounded-SAM unavailable: {e}")
        return None


# ── Google Vision API ─────────────────────────────────────────────────────────

def _google_vision(lat: float, lon: float) -> dict | None:
    """
    Use Google Vision API to detect building footprint from aerial imagery.
    Requires GOOGLE_VISION_API_KEY environment variable.
    """
    try:
        from pipeline.footprint_google import get_google_footprint
        return get_google_footprint(lat, lon)
    except Exception as e:
        # Silently skip if Google Vision not configured
        return None


# ── Bounding-box fallback ─────────────────────────────────────────────────────

def _bbox_fallback(lat: float, lon: float) -> dict:
    """
    When no polygon source works, estimate footprint from a typical
    single-family home bounding box (≈ 1,600 sqft footprint).
    Flagged low-confidence so the caller can surface a warning.
    """
    # 40 ft ≈ 0.000121 degrees lat; 45 ft ≈ varies by lat
    delta_lat = 40 / 364000
    delta_lon = 45 / (364000 * math.cos(math.radians(lat)))
    poly = Polygon([
        (lon - delta_lon, lat - delta_lat),
        (lon + delta_lon, lat - delta_lat),
        (lon + delta_lon, lat + delta_lat),
        (lon - delta_lon, lat + delta_lat),
        (lon - delta_lon, lat - delta_lat),
    ])
    return {
        "polygon": poly,
        "footprint_sqft": 1600,
        "source": "fallback",
        "confidence": 0.30,
    }


if __name__ == "__main__":
    import sys
    lat, lon = float(sys.argv[1]), float(sys.argv[2])
    r = get_footprint(lat, lon)
    print(f"footprint_sqft={r['footprint_sqft']}  source={r['source']}  confidence={r['confidence']:.2f}")
