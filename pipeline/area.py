"""
Stage 5 — Roof Area Calculator
footprint_sqft × pitch_multiplier → roof_sqft

This is the number we submit. Sanity-checked against residential norms.
"""

RESIDENTIAL_MIN_SQFT = 600
RESIDENTIAL_MAX_SQFT = 12_000


def calculate_roof_area(footprint_sqft: float, pitch_multiplier: float) -> dict:
    """
    Returns the final roof area and a confidence/sanity flag.
    """
    roof_sqft = round(footprint_sqft * pitch_multiplier)

    in_range = RESIDENTIAL_MIN_SQFT <= roof_sqft <= RESIDENTIAL_MAX_SQFT
    warning = None
    if not in_range:
        warning = (
            f"roof_sqft={roof_sqft} is outside typical residential range "
            f"({RESIDENTIAL_MIN_SQFT}–{RESIDENTIAL_MAX_SQFT} sqft). "
            "Double-check footprint and pitch inputs."
        )

    return {
        "roof_sqft": roof_sqft,
        "footprint_sqft": round(footprint_sqft),
        "pitch_multiplier": pitch_multiplier,
        "in_range": in_range,
        "warning": warning,
    }
