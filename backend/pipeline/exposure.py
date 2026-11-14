"""Buildings and roads near a landslide from OpenStreetMap, for the "Earth impact" screen.

    uv run --group pipeline python -m pipeline.exposure --site toguz-bulak [--radius-km 2]

Asks the public Overpass API once for buildings, roads and named places around the slide,
then writes data/ext/<site>/exposure.geojson (buildings as points, roads as lines) and
data/ext/<site>/exposure.json (the counts). write_site copies both into the site and adds
them to the slope_echo block, so rerun pipeline.prepare_nisar afterwards.

The centre is the point of interest with id "slide" if the manifest has one, else the first
point of interest, else the middle of the bbox. It counts what is near, not what is at risk.
"""

import argparse
import datetime as dt
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.logging import configure_logging, get_logger
from app.features.sites.slope_echo import Exposure, SourceRef
from pipeline.derived import EXPOSURE_FILE, EXPOSURE_NUMBERS_FILE, EXPOSURE_OVERLAY
from pipeline.prepare_nisar import EXT_ROOT, ManifestSite, load_manifest

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass asks clients to identify themselves; a project name, no personal details.
USER_AGENT = "data-nebula/0.1 (NASA Space Apps 2026 hackathon project)"
# Same names derived.py looks for once write_site has copied ext/ into the site.
EXPOSURE_GEOJSON = PurePosixPath(EXPOSURE_FILE).name
EXPOSURE_NUMBERS = PurePosixPath(EXPOSURE_NUMBERS_FILE).name
SLIDE_POINT_ID = "slide"
DEFAULT_RADIUS_KM = 2.0
PLACE_SEARCH_KM = 15.0
EARTH_RADIUS_KM = 6371.0088

# Roads a vehicle can use. Rural Kyrgyz roads are mostly "unclassified" or "track", so both
# count; footpaths, steps and cycleways do not.
ROAD_CLASSES = frozenset(
    {
        "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
        "residential", "living_street", "service", "track", "road",
        "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
    }
)  # fmt: skip
PLACE_CLASSES = ("city", "town", "village", "hamlet", "isolated_dwelling")
OSM_SOURCE: SourceRef = EXPOSURE_OVERLAY.source

Element = dict[str, Any]
Fetcher = Callable[[str], dict[str, Any]]
log = get_logger("exposure")


@dataclass(frozen=True)
class Center:
    lon: float
    lat: float
    label: str
    is_slide: bool = False


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def exposure_center(site: ManifestSite) -> Center:
    points = site.points_of_interest
    slide = next((p for p in points if p.id == SLIDE_POINT_ID), None)
    if slide:
        return Center(slide.lon, slide.lat, slide.name, is_slide=True)
    if points:
        return Center(points[0].lon, points[0].lat, points[0].name)
    west, south, east, north = site.bbox
    return Center((west + east) / 2, (south + north) / 2, "the centre of the study area")


def overpass_query(center: Center, radius_km: float) -> str:
    near = f"(around:{round(radius_km * 1000)},{center.lat},{center.lon})"
    places = f"(around:{round(PLACE_SEARCH_KM * 1000)},{center.lat},{center.lon})"
    place_pattern = "|".join(PLACE_CLASSES)
    return (
        "[out:json][timeout:90];("
        f'node["building"]{near};way["building"]{near};relation["building"]{near};'
        f'way["highway"]{near};'
        f'node["place"~"^({place_pattern})$"]["name"]{places};'
        ");out geom;"
    )


# The public Overpass servers are often busy; these answers mean "try again shortly".
RETRY_STATUSES = frozenset({429, 502, 503, 504})
RETRY_WAITS_S = (10, 30)


