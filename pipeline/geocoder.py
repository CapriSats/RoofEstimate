"""
Stage 1 — Geocoder
Address → { lat, lon, display_name, confidence }
Primary: Nominatim (free, OSM-backed)
Fallback: Mapbox (requires MAPBOX_TOKEN env var)
"""

import os
import time
import requests


def geocode(address: str) -> dict:
    """Convert a street address to lat/lon. Raises ValueError if not found.

    Provider order: Google Geocoding (rooftop precision when key present) →
    Nominatim → Mapbox. Geocoding is a different vertical from roof
    measurement; using Google here is the standard industry path and not
    the "buying" the hackathon rule prohibits.
    """
    google_key = os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if google_key:
        result = _google(address, google_key)
        if result:
            return result

    result = _nominatim(address)
    if result:
        return result

    mapbox_token = os.getenv("MAPBOX_TOKEN")
    if mapbox_token:
        result = _mapbox(address, mapbox_token)
        if result:
            return result

    raise ValueError(f"Could not geocode: {address!r}")


# ── Google Geocoding (rooftop precision) ──────────────────────────────────────

def _google(address: str, api_key: str) -> dict | None:
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": api_key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    if data.get("status") != "OK" or not data.get("results"):
        return None
    res = data["results"][0]
    loc = res["geometry"]["location"]
    precision = res["geometry"].get("location_type", "APPROXIMATE")
    confidence_by_precision = {
        "ROOFTOP": 0.95,
        "RANGE_INTERPOLATED": 0.80,
        "GEOMETRIC_CENTER": 0.70,
        "APPROXIMATE": 0.60,
    }
    return {
        "lat": loc["lat"],
        "lon": loc["lng"],
        "display_name": res.get("formatted_address", address),
        "confidence": confidence_by_precision.get(precision, 0.6),
        "source": f"google_{precision.lower()}",
    }


# ── providers ────────────────────────────────────────────────────────────────

def _nominatim(address: str) -> dict | None:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 3, "addressdetails": 1}
    headers = {"User-Agent": "RoofEstimator/1.0 hackathon@jobnimbus.com"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        results = r.json()
        time.sleep(1)  # Nominatim rate limit: 1 req/sec
        if not results:
            return None
        # Prefer results with building/house type
        for hit in results:
            if hit.get("type") in ["house", "building", "residential"]:
                return {
                    "lat": float(hit["lat"]),
                    "lon": float(hit["lon"]),
                    "display_name": hit.get("display_name", address),
                    "confidence": float(hit.get("importance", 0.5)),
                    "source": "nominatim",
                }
        # Fall back to first result
        hit = results[0]
        return {
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "display_name": hit.get("display_name", address),
            "confidence": float(hit.get("importance", 0.5)),
            "source": "nominatim",
        }
    except Exception:
        return None


def _mapbox(address: str, token: str) -> dict | None:
    encoded = requests.utils.quote(address)
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded}.json"
    params = {"access_token": token, "limit": 1, "types": "address"}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        features = data.get("features", [])
        if not features:
            return None
        feat = features[0]
        lon, lat = feat["center"]
        return {
            "lat": lat,
            "lon": lon,
            "display_name": feat.get("place_name", address),
            "confidence": feat.get("relevance", 0.5),
            "source": "mapbox",
        }
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    addr = " ".join(sys.argv[1:]) or "3561 E 102nd Ct, Thornton, CO 80229"
    print(geocode(addr))
