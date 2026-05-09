"""
Configuration for optional / experimental pipeline methods.
Production pipeline (pitch.py) uses its own defaults.
This config ONLY governs new / A/B-tested methods.
"""

import os
from dataclasses import dataclass, field

# Solar API stance — controls how Google Solar API contributes to the final number.
# Configurable per the hackathon "Build, don't buy" rule:
#   "off"     — Solar API disabled. OSM + Vision LLM only. Lowest DQ risk.
#   "fusion"  — Solar API contributes one input among several; fusion combines them.
#   "primary" — Solar API primary; OSM fallback only when Solar misses.
SOLAR_MODE = os.environ.get("SOLAR_MODE", "fusion").lower()
assert SOLAR_MODE in ("off", "fusion", "primary"), \
    f"SOLAR_MODE must be off|fusion|primary, got {SOLAR_MODE!r}"


@dataclass
class ShadowOverlapConfig:
    """Kadhim & Mourshed (2018) shadow-overlap pitch estimator settings."""

    # Height search range (metres) — residential roofs: ridge 3–15 m above eave
    height_min_m: float = 3.0
    height_max_m: float = 30.0
    height_step_m: float = 0.5

    # Minimum Jaccard similarity to accept a result
    min_jaccard: float = 0.25

    # Minimum solar elevation (degrees) — shadows unreliable below this
    min_solar_elevation_deg: float = 10.0

    # Shadow detection — pixel brightness threshold (0-255); darker = shadow
    shadow_threshold: int = 80

    # Morphological cleanup kernel size (pixels)
    morph_kernel_size: int = 3

    # Whether to include the full Jaccard curve in the output (useful for debugging)
    return_jaccard_curve: bool = False


@dataclass
class PipelineConfig:
    shadow_overlap: ShadowOverlapConfig = field(default_factory=ShadowOverlapConfig)
    shadow_overlap_enabled: bool = False   # Off by default; toggle for A/B testing

    # Confidence weight when fusing with other pitch sources
    confidence_weights: dict = field(default_factory=lambda: {
        "shadow_overlap": 0.80,
        "vision_llm":     0.75,
        "regional_default": 0.45,
    })


# Module-level singleton — import and mutate to configure
default_config = PipelineConfig()
