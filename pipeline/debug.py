"""
Per-property debug artifacts for pipeline verification.

When MEASURE_DEBUG=1 (or measure_roof(debug=True)) is set, each call writes:
  outputs/debug/<slug>/
    step_log.json     — per-stage outputs (geocode, sources, final)
    aerial_full.png   — full ESRI tile centred on geocoded lat/lon
    aerial_cropped.png — Google Static frame around the chosen polygon
    annotated.png     — aerial_cropped with the chosen polygon outlined
                        and a red bbox so you can visually verify it's
                        the right house

Use it to sanity-check a single property quickly:
    python -m pipeline.measurement "14132 Trenton Ave, Orland Park, IL 60462"
"""

from __future__ import annotations

import json
import math
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

DEBUG_DIR = Path(__file__).parent.parent / "outputs" / "debug"


def slugify(address: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", address).strip("_").lower()
    return s[:80] or "anon"


def write_step_log(address: str, step_log: dict) -> Path:
    out_dir = DEBUG_DIR / slugify(address)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "step_log.json"
    with path.open("w") as f:
        json.dump(step_log, f, indent=2, default=str)
    return path


def save_aerial(address: str, name: str, image_bytes: bytes) -> Path:
    out_dir = DEBUG_DIR / slugify(address)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_bytes(image_bytes)
    return path


def annotate_polygon_in_memory(
    image_bytes: bytes,
    polygon,
    image_meta: dict,
    label: str = "",
) -> Optional[bytes]:
    """Same as annotate_polygon_on_image but returns PNG bytes instead of writing to disk."""
    annotated = _annotate_polygon_pil(image_bytes, polygon, image_meta, label)
    if annotated is None:
        return None
    from io import BytesIO
    out = BytesIO()
    annotated.save(out, format="PNG")
    return out.getvalue()


def _annotate_polygon_pil(
    image_bytes: bytes,
    polygon,
    image_meta: dict,
    label: str = "",
):
    """Shared PIL drawing helper. Returns a PIL.Image or None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    center_lat = image_meta.get("center_lat")
    center_lon = image_meta.get("center_lon")
    mpp = image_meta.get("meters_per_pixel")
    if center_lat is None or center_lon is None or not mpp:
        return None

    cos_lat = math.cos(math.radians(center_lat))
    def to_px(lon: float, lat: float):
        dx_m = (lon - center_lon) * 111_000 * cos_lat
        dy_m = (lat - center_lat) * 111_000
        return (width / 2 + dx_m / mpp, height / 2 - dy_m / mpp)

    coords = list(polygon.exterior.coords)
    pixel_ring = [to_px(lon, lat) for lon, lat in coords]

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon(pixel_ring, fill=(0, 200, 100, 80), outline=(0, 220, 120, 255))

    minx, miny, maxx, maxy = polygon.bounds
    bbox_corners = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)]
    bbox_pixels = [to_px(lon, lat) for lon, lat in bbox_corners]
    for i in range(len(bbox_pixels) - 1):
        draw.line([bbox_pixels[i], bbox_pixels[i + 1]], fill=(255, 60, 60, 255), width=3)

    if label:
        try:
            font = ImageFont.load_default()
            draw.rectangle([(8, 8), (8 + len(label) * 7 + 6, 26)], fill=(0, 0, 0, 180))
            draw.text((12, 11), label, fill=(255, 255, 255, 255), font=font)
        except Exception:
            pass

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def annotate_polygon_on_image(
    address: str,
    image_bytes: bytes,
    polygon,
    image_meta: dict,
    label: str = "",
) -> Optional[Path]:
    """Render annotated image and write to outputs/debug/<slug>/annotated.png."""
    annotated = _annotate_polygon_pil(image_bytes, polygon, image_meta, label)
    if annotated is None:
        return None
    out_dir = DEBUG_DIR / slugify(address)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "annotated.png"
    annotated.save(path)
    return path
