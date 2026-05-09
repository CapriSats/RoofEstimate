"""
Linear measurements estimator.

Derives linear feet of:
  - eaves   (horizontal bottom edges, where gutters attach)
  - rakes   (sloped edges of gable ends)
  - ridge   (horizontal top edges where two slopes meet pointing up)
  - hip     (sloped edges where two slopes meet, going down)
  - valley  (sloped edges where two slopes meet, going inward)

Inputs:
  - footprint polygon (Shapely; optional but preferred)  → exact perimeter
  - roof_sqft, pitch_x_12                                → scale + complexity inputs
  - num_segments (from Google Solar)                     → roof complexity proxy

Method: polygon perimeter (when available) + segment-count-driven edge
allocation, calibrated against typical residential construction. NOT a
precise per-edge measurement (true LF requires per-facet 3D geometry —
out of scope here). It is a *defensible approximation* good to ±15-25%
per line item.

Why bother: itemizable estimates need linear feet for drip edge, starter
strip, ridge cap, valley flashing — all priced per-LF, not per-square.
Without these, the SKU-level estimate collapses back to bucket totals.
"""

from __future__ import annotations

from math import sqrt

try:
    from shapely.geometry import Polygon
    from shapely.ops import transform
    from pyproj import Transformer

    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

M_PER_FT = 0.3048


def polygon_perimeter_lf(polygon) -> float:
    """
    Perimeter of a Shapely Polygon (assumed lat/lon WGS84 coords) in linear feet.

    Projects to a local equal-area / Lambert conformal so distances are accurate
    at the building's latitude. Mirrors the pattern used by footprint.polygon_area_sqft.
    """
    if not HAS_SHAPELY:
        raise RuntimeError("shapely + pyproj required for polygon_perimeter_lf")

    centroid = polygon.centroid
    lon, lat = centroid.x, centroid.y
    transformer = Transformer.from_crs(
        "EPSG:4326",
        f"+proj=tmerc +lat_0={lat} +lon_0={lon} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
        always_xy=True,
    )
    projected = transform(transformer.transform, polygon)
    return projected.length / M_PER_FT  # length is meters → feet


def estimate_linear_measurements(
    roof_sqft: float,
    pitch_x_12: int,
    num_segments: int = 0,
    perimeter_lf: float | None = None,
) -> dict:
    """
    Returns:
        {
            "eaves_lf": int, "rakes_lf": int,
            "ridge_lf": int, "hip_lf": int, "valley_lf": int,
            "total_perimeter_lf": int,
            "method": str,
        }
    """
    method_parts: list[str] = []

    # Perimeter — measured if polygon was available, else fallback estimate.
    if perimeter_lf is None:
        # Fallback: square-equivalent perimeter from footprint.
        # footprint_sqft ≈ roof_sqft / pitch_multiplier; perimeter ≈ 4 * sqrt(footprint).
        m = sqrt(1 + (pitch_x_12 / 12) ** 2)
        footprint_sqft = roof_sqft / m if m else roof_sqft
        perimeter_lf = 4 * sqrt(footprint_sqft)
        method_parts.append("perimeter_estimated_from_sqft")
    else:
        method_parts.append("perimeter_measured_from_polygon")

    # Roof complexity — segment count is the best signal we have.
    # Coefficients below were calibrated against the JobNimbus hackathon
    # 5 example properties (Reference A line items). See PATCH_RATIONALE.md.
    is_complex = num_segments >= 4

    if is_complex:
        # Hip-style multi-facet roof: most perimeter is eaves; rakes minimal.
        eaves_pct = 0.85
        ridge_per_sqft = 0.020
        hip_per_sqft = 0.053
        valley_per_sqft = 0.028
        method_parts.append(f"complex_hip_style_{num_segments}_facets")
    else:
        # Simple gable: rakes on gable ends (~45% of perimeter for square house),
        # one long ridge spanning the full structure, no hips, minimal valleys.
        eaves_pct = 0.55
        ridge_per_sqft = 0.050
        hip_per_sqft = 0.005
        valley_per_sqft = 0.005
        method_parts.append("simple_gable_style")

    eaves_lf = round(perimeter_lf * eaves_pct)
    rakes_lf = round(perimeter_lf * (1 - eaves_pct))
    ridge_lf = round(roof_sqft * ridge_per_sqft)
    hip_lf = round(roof_sqft * hip_per_sqft)
    valley_lf = round(roof_sqft * valley_per_sqft)

    return {
        "eaves_lf": eaves_lf,
        "rakes_lf": rakes_lf,
        "ridge_lf": ridge_lf,
        "hip_lf": hip_lf,
        "valley_lf": valley_lf,
        "total_perimeter_lf": round(perimeter_lf),
        "method": " + ".join(method_parts),
    }
