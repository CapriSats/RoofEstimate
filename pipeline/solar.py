"""
Google Solar API + Geocoding — primary path for roof measurement.

Produces slope-corrected roof area and pitch in a single call from Google's
3D building model. Far more accurate than vision-on-aerial pipelines for
covered US suburban addresses.

Requires a Google Maps Platform key (env var GOOGLE_VISION_API_KEY) with both
Geocoding API and Solar API enabled on the project.

Public entry point:
    get_solar_roof_measurement(address) -> dict | None

Returns None when the address can't be rooftop-geocoded, the Solar API has
no coverage, or the picked building is far from the geocoded rooftop (a
"wrong building" guard).
"""

import math
import os
from typing import Optional

import requests

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
SOLAR_URL = "https://solar.googleapis.com/v1/buildingInsights:findClosest"

PITCH_MULTIPLIER = {
    2: 1.014, 3: 1.031, 4: 1.054, 5: 1.083,
    6: 1.118, 7: 1.158, 8: 1.202, 9: 1.250,
    10: 1.302, 11: 1.357, 12: 1.414,
}

M2_TO_SQFT = 10.7639


def get_solar_roof_measurement(address: str) -> Optional[dict]:
    # Honor the SOLAR_MODE flag — when off, this whole path is disabled
    # for hackathon "build, don't buy" compliance.
    from pipeline.config import SOLAR_MODE
    if SOLAR_MODE == "off":
        return None

    api_key = os.environ.get("GOOGLE_VISION_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return None

    geo = _google_geocode(address, api_key)
    if not geo:
        return None

    insights = _solar_find_closest(geo["lat"], geo["lon"], api_key)
    if not insights:
        return None

    measurement = _parse_insights(insights)
    if not measurement:
        return None

    # "Wrong building" guard: if Solar API returned a building whose centroid
    # is far from the rooftop-geocoded address, the closest-building heuristic
    # likely picked a neighbor. Treat as miss so the caller can fall back.
    bbox = insights.get("boundingBox") or {}
    sw = bbox.get("sw", {})
    ne = bbox.get("ne", {})
    if sw and ne:
        bldg_lat = (sw.get("latitude", geo["lat"]) + ne.get("latitude", geo["lat"])) / 2
        bldg_lon = (sw.get("longitude", geo["lon"]) + ne.get("longitude", geo["lon"])) / 2
        dist_m = _haversine_m(geo["lat"], geo["lon"], bldg_lat, bldg_lon)
        if geo["precision"] == "ROOFTOP" and dist_m > 60:
            return None
        if geo["precision"] != "ROOFTOP" and dist_m > 100:
            return None
        measurement["building_offset_m"] = round(dist_m, 1)

    measurement["lat"] = geo["lat"]
    measurement["lon"] = geo["lon"]
    measurement["geocode_precision"] = geo["precision"]
    return measurement


# ── Google Geocoding ─────────────────────────────────────────────────────────

def _google_geocode(address: str, api_key: str) -> Optional[dict]:
    try:
        r = requests.get(GEOCODE_URL, params={"address": address, "key": api_key}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Google Geocoding error: {e}")
        return None

    if data.get("status") != "OK" or not data.get("results"):
        return None

    res = data["results"][0]
    loc = res["geometry"]["location"]
    return {
        "lat": loc["lat"],
        "lon": loc["lng"],
        "precision": res["geometry"].get("location_type", "APPROXIMATE"),
        "formatted_address": res.get("formatted_address", address),
    }


# ── Solar API ────────────────────────────────────────────────────────────────

def _solar_find_closest(lat: float, lon: float, api_key: str) -> Optional[dict]:
    # Retry transient 403s — Solar API enablement can take minutes to propagate
    # across regional backends, producing intermittent "API not enabled" errors
    # even after the project has it enabled.
    import time
    for attempt in range(3):
        try:
            r = requests.get(SOLAR_URL, params={
                "location.latitude": lat,
                "location.longitude": lon,
                "key": api_key,
                "requiredQuality": "LOW",
            }, timeout=20)
        except Exception as e:
            print(f"Solar API error: {e}")
            return None

        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            # No building coverage at this location — definitive, no point retrying.
            return None
        if r.status_code == 403 and attempt < 2:
            time.sleep(1.5 * (attempt + 1))
            continue
        print(f"Solar API HTTP {r.status_code}: {r.text[:200]}")
        return None
    return None


def _parse_insights(insights: dict) -> Optional[dict]:
    sp = insights.get("solarPotential") or {}
    segments = sp.get("roofSegmentStats") or []
    if not segments:
        return None

    total_segment_m2 = sum(s.get("stats", {}).get("areaMeters2", 0) for s in segments)
    if total_segment_m2 <= 0:
        return None

    # Slope-corrected total roof surface area — what reference measurements report.
    roof_sqft = round(total_segment_m2 * M2_TO_SQFT)

    # Area-weighted average pitch in degrees → snapped to nearest x:12 increment.
    weighted_pitch_deg = (
        sum(s.get("pitchDegrees", 0) * s.get("stats", {}).get("areaMeters2", 0) for s in segments)
        / total_segment_m2
    )
    pitch_x_12 = max(2, min(12, round(math.tan(math.radians(weighted_pitch_deg)) * 12)))

    # Footprint = horizontal-projection sum across segments.
    # roof_segment_areaMeters2 is slope-corrected; horizontal projection is areaMeters2 * cos(pitch).
    footprint_m2 = sum(
        s.get("stats", {}).get("areaMeters2", 0) * math.cos(math.radians(s.get("pitchDegrees", 0)))
        for s in segments
    )
    footprint_sqft = round(footprint_m2 * M2_TO_SQFT)

    quality = insights.get("imageryQuality", "UNKNOWN")
    confidence = {"HIGH": 0.95, "MEDIUM": 0.85, "LOW": 0.70}.get(quality, 0.60)

    return {
        "roof_sqft": roof_sqft,
        "footprint_sqft": footprint_sqft,
        "pitch_x_12": pitch_x_12,
        "pitch_multiplier": PITCH_MULTIPLIER.get(pitch_x_12, 1.118),
        "pitch_deg": round(weighted_pitch_deg, 1),
        "num_segments": len(segments),
        "imagery_quality": quality,
        "source": "google_solar",
        "confidence": confidence,
    }


# ── helpers ──────────────────────────────────────────────────────────────────

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


if __name__ == "__main__":
    import json
    import sys
    addr = " ".join(sys.argv[1:]) or "14132 Trenton Ave, Orland Park, IL 60462"
    result = get_solar_roof_measurement(addr)
    print(json.dumps(result, indent=2) if result else "No measurement (Solar API miss or wrong-building guard)")
