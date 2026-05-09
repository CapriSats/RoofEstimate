"""
Microsoft Global ML Building Footprints — on-demand quadkey-based fetch.

Microsoft publishes ~1.4B building polygons worldwide as GeoJSONL files
partitioned by Bing-style quadkey (zoom 9). This module:

  1. Lazy-downloads the small index (~7 MB CSV mapping quadkey → file URL).
  2. For a query lat/lon, computes the containing zoom-9 quadkey,
     fetches the relevant tile (typically 1–10 MB compressed, cached on disk),
     and returns the closest residential-sized polygon.

This is the "build" alternative to Google Solar API — Microsoft gives us the
raw polygon data and we do the area math, selection logic, and confidence
scoring ourselves.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from shapely.geometry import Point, Polygon, shape

CACHE_DIR = Path(__file__).parent.parent / "data" / "ms_buildings_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

INDEX_URL = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
INDEX_CACHE = CACHE_DIR / "dataset-links.csv"
INDEX_TTL_S = 7 * 86_400  # refresh weekly

# Module-level cache: quadkey -> [(region, url), ...]
_INDEX: dict[str, list[tuple[str, str]]] | None = None


# ── public API ───────────────────────────────────────────────────────────────

def get_ms_footprint(lat: float, lon: float, radius_m: float = 250) -> Optional[dict]:
    """
    Returns the closest residential building footprint from MS data, or None
    if the tile is unavailable or no candidates match.
    """
    from pipeline.footprint import polygon_area_sqft

    index = _ensure_index()
    if not index:
        return None

    qk = _compute_quadkey(lat, lon, zoom=9)
    entries = index.get(qk, [])
    if not entries:
        return None

    # For US queries we only want UnitedStates region tiles. For other countries
    # this would need adjustment, but our hackathon scope is US-only.
    us_urls = [url for region, url in entries if region == "UnitedStates"]
    if not us_urls:
        # Fall back to whatever region the index says
        us_urls = [url for _, url in entries]

    point = Point(lon, lat)
    deg_radius = radius_m / 111_000.0  # rough deg ≈ m at our latitudes
    deg_pre_filter = deg_radius * 1.5

    candidates: list[dict] = []
    for url in us_urls:
        for geom_dict in _iter_tile_buildings(url):
            # Cheap bbox pre-filter to avoid building shapely Polygons for
            # every one of ~38k buildings in a tile.
            coords = geom_dict.get("coordinates")
            if not coords:
                continue
            try:
                ring = coords[0]
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                if (min(xs) > lon + deg_pre_filter
                    or max(xs) < lon - deg_pre_filter
                    or min(ys) > lat + deg_pre_filter
                    or max(ys) < lat - deg_pre_filter):
                    continue
            except Exception:
                continue

            try:
                poly = shape(geom_dict)
                if not poly.is_valid:
                    poly = poly.buffer(0)
            except Exception:
                continue

            dist = poly.distance(point)
            if dist > deg_radius:
                continue

            area = polygon_area_sqft(poly)
            if area < 400 or area > 6_000:
                continue  # filter non-residential sizes

            candidates.append({
                "poly": poly,
                "area": area,
                "contains": poly.contains(point),
                "dist": dist,
            })

    if not candidates:
        return None

    containing = [c for c in candidates if c["contains"]]
    if containing:
        chosen = min(containing, key=lambda c: c["area"])
        confidence = 0.92
    else:
        chosen = min(candidates, key=lambda c: c["dist"])
        confidence = 0.78 if chosen["dist"] * 111_000 < 60 else 0.60

    return {
        "polygon": chosen["poly"],
        "footprint_sqft": round(chosen["area"]),
        "source": "ms_buildings",
        "confidence": confidence,
    }


# ── quadkey math ─────────────────────────────────────────────────────────────

def _compute_quadkey(lat: float, lon: float, zoom: int = 9) -> str:
    n = 1 << zoom
    sin_lat = math.sin(math.radians(lat))
    tile_x = int((lon + 180.0) / 360.0 * n)
    tile_y = int((0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * n)
    parts = []
    for i in range(zoom, 0, -1):
        digit = 0
        mask = 1 << (i - 1)
        if (tile_x & mask) != 0:
            digit += 1
        if (tile_y & mask) != 0:
            digit += 2
        parts.append(str(digit))
    return "".join(parts)


# ── index management ─────────────────────────────────────────────────────────

def _ensure_index() -> dict[str, list[tuple[str, str]]]:
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    fresh = (
        INDEX_CACHE.exists()
        and (time.time() - INDEX_CACHE.stat().st_mtime) < INDEX_TTL_S
    )
    if not fresh:
        try:
            r = requests.get(INDEX_URL, timeout=60)
            r.raise_for_status()
            INDEX_CACHE.write_bytes(r.content)
        except Exception as e:
            print(f"MS Buildings index download failed: {e}")
            if not INDEX_CACHE.exists():
                _INDEX = {}
                return _INDEX

    idx: dict[str, list[tuple[str, str]]] = {}
    with INDEX_CACHE.open("r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qk = row.get("QuadKey")
            url = row.get("Url")
            region = row.get("Location", "")
            if qk and url:
                idx.setdefault(qk, []).append((region, url))
    _INDEX = idx
    return idx


# ── tile fetching ────────────────────────────────────────────────────────────

def _tile_cache_path(url: str) -> Path:
    name = url.rsplit("/", 1)[-1]
    return CACHE_DIR / name


def _iter_tile_buildings(url: str):
    """Yield each building's geometry dict from a tile (cached on first fetch)."""
    cache = _tile_cache_path(url)
    if not cache.exists():
        try:
            print(f"MS Buildings: downloading tile {cache.name} …")
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            cache.write_bytes(r.content)
        except Exception as e:
            print(f"MS tile download failed for {url}: {e}")
            return

    try:
        with gzip.open(cache, "rt") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    feat = json.loads(line)
                    geom = feat.get("geometry")
                    if geom:
                        yield geom
                except Exception:
                    continue
    except Exception as e:
        print(f"MS tile parse failed for {cache}: {e}")
        return


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        lat, lon = float(sys.argv[1]), float(sys.argv[2])
    else:
        lat, lon = 30.01941, -95.31189  # ex1 Kenswick (rooftop-precision)
    r = get_ms_footprint(lat, lon)
    print(json.dumps({
        "footprint_sqft": r["footprint_sqft"] if r else None,
        "source": r["source"] if r else None,
        "confidence": r["confidence"] if r else None,
    }, indent=2) if r else "No MS Buildings result")
