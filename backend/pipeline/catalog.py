"""Registered landslides near a site from NASA COOLR, for the "registered events" list.

    uv run --group pipeline python -m pipeline.catalog --site toguz-bulak [--radius-km 100]

COOLR (Cooperative Open Online Landslide Repository) holds NASA's Global Landslide Catalog
(GLC) and volunteer Landslide Reporter entries. One query asks for every report within the
radius of the slide (same centre as pipeline.exposure); the newest ones become the catalog.
Writes data/ext/<site>/catalog.json; write_site adds it to the slope_echo block, so rerun
pipeline.prepare_nisar. Report-based: a missing entry means nobody reported one, not that
nothing happened.
"""

import argparse
import datetime as dt
import json
import math
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.logging import configure_logging, get_logger
from app.features.sites.slope_echo import CatalogEntry, SourceRef
from pipeline.derived import CATALOG_NUMBERS_FILE
from pipeline.exposure import Center, exposure_center, haversine_km
from pipeline.http import request_with_retry
from pipeline.prepare_nisar import EXT_ROOT, ManifestSite, load_manifest

COOLR_REPORTS = (
    "https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/"
    "COOLR_Reports_Points/FeatureServer/0/query"
)
CATALOG_FILE = PurePosixPath(CATALOG_NUMBERS_FILE).name
DEFAULT_RADIUS_KM = 100.0
DEFAULT_LIMIT = 10
COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

Query = Callable[[dict[str, Any]], dict[str, Any]]
log = get_logger("catalog")


def compass(lon1: float, lat1: float, lon2: float, lat2: float) -> str:
    """Eight-point direction from point 1 to point 2."""
    dx = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    dy = lat2 - lat1
    bearing = math.degrees(math.atan2(dx, dy)) % 360
    return COMPASS[round(bearing / 45) % 8]


def _date(value: Any) -> dt.date | None:
    if isinstance(value, int | float):  # ArcGIS dates are milliseconds since 1970, UTC
        return dt.datetime.fromtimestamp(value / 1000, dt.UTC).date()
    return None


def catalog_entries(
    features: list[dict[str, Any]], center: Center, limit: int = DEFAULT_LIMIT
) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    for feature in features:
        attrs = feature.get("attributes", {})
        geometry = feature.get("geometry") or {}
        date = _date(attrs.get("event_date"))
        if date is None or "x" not in geometry:
            continue
        lon, lat = geometry["x"], geometry["y"]
        distance = haversine_km(center.lon, center.lat, lon, lat)
        title = attrs.get("event_title") or attrs.get("location_description") or "Landslide"
        kind = ", ".join(
            str(attrs[k]).replace("_", " ")
            for k in ("landslide_category", "landslide_trigger")
            if attrs.get(k) and attrs[k] != "unknown"
        )
        origin = attrs.get("event_import_source")
        reporter = attrs.get("source_name")
        entries.append(
            CatalogEntry(
                date=date,
                type=kind or "landslide",
                name=f"{title} ({distance:.0f} km {compass(center.lon, center.lat, lon, lat)})",
                source=SourceRef(
                    name=" · ".join(
                        part
                        for part in (f"NASA COOLR ({origin})" if origin else "NASA COOLR", reporter)
                        if part
                    ),
                    url=attrs.get("source_link") or None,
                ),
            )
        )
    return sorted(entries, key=lambda e: e.date, reverse=True)[:limit]


def query_coolr(params: dict[str, Any]) -> dict[str, Any]:
    response = request_with_retry("GET", COOLR_REPORTS, params=params, timeout=90)
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(f"COOLR query failed: {body['error']}")
    return body


def run_catalog(
    site: ManifestSite,
    ext_root: Path = EXT_ROOT,
    radius_km: float = DEFAULT_RADIUS_KM,
    query: Query = query_coolr,
    limit: int = DEFAULT_LIMIT,
) -> Path:
    center = exposure_center(site)
    body = query(
        {
            "f": "json",
            "geometry": f"{center.lon},{center.lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "outSR": 4326,
            "distance": round(radius_km * 1000),
            "units": "esriSRUnit_Meter",
            "outFields": "*",
            "returnGeometry": "true",
            "resultRecordCount": 2000,
        }
    )
    features = body.get("features", [])
    entries = catalog_entries(features, center, limit)
    ext_dir = ext_root / site.id
    ext_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "radius_km": radius_km,
        "center": center.label,
        "reports_found": len(features),
        "fetched": dt.date.today().isoformat(),
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    (ext_dir / CATALOG_FILE).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    nearest = min(
        (
            haversine_km(center.lon, center.lat, f["geometry"]["x"], f["geometry"]["y"])
            for f in features
            if f.get("geometry")
        ),
        default=None,
    )
    log.info(
        "%s: %d reports within %g km of %s (nearest %s), newest %s; kept %d",
        site.id,
        len(features),
        radius_km,
        center.label,
        f"{nearest:.0f} km" if nearest is not None else "none",
        entries[0].date if entries else "none",
        len(entries),
    )
    return ext_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="NASA COOLR landslide reports near one site.")
    parser.add_argument("--site", required=True, help="site id in data/manifest.json")
    parser.add_argument("--radius-km", type=float, default=DEFAULT_RADIUS_KM)
    args = parser.parse_args()
    configure_logging()
    site = next((s for s in load_manifest().sites if s.id == args.site), None)
    if site is None:
        raise SystemExit(f"No site {args.site!r} in data/manifest.json")
    ext_dir = run_catalog(site, radius_km=args.radius_km)
    log.info("Wrote %s; rerun pipeline.prepare_nisar to add it to the site", ext_dir)


if __name__ == "__main__":
    main()
