"""Find listings near a campus.

Two steps, because SQLite cannot do the distance formula itself:
    1. the database picks everything inside a rectangle   (cheap)
    2. Python measures the real distance of those few     (exact)
"""

import math

EARTH_RADIUS_KM = 6371.0
KM_PER_DEGREE_LAT = 111.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two points on Earth, in kilometres."""
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    d_lat = lat2 - lat1
    d_lon = lon2 - lon1

    a = (math.sin(d_lat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2)

    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(latitude, longitude, radius_km):
    """A rectangle that definitely contains everything within radius_km."""
    lat_delta = radius_km / KM_PER_DEGREE_LAT

    # Longitude degrees get narrower away from the equator.
    km_per_degree_lon = KM_PER_DEGREE_LAT * math.cos(math.radians(latitude))
    lon_delta = radius_km / km_per_degree_lon

    return {
        "lat_min": latitude - lat_delta,
        "lat_max": latitude + lat_delta,
        "lon_min": longitude - lon_delta,
        "lon_max": longitude + lon_delta,
    }


def listings_near_university(university, radius_km, viewer):
    """Visible listings within radius_km of a campus, nearest first."""
    from .models import Listing

    campus_lat = university.latitude
    campus_lon = university.longitude
    box = bounding_box(campus_lat, campus_lon, radius_km)

    # Step 1 — the rectangle. visible_to() runs first, so a listing this
    # viewer may not see is never even measured.
    candidates = Listing.visible_to(viewer).filter(
        latitude__gte=box["lat_min"], latitude__lte=box["lat_max"],
        longitude__gte=box["lon_min"], longitude__lte=box["lon_max"],
    )

    # Step 2 — the real distance.
    results = []
    for listing in candidates:
        distance = haversine_km(
            campus_lat, campus_lon, listing.latitude, listing.longitude)

        if distance <= radius_km:
            results.append({
                "listing": listing,
                "distance_km": round(distance, 2),
            })

    results.sort(key=lambda row: row["distance_km"])
    return results
