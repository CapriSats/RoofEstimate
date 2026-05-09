"""
Stage 2 — Imagery Fetcher
lat/lon → { image_bytes, meters_per_pixel, tile_x, tile_y, zoom }
Primary: ESRI World Imagery (no API key required)
Fallback: Bing Maps Static (requires BING_MAPS_KEY env var)
"""

import io
import math
import os
import requests
from PIL import Image


# ESRI tile at zoom 19 ≈ 30 cm/px in CONUS — sufficient for roof segmentation
DEFAULT_ZOOM = 19


def fetch_imagery(lat: float, lon: float, zoom: int = DEFAULT_ZOOM) -> dict:
    """
    Returns aerial tile centred on lat/lon.
    dict keys: image_bytes (bytes), image (PIL.Image), meters_per_pixel (float),
                zoom, tile_x, tile_y, center_lat, center_lon, source (str)
    """
    result = _esri(lat, lon, zoom)
    if result:
        return result

    bing_key = os.getenv("BING_MAPS_KEY")
    if bing_key:
        result = _bing(lat, lon, bing_key)
        if result:
            return result

    raise RuntimeError(f"Could not fetch imagery for ({lat}, {lon})")


def fetch_imagery_for_polygon(polygon, padding_pct: float = 0.35,
                               target_size_px: int = 640) -> dict | None:
    """
    Returns aerial imagery framed precisely around a building polygon, with
    padding. Uses Google Maps Static API when the key is available; falls
    back to a centred ESRI tile (which won't be polygon-aligned).

    Why: Vision LLM pitch estimation works much better when the image shows
    *only* the target building. Wide tiles with several buildings force the
    model to guess which one to analyse, which is the main pitch-error
    source we measured.
    """
    minx, miny, maxx, maxy = polygon.bounds
    centroid = polygon.centroid
    lat_c, lon_c = centroid.y, centroid.x

    # Polygon dimensions in metres (approximate at this latitude).
    lat_per_m = 1 / 111_000
    lon_per_m = 1 / (111_000 * math.cos(math.radians(lat_c)))
    width_m = (maxx - minx) / lon_per_m
    height_m = (maxy - miny) / lat_per_m
    max_dim_m = max(width_m, height_m) * (1 + 2 * padding_pct)
    if max_dim_m <= 0:
        return None

    # Solve for the Web-Mercator zoom that fits max_dim_m into target_size_px.
    earth_circ_m = 40_075_016.686
    pixels_per_tile = 256
    target_mpp = max_dim_m / target_size_px
    if target_mpp <= 0:
        return None
    zoom_f = math.log2(
        earth_circ_m * math.cos(math.radians(lat_c)) / pixels_per_tile / target_mpp
    )
    zoom = max(17, min(21, int(round(zoom_f))))  # residential range

    api_key = os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if api_key:
        try:
            r = requests.get(
                "https://maps.googleapis.com/maps/api/staticmap",
                params={
                    "center": f"{lat_c},{lon_c}",
                    "zoom": zoom,
                    "size": f"{target_size_px}x{target_size_px}",
                    "maptype": "satellite",
                    "key": api_key,
                },
                timeout=20,
            )
            r.raise_for_status()
            mpp = (
                earth_circ_m * math.cos(math.radians(lat_c))
                / pixels_per_tile / (2 ** zoom)
            )
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            return {
                "image_bytes": r.content,
                "image": img,
                "meters_per_pixel": mpp,
                "zoom": zoom,
                "tile_x": None,
                "tile_y": None,
                "center_lat": lat_c,
                "center_lon": lon_c,
                "source": "google_static_satellite",
            }
        except Exception as e:
            print(f"Google Static imagery error: {e}")
            # fall through to ESRI tile

    return _esri(lat_c, lon_c, zoom)


# ── helpers ──────────────────────────────────────────────────────────────────

def _meters_per_pixel(lat: float, zoom: int) -> float:
    return (156543.03392 * math.cos(math.radians(lat))) / (2 ** zoom)


def _lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


# ── providers ─────────────────────────────────────────────────────────────────

def _esri(lat: float, lon: float, zoom: int) -> dict | None:
    x, y = _lat_lon_to_tile(lat, lon, zoom)
    url = (
        f"https://services.arcgisonline.com/ArcGIS/rest/services/"
        f"World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
    )
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        return {
            "image_bytes": r.content,
            "image": img,
            "meters_per_pixel": _meters_per_pixel(lat, zoom),
            "zoom": zoom,
            "tile_x": x,
            "tile_y": y,
            "center_lat": lat,
            "center_lon": lon,
            "source": "esri",
        }
    except Exception:
        return None


def _bing(lat: float, lon: float, key: str, width: int = 640, height: int = 640) -> dict | None:
    zoom = 19
    url = "https://dev.virtualearth.net/REST/v1/Imagery/Map/Aerial"
    params = {
        "centerPoint": f"{lat},{lon}",
        "zoomLevel": zoom,
        "mapSize": f"{width},{height}",
        "key": key,
        "format": "jpeg",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        return {
            "image_bytes": r.content,
            "image": img,
            "meters_per_pixel": _meters_per_pixel(lat, zoom),
            "zoom": zoom,
            "tile_x": None,
            "tile_y": None,
            "center_lat": lat,
            "center_lon": lon,
            "source": "bing",
        }
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    lat, lon = float(sys.argv[1]), float(sys.argv[2])
    result = fetch_imagery(lat, lon)
    out = f"/tmp/aerial_{lat}_{lon}.jpg"
    with open(out, "wb") as f:
        f.write(result["image_bytes"])
    print(f"Saved to {out} — {result['meters_per_pixel']:.3f} m/px via {result['source']}")
