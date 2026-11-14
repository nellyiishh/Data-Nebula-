"""Daily rain over a site from NASA GPM IMERG Late daily (V07), for the rain screen.

    uv run --group pipeline python -m pipeline.rain --site toguz-bulak

Reads ONE 0.1° cell (~10 km) per day through NASA's OPeNDAP service instead of
downloading 27 MB global files. Writes data/ext/<site>/rain.json as {"series": [{date, mm}]},
which write_site then copies into the site. Needs the Earthdata login (backend/.env) and,
once per account, acceptance of the GES DISC archive's terms in Earthdata (otherwise every
request answers 403 "EULA Acceptance Failure").
"""

import argparse
import datetime as dt
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

import h5py
import numpy as np

from app.core.config import REPO_ROOT
from app.core.logging import configure_logging, get_logger
from pipeline.prepare_nisar import BACKEND_DIR, EXT_ROOT, RAW_DIR, load_manifest
from pipeline.remote_crop import load_earthdata_env, require_earthdata_env

IMERG_COLLECTION = "C2723754859-GES_DISC"  # GPM_3IMERGDL version 07
CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"
CELL_DEG = 0.1
FIRST_LON, FIRST_LAT = -179.95, -89.95  # centre of cell (0, 0)
LON_CELLS, LAT_CELLS = 3600, 1800
DAYS_BEFORE_FIRST_PASS = 30  # the web shows 30-day totals before each pass
ACCEPTED_UNITS = {"mm", "mm/day"}  # a daily file's value is that day's total either way
SOURCE = {
    "name": "GPM IMERG Late daily V07 (NASA GES DISC)",
    "url": "https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGDL_07/summary",
}
# Earthdata page where an account approves the GES DISC archive (and its terms) once.
GES_DISC_APPROVAL_URL = (
    "https://urs.earthdata.nasa.gov/approve_app?client_id=e2WVk8Pw6weeLUKZYOxvTQ"
)
log = get_logger("rain")


class RainCellError(ValueError):
    """The returned cell is not what this module can read safely."""


class Response(Protocol):
    @property
    def content(self) -> bytes: ...

    @property
    def status_code(self) -> int: ...

    def raise_for_status(self) -> None: ...


class Session(Protocol):
    def get(self, url: str, *, params: dict[str, str], timeout: float) -> Response: ...


def imerg_index(lon: float, lat: float) -> tuple[int, int]:
    """(lon index, lat index) of the 0.1° cell containing the point."""
    i_lon = round((lon - FIRST_LON) / CELL_DEG)
    i_lat = round((lat - FIRST_LAT) / CELL_DEG)
    return min(max(i_lon, 0), LON_CELLS - 1), min(max(i_lat, 0), LAT_CELLS - 1)


def rain_window(pass_dates: list[dt.date]) -> tuple[dt.date, dt.date]:
    """From 30 days before the first radar pass to the last pass."""
    first, last = min(pass_dates), max(pass_dates)
    return first - dt.timedelta(days=DAYS_BEFORE_FIRST_PASS), last


def read_cell_mm(nc4: bytes) -> float | None:
    """The one precipitation value in an OPeNDAP netCDF-4 subset; None for no data."""
    with h5py.File(io.BytesIO(nc4), "r") as h5:
        node = h5["precipitation"]
        if not isinstance(node, h5py.Dataset):
            raise RainCellError("precipitation is not a dataset")
        units = node.attrs.get("units", b"")
        units = units.decode() if isinstance(units, bytes) else str(units)
        if units not in ACCEPTED_UNITS:
            raise RainCellError(f"unexpected precipitation units {units!r}")
        value = float(np.asarray(node[()]).reshape(-1)[0])
        fill = node.attrs.get("_FillValue")
    fill_value = None if fill is None else float(np.asarray(fill).reshape(-1)[0])
    if not np.isfinite(value) or (fill_value is not None and np.isclose(value, fill_value)):
        return None
    if value < 0:
        return None
    return round(value, 2)