def fetch_overpass(query: str, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    import requests  # pipeline-only dependency

    for wait in (*RETRY_WAITS_S, None):
        response = requests.post(
            OVERPASS_URL, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=120
        )
        if response.status_code not in RETRY_STATUSES or wait is None:
            response.raise_for_status()
            return response.json()
        log.warning("Overpass answered %d; retrying in %ds", response.status_code, wait)
        sleep(wait)
    raise AssertionError("unreachable")


def _position(element: Element) -> tuple[float, float] | None:
    """A representative point: the node itself, a way's vertex mean, or a relation's box."""
    if "lon" in element and "lat" in element:
        return element["lon"], element["lat"]
    geometry = element.get("geometry") or []
    if len(geometry) > 1 and geometry[0] == geometry[-1]:
        geometry = geometry[:-1]  # closed ring: the first vertex is repeated at the end
    if geometry:
        return (
            sum(p["lon"] for p in geometry) / len(geometry),
            sum(p["lat"] for p in geometry) / len(geometry),
        )
    if bounds := element.get("bounds"):
        return (bounds["minlon"] + bounds["maxlon"]) / 2, (bounds["minlat"] + bounds["maxlat"]) / 2
    return None


def _distance(center: Center, lon: float, lat: float) -> float:
    return haversine_km(center.lon, center.lat, lon, lat)


KM_PER_DEGREE = math.pi * EARTH_RADIUS_KM / 180


def _to_local(center: Center, lon: float, lat: float) -> tuple[float, float]:
    """Flat km coordinates around the centre; accurate to well under 1% within a few km."""
    x = (lon - center.lon) * KM_PER_DEGREE * math.cos(math.radians(center.lat))
    return x, (lat - center.lat) * KM_PER_DEGREE


def _to_lonlat(center: Center, x: float, y: float) -> list[float]:
    lon = center.lon + x / (KM_PER_DEGREE * math.cos(math.radians(center.lat)))
    return [lon, center.lat + y / KM_PER_DEGREE]


def _clip_segment(
    a: tuple[float, float], b: tuple[float, float], radius_km: float
) -> tuple[float, float] | None:
    """The part [t0, t1] of segment a→b inside the circle (0 = a, 1 = b), or None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    qa = dx * dx + dy * dy
    qb = 2 * (a[0] * dx + a[1] * dy)
    qc = a[0] ** 2 + a[1] ** 2 - radius_km**2
    if qa == 0:
        return (0.0, 1.0) if qc <= 0 else None
    disc = qb * qb - 4 * qa * qc
    if disc < 0:
        return None
    root = math.sqrt(disc)
    t0, t1 = max(0.0, (-qb - root) / (2 * qa)), min(1.0, (-qb + root) / (2 * qa))
    return (t0, t1) if t0 < t1 else None


def _road_runs(
    geometry: list[dict[str, float]], center: Center, radius_km: float
) -> tuple[list[list[list[float]]], float]:
    """Parts of a road inside the circle, cut exactly at its edge, and their length."""
    local = [_to_local(center, p["lon"], p["lat"]) for p in geometry]
    runs: list[list[list[float]]] = []
    current: list[list[float]] = []
    length = 0.0
    for a, b in zip(local, local[1:], strict=False):
        part = _clip_segment(a, b, radius_km)
        if part is None:
            if current:
                runs.append(current)
                current = []
            continue
        t0, t1 = part
        start = (a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1]))
        stop = (a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1]))
        length += math.dist(start, stop)
        if current and t0 > 0:  # re-entered the circle: a new piece of road
            runs.append(current)
            current = []
        if not current:
            current = [_to_lonlat(center, *start)]
        current.append(_to_lonlat(center, *stop))
        if t1 < 1:  # left the circle inside this segment
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs, length


def _feature(kind: str, geometry_type: str, coordinates: Any) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"kind": kind},
        "geometry": {"type": geometry_type, "coordinates": coordinates},
    }


def summarize(
    elements: list[Element], center: Center, radius_km: float
) -> tuple[dict[str, Any], Exposure]:
    features: list[dict[str, Any]] = []
    buildings = 0
    roads_km = 0.0
    places: list[tuple[float, str]] = []

    for element in elements:
        tags = element.get("tags", {})
        position = _position(element)
        if "building" in tags and position:
            if _distance(center, *position) <= radius_km:
                buildings += 1
                features.append(_feature("building", "Point", [position[0], position[1]]))
        elif tags.get("highway") in ROAD_CLASSES and element.get("geometry"):
            runs, length = _road_runs(element["geometry"], center, radius_km)
            roads_km += length
            features += [_feature("road", "LineString", run) for run in runs]
        elif tags.get("place") in PLACE_CLASSES and position:
            name = tags.get("name:en") or tags.get("name")
            if name:
                places.append((_distance(center, *position), name))

    if not places:
        raise ValueError(
            f"No named settlement in OpenStreetMap within {PLACE_SEARCH_KM:g} km of "
            f"{center.label}; check the centre point before reporting exposure"
        )
    distance_km, settlement = min(places)
    exposure = Exposure(
        radius_km=radius_km,
        buildings=buildings,
        roads_km=round(roads_km, 2),
        nearest_settlement=settlement,
        distance_km=round(distance_km, 2),
        method=(
            f"OpenStreetMap buildings (each counted once) and road length within "
            f"{radius_km:g} km of {center.label}, fetched {dt.date.today().isoformat()}. "
            "Roads are drivable classes clipped to the circle; footpaths are left out. "
            + (
                ""
                if center.is_slide
                else "The slide itself is not mapped yet, so this is measured around this "
                "point, not around the slide. "
            )
            + "Counts what is nearby: not a hazard or population estimate, and "
            "OpenStreetMap may miss buildings in rural areas."
        ),
        source=OSM_SOURCE,
    )
    return {"type": "FeatureCollection", "features": features}, exposure


def run_exposure(
    site: ManifestSite,
    ext_root: Path = EXT_ROOT,
    radius_km: float = DEFAULT_RADIUS_KM,
    fetch: Fetcher = fetch_overpass,
) -> Path:
    """Fetches, summarises and writes both files into ext_root/<site>/. Returns that folder."""
    center = exposure_center(site)
    elements = fetch(overpass_query(center, radius_km)).get("elements", [])
    geojson, exposure = summarize(elements, center, radius_km)
    ext_dir = ext_root / site.id
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / EXPOSURE_GEOJSON).write_text(json.dumps(geojson) + "\n")
    (ext_dir / EXPOSURE_NUMBERS).write_text(exposure.model_dump_json(indent=2) + "\n")
    log.info(
        "%s: %d buildings, %.2f km of road within %g km of %s; nearest place %s (%.2f km)",
        site.id,
        exposure.buildings,
        exposure.roads_km,
        radius_km,
        center.label,
        exposure.nearest_settlement,
        exposure.distance_km,
    )
    return ext_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenStreetMap exposure for one site.")
    parser.add_argument("--site", required=True, help="site id in data/manifest.json")
    parser.add_argument("--radius-km", type=float, default=DEFAULT_RADIUS_KM)
    args = parser.parse_args()
    configure_logging()
    site = next((s for s in load_manifest().sites if s.id == args.site), None)
    if site is None:
        raise SystemExit(f"No site {args.site!r} in data/manifest.json")
    ext_dir = run_exposure(site, radius_km=args.radius_km)
    log.info("Wrote %s; rerun pipeline.prepare_nisar to add it to the site", ext_dir)


if __name__ == "__main__":
    main()
