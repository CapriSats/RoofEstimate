"""
Confidence-Weighted Fusion Engine
Combines multiple measurement sources using Bayesian-style weighting
"""
import numpy as np
from typing import List
from collections import Counter


PITCH_MULTIPLIER = {
    2: 1.014, 3: 1.031, 4: 1.054, 5: 1.083,
    6: 1.118, 7: 1.158, 8: 1.202, 9: 1.250,
    10: 1.302, 11: 1.357, 12: 1.414,
}


def fuse_pitch_estimates(estimates: List[dict]) -> dict:
    """
    Fuse multiple pitch estimates with confidence weighting.
    
    Input: [
        {"pitch_x_12": 6, "confidence": 0.75, "source": "vision"},
        {"pitch_x_12": 7, "confidence": 0.90, "source": "shadow"},
        {"pitch_x_12": 6, "confidence": 0.60, "source": "osm_prior"},
    ]
    
    Returns: {
        pitch_x_12: int,
        pitch_multiplier: float,
        confidence: float,
        sources_used: list[str],
        uncertainty: float,
        reasoning: str
    }
    """
    if not estimates:
        return {
            "pitch_x_12": 6,
            "pitch_multiplier": 1.118,
            "confidence": 0.4,
            "sources_used": ["default"],
            "uncertainty": 0.5,
            "reasoning": "No estimates available, using default 6:12"
        }
    
    # Filter out low-confidence estimates
    valid = [e for e in estimates if e.get("confidence", 0) > 0.3]
    if not valid:
        valid = estimates  # Keep all if none pass threshold
    
    # Outlier rejection using MAD (Median Absolute Deviation)
    pitches = [e["pitch_x_12"] for e in valid]
    median_pitch = np.median(pitches)
    mad = np.median([abs(p - median_pitch) for p in pitches])
    
    # Keep estimates within 2 MAD
    threshold = 2 * (mad if mad > 0 else 1.5)
    filtered = [e for e in valid if abs(e["pitch_x_12"] - median_pitch) <= threshold]
    
    if not filtered:
        filtered = valid
    
    # Weighted mode (most common pitch, weighted by confidence)
    pitch_weights = {}
    for e in filtered:
        pitch = e["pitch_x_12"]
        conf = e["confidence"]
        pitch_weights[pitch] = pitch_weights.get(pitch, 0) + conf
    
    # Select pitch with highest weighted vote
    best_pitch = max(pitch_weights, key=pitch_weights.get)
    
    # Combined confidence (normalized weighted sum)
    total_weight = sum(e["confidence"] for e in filtered)
    combined_confidence = sum(
        e["confidence"] for e in filtered if e["pitch_x_12"] == best_pitch
    ) / total_weight if total_weight > 0 else 0.5
    
    # Boost confidence if multiple sources agree
    agreement_count = sum(1 for e in filtered if e["pitch_x_12"] == best_pitch)
    if agreement_count >= 2:
        combined_confidence = min(0.95, combined_confidence * 1.15)
    
    # Uncertainty (standard deviation of pitches)
    if len(pitches) > 1:
        uncertainty = float(np.std(pitches)) / 12.0  # Normalized
    else:
        uncertainty = 0.3
    
    sources_used = [e["source"] for e in filtered if e["pitch_x_12"] == best_pitch]
    
    reasoning = f"Fused {len(filtered)} sources: {', '.join(set(s['source'] for s in filtered))}"
    if agreement_count >= 2:
        reasoning += f" ({agreement_count} agree on {best_pitch}:12)"
    
    return {
        "pitch_x_12": best_pitch,
        "pitch_multiplier": PITCH_MULTIPLIER.get(best_pitch, 1.118),
        "confidence": round(combined_confidence, 2),
        "sources_used": sources_used,
        "uncertainty": round(uncertainty, 2),
        "reasoning": reasoning
    }


def fuse_footprint_estimates(estimates: List[dict]) -> dict:
    """
    Fuse multiple footprint area estimates.
    
    Input: [
        {"footprint_sqft": 2400, "confidence": 0.75, "source": "vision"},
        {"footprint_sqft": 2350, "confidence": 0.85, "source": "ms_footprints"},
    ]
    
    Returns: {
        footprint_sqft: int,
        confidence: float,
        sources_used: list[str],
        uncertainty_pct: float,
        reasoning: str
    }
    """
    if not estimates:
        return {
            "footprint_sqft": 1800,
            "confidence": 0.3,
            "sources_used": ["default"],
            "uncertainty_pct": 25.0,
            "reasoning": "No estimates, using median default"
        }
    
    # Filter valid estimates
    valid = [e for e in estimates if e.get("confidence", 0) > 0.25]
    if not valid:
        valid = estimates
    
    # Outlier rejection
    areas = [e["footprint_sqft"] for e in valid]
    median_area = np.median(areas)
    mad = np.median([abs(a - median_area) for a in areas])
    
    threshold = 2 * (mad if mad > 0 else median_area * 0.2)
    filtered = [e for e in valid if abs(e["footprint_sqft"] - median_area) <= threshold]
    
    if not filtered:
        filtered = valid
    
    # Weighted average
    total_weight = sum(e["confidence"] for e in filtered)
    if total_weight > 0:
        weighted_area = sum(
            e["footprint_sqft"] * e["confidence"] for e in filtered
        ) / total_weight
    else:
        weighted_area = median_area
    
    # Combined confidence
    combined_confidence = total_weight / len(filtered) if filtered else 0.3
    combined_confidence = min(0.95, combined_confidence)
    
    # Uncertainty as coefficient of variation
    if len(areas) > 1:
        cv = float(np.std(areas) / np.mean(areas)) * 100
        uncertainty_pct = min(50.0, cv)
    else:
        uncertainty_pct = 15.0
    
    sources_used = [e["source"] for e in filtered]
    
    return {
        "footprint_sqft": int(round(weighted_area)),
        "confidence": round(combined_confidence, 2),
        "sources_used": sources_used,
        "uncertainty_pct": round(uncertainty_pct, 1),
        "reasoning": f"Weighted average of {len(filtered)} sources (±{uncertainty_pct:.0f}%)"
    }


if __name__ == "__main__":
    # Test pitch fusion
    pitch_estimates = [
        {"pitch_x_12": 6, "confidence": 0.75, "source": "vision"},
        {"pitch_x_12": 7, "confidence": 0.90, "source": "shadow"},
        {"pitch_x_12": 6, "confidence": 0.60, "source": "osm"},
    ]
    
    result = fuse_pitch_estimates(pitch_estimates)
    print("Pitch Fusion Result:")
    print(f"  Pitch: {result['pitch_x_12']}:12")
    print(f"  Confidence: {result['confidence']:.0%}")
    print(f"  Sources: {result['sources_used']}")
    print(f"  Reasoning: {result['reasoning']}")