def daily_rain(
    lon: float,
    lat: float,
    granules: list[tuple[dt.date, str]],
    session: Session,
    cache_path: Path,
) -> list[dict[str, Any]]:
    """{date, mm} for each granule. Cache: owner = this module, data/raw/<site>/imerg.json
    (gitignored), keyed by date. No TTL: a published day does not change. Delete to refetch."""
    cache: dict[str, float | None] = (
        json.loads(cache_path.read_text()) if cache_path.is_file() else {}
    )
    i_lon, i_lat = imerg_index(lon, lat)
    constraint = {"dap4.ce": f"/precipitation[0][{i_lon}][{i_lat}]"}
    for date, url in granules:
        key = date.isoformat()
        if key in cache:
            continue
        response = session.get(f"{url}.dap.nc4", params=constraint, timeout=60)
        response.raise_for_status()
        cache[key] = read_cell_mm(response.content)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True))  # resumable
    return [{"date": d.isoformat(), "mm": cache[d.isoformat()]} for d, _ in granules]


def find_granules(start: dt.date, end: dt.date, session: Any) -> list[tuple[dt.date, str]]:
    """(day, OPeNDAP URL) for every IMERG Late daily file in [start, end], from CMR."""
    response = session.get(
        CMR_GRANULES,
        params={
            "collection_concept_id": IMERG_COLLECTION,
            "temporal": f"{start.isoformat()}T00:00:00Z,{end.isoformat()}T23:59:59Z",
            "page_size": "400",
        },
        timeout=60,
    )
    response.raise_for_status()
    granules = []
    for entry in response.json()["feed"]["entry"]:
        day = dt.date.fromisoformat(entry["time_start"][:10])
        urls = [link["href"] for link in entry["links"] if "opendap" in link["href"]]
        if urls:
            granules.append((day, urls[0]))
    return sorted(set(granules))


def _pass_dates(granule_ids: list[str]) -> list[dt.date]:
    stamps = (re.search(r"_(\d{8})T\d{6}_", granule) for granule in granule_ids)
    return [dt.datetime.strptime(m.group(1), "%Y%m%d").date() for m in stamps if m]


def main() -> None:
    import requests

    parser = argparse.ArgumentParser(description="Daily IMERG rain for one manifest site.")
    parser.add_argument("--site", required=True, help="site id in data/manifest.json")
    args = parser.parse_args()
    configure_logging()
    load_earthdata_env(BACKEND_DIR / ".env", os.environ)
    require_earthdata_env(os.environ)

    site = next((s for s in load_manifest().sites if s.id == args.site), None)
    if site is None:
        raise SystemExit(f"No site {args.site!r} in data/manifest.json")
    lon = (site.bbox[0] + site.bbox[2]) / 2
    lat = (site.bbox[1] + site.bbox[3]) / 2
    if site.points_of_interest:  # the first point (the village) says where people are
        lon, lat = site.points_of_interest[0].lon, site.points_of_interest[0].lat

    session = requests.Session()
    if token := os.environ.get("EARTHDATA_TOKEN"):
        session.headers["Authorization"] = f"Bearer {token}"
    start, end = rain_window(_pass_dates(site.granules))
    granules = find_granules(start, end, requests)  # CMR search is public
    log.info("%d IMERG days %s → %s at %.4f N %.4f E", len(granules), start, end, lat, lon)
    try:
        series = daily_rain(lon, lat, granules, session, RAW_DIR / site.id / "imerg.json")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 403:
            raise SystemExit(
                "NASA GES DISC refused the request (403). Accept its terms once for this "
                f"Earthdata account, then rerun: {GES_DISC_APPROVAL_URL}"
            ) from exc
        raise

    out = EXT_ROOT / site.id / "rain.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"series": series}, indent=2) + "\n")
    missing = sum(1 for entry in series if entry["mm"] is None)
    log.info(
        "Wrote %s (%d days, %d without data)", out.relative_to(REPO_ROOT), len(series), missing
    )


if __name__ == "__main__":
    main()
