"""Camera (true-colour) pictures of a site from NASA HLS, for Radar Vision and before/after.

    uv run --group pipeline python -m pipeline.optical --site toguz-bulak

HLS v2.0 (Harmonized Landsat 8/9 + Sentinel-2, 30 m) is searched over the site from 8 days
before the first radar pass until today. Each scene's cloud mask (Fmask) is read for the
site only, to measure how clear OUR area is (the catalogue's cloud % is for a 110 km tile).
For every radar pass the clearest scene within 8 days on the same side of the event is
kept, plus the first clear scene after the event. Only small windows are read, never whole
files. Needs the site already prepared (its grid) and EARTHDATA_TOKEN in backend/.env.

Writes data/ext/<site>/optical/<date>.png and data/ext/<site>/optical.json (scene IDs and
clear %); write_site turns them into the optical layer, so rerun pipeline.prepare_nisar.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.core.config import Settings
from app.core.logging import configure_logging, get_logger
from app.features.sites.models import MercatorBounds
from app.features.sites.rendering import encode_png
from app.features.sites.repository import STACK_FILE
from app.features.sites.schemas import SiteDetail
from pipeline.derived import OPTICAL_DIR, OPTICAL_NUMBERS_FILE
from pipeline.http import request_with_retry
from pipeline.prepare_nisar import BACKEND_DIR, EXT_ROOT, RAW_DIR
from pipeline.remote_crop import load_earthdata_env

CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"
HLS_PRODUCTS = ("HLSS30", "HLSL30")  # Sentinel-2 and Landsat 8/9, both version 2.0
HLS_VERSION = "2.0"
RGB_BANDS = ("B04", "B03", "B02")  # red, green, blue: same names in both products
FMASK = "Fmask"
REFLECTANCE_SCALE = 1e-4
REFLECTANCE_FILL = -9999
FMASK_FILL = 255
# Fmask bits that hide the ground: 1 cloud, 2 next to cloud or shadow, 3 cloud shadow.
# Bit 0 (cirrus) is reserved in HLS v2; snow (4) and water (5) are real ground, kept.
NOT_CLEAR_BITS = 0b1110
MIN_CLEAR = 0.8
WINDOW_DAYS = 8
# One fixed stretch for every picture, so dates compare honestly (no per-image contrast).
MAX_REFLECTANCE = 0.35
GAMMA = 1 / 1.6

OPTICAL_NUMBERS = PurePosixPath(OPTICAL_NUMBERS_FILE).name
log = get_logger("optical")
Array = NDArray[np.floating]


@dataclass(frozen=True)
class Scene:
    scene_id: str
    acquired: dt.datetime
    band_urls: dict[str, str]

    @property
    def date(self) -> dt.date:
        return self.acquired.date()


@dataclass(frozen=True)
class SiteGrid:
    """The prepared site's EPSG:3857 grid: every layer shares these bounds and this shape."""

    bounds_merc: MercatorBounds
    shape: tuple[int, int]  # rows, cols


Search = Callable[[], list[Scene]]
Reader = Callable[[Scene, str, SiteGrid], Array]


def clear_fraction(fmask: Array) -> float:
    """Share of pixels with data where the ground is visible."""
    valid = np.isfinite(fmask)
    if not valid.any():
        return 0.0
    bits = fmask[valid].astype(np.uint8)
    return float(((bits & NOT_CLEAR_BITS) == 0).mean())


def _side(date: dt.date, event: dt.date) -> bool:
    """True = after the event. A scene on the event day is before it: HLS passes are around
    05-06 UTC, and slides are usually reported later in the day."""
    return date > event


def choose_frames(
    candidates: list[tuple[Scene, float]],
    radar_dates: list[dt.date],
    event: dt.date,
    min_clear: float = MIN_CLEAR,
    window_days: int = WINDOW_DAYS,
) -> list[tuple[Scene, float]]:
    clear = [(s, c) for s, c in candidates if c >= min_clear]
    chosen: dict[str, tuple[Scene, float]] = {}
    for radar in radar_dates:
        near = [
            (s, c)
            for s, c in clear
            if abs((s.date - radar).days) <= window_days
            and _side(s.date, event) == _side(radar, event)
        ]
        if near:
            best = max(near, key=lambda sc: (sc[1], -abs((sc[0].date - radar).days)))
            chosen[best[0].scene_id] = best
    after = sorted((sc for sc in clear if _side(sc[0].date, event)), key=lambda sc: sc[0].date)
    if after and not any(_side(s.date, event) for s, _ in chosen.values()):
        chosen[after[0][0].scene_id] = after[0]
    frames = sorted(chosen.values(), key=lambda sc: sc[0].acquired)
    # Two products can image the same day; keep the clearer one (the web keys frames by date).
    by_day: dict[dt.date, tuple[Scene, float]] = {}
    for scene, c in frames:
        if scene.date not in by_day or c > by_day[scene.date][1]:
            by_day[scene.date] = (scene, c)
    return [by_day[day] for day in sorted(by_day)]


def true_colour_rgba(red: Array, green: Array, blue: Array) -> NDArray[np.uint8]:
    def channel(band: Array) -> NDArray[np.uint8]:
        scaled = np.clip(np.nan_to_num(band, nan=0.0) / MAX_REFLECTANCE, 0.0, 1.0) ** GAMMA
        return (scaled * 255).round().astype(np.uint8)

    valid = np.isfinite(red) & np.isfinite(green) & np.isfinite(blue)
    alpha = np.where(valid, 255, 0).astype(np.uint8)
    return np.dstack([channel(red), channel(green), channel(blue), alpha])


def run_optical(
    site_id: str,
    grid: SiteGrid,
    radar_dates: list[dt.date],
    event: dt.date,
    ext_root: Path,
    search: Search,
    read: Reader,
) -> Path:
    scenes = search()
    candidates: list[tuple[Scene, float]] = []
    for scene in scenes:
        try:
            clear = clear_fraction(read(scene, FMASK, grid))
        except Exception as exc:  # one unreadable scene must not stop the others
            log.warning("%s %s skipped: %s", scene.date, scene.scene_id, exc)
            continue
        candidates.append((scene, clear))
        log.info("%s %s: %.0f%% clear over the site", scene.date, scene.scene_id, clear * 100)
    chosen = choose_frames(candidates, radar_dates, event)
    if not chosen:
        raise ValueError(
            f"{site_id}: no scene at least {MIN_CLEAR:.0%} clear near any radar pass "
            f"({len(scenes)} searched); the camera layer would only show clouds"
        )
    ext_dir = ext_root / site_id
    (ext_dir / PurePosixPath(OPTICAL_DIR).name).mkdir(parents=True, exist_ok=True)
    frames = []
    for scene, clear in chosen:
        rgb = [read(scene, band, grid) for band in RGB_BANDS]
        relative = f"{OPTICAL_DIR}/{scene.date.isoformat()}.png"
        (ext_dir / PurePosixPath(relative).relative_to("ext")).write_bytes(
            encode_png(true_colour_rgba(*rgb))
        )
        frames.append(
            {
                "date": scene.date.isoformat(),
                "file": relative,
                "scene_id": scene.scene_id,
                "clear_pct": round(clear * 100, 1),
            }
        )
    (ext_dir / OPTICAL_NUMBERS).write_text(json.dumps({"frames": frames}, indent=2) + "\n")
    return ext_dir


# ---- Real catalogue and reader (network) ------------------------------------------------


def cmr_search(bbox: tuple[float, float, float, float], start: dt.date, end: dt.date) -> Search:
    def search() -> list[Scene]:
        scenes: list[Scene] = []
        for product in HLS_PRODUCTS:
            response = request_with_retry(
                "GET",
                CMR_GRANULES,
                params={
                    "short_name": product,
                    "version": HLS_VERSION,
                    "bounding_box": ",".join(str(v) for v in bbox),
                    "temporal": f"{start.isoformat()}T00:00:00Z,{end.isoformat()}T23:59:59Z",
                    "page_size": 500,
                },
                timeout=60,
            )
            response.raise_for_status()
            scenes += [_scene_from_cmr(entry) for entry in response.json()["feed"]["entry"]]
        return sorted(scenes, key=lambda s: s.acquired)

    return search


def _scene_from_cmr(entry: dict[str, Any]) -> Scene:
    urls: dict[str, str] = {}
    for link in entry.get("links", []):
        href = link.get("href", "")
        if href.startswith("https://") and href.endswith(".tif"):
            band = href.rsplit(".", 2)[-2]
            urls.setdefault(band, href)
    acquired = dt.datetime.fromisoformat(entry["time_start"].replace("Z", "+00:00"))
    return Scene(scene_id=entry["title"], acquired=acquired, band_urls=urls)


def _signed_url(url: str, token: str) -> str:
    """LP DAAC answers with a redirect to a short-lived signed link. GDAL would forward our
    login header to that host and be refused, so resolve the link first, then read it."""
    response = request_with_retry(
        "GET",
        url,
        headers={"Authorization": f"Bearer {token}"},
        allow_redirects=False,
        timeout=60,
    )
    location = response.headers.get("Location")
    if response.status_code in (301, 302, 303, 307, 308) and location:
        return location
    response.raise_for_status()
    return url


def hls_reader(token: str) -> Reader:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds as transform_from_bounds
    from rasterio.warp import reproject, transform_bounds
    from rasterio.windows import from_bounds as window_from_bounds

    def read(scene: Scene, band: str, grid: SiteGrid) -> Array:
        rows, cols = grid.shape
        dst_transform = transform_from_bounds(*grid.bounds_merc, cols, rows)
        is_mask = band == FMASK
        fill = FMASK_FILL if is_mask else REFLECTANCE_FILL
        with (
            rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"),
            rasterio.open(_signed_url(scene.band_urls[band], token)) as src,
        ):
            west, south, east, north = transform_bounds("EPSG:3857", src.crs, *grid.bounds_merc)
            pad = 2 * abs(src.res[0])  # a little margin so resampling has neighbours
            window = (
                window_from_bounds(
                    west - pad, south - pad, east + pad, north + pad, transform=src.transform
                )
                .round_offsets()
                .round_lengths()
            )
            data = src.read(1, window=window, boundless=True, fill_value=fill)
            out = np.full(grid.shape, fill, dtype=data.dtype)
            reproject(
                source=data,
                destination=out,
                src_transform=src.window_transform(window),
                src_crs=src.crs,
                src_nodata=fill,
                dst_transform=dst_transform,
                dst_crs="EPSG:3857",
                dst_nodata=fill,
                resampling=Resampling.nearest if is_mask else Resampling.bilinear,
            )
        values = out.astype(np.float32)
        values[out == fill] = np.nan
        return values if is_mask else values * REFLECTANCE_SCALE

    return read


def cached(read: Reader, cache_dir: Path) -> Reader:
    """Saves each (scene, band) window, so a rerun after a network failure is quick.
    The grid is part of the file name: a rebuilt site with a new grid misses the cache."""

    def read_cached(scene: Scene, band: str, grid: SiteGrid) -> Array:
        key = hashlib.sha1(repr((grid.bounds_merc, grid.shape)).encode()).hexdigest()[:10]
        path = cache_dir / f"{scene.scene_id}.{band}.{key}.npy"
        if path.is_file():
            return np.load(path)
        values = read(scene, band, grid)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, values)
        return values

    return read_cached


def load_grid(site_dir: Path) -> SiteGrid:
    with np.load(site_dir / STACK_FILE) as npz:
        xmin, ymin, xmax, ymax = (float(v) for v in npz["bounds_merc"])
        _, rows, cols = npz["hh"].shape
    return SiteGrid(bounds_merc=(xmin, ymin, xmax, ymax), shape=(int(rows), int(cols)))


def main() -> None:
    parser = argparse.ArgumentParser(description="NASA HLS camera pictures for one site.")
    parser.add_argument("--site", required=True, help="prepared site id")
    args = parser.parse_args()
    configure_logging()
    load_earthdata_env(BACKEND_DIR / ".env", os.environ)
    token = os.environ.get("EARTHDATA_TOKEN")
    if not token:
        raise SystemExit("EARTHDATA_TOKEN is not set (backend/.env); HLS needs a token")

    site_dir = Settings().data_dir / args.site
    if not (site_dir / STACK_FILE).is_file():
        raise SystemExit(f"Prepare {args.site!r} first (pipeline.prepare_nisar): no grid yet")
    site = SiteDetail.model_validate_json((site_dir / "site.json").read_text())
    if site.slope_echo is None:
        raise SystemExit(f"{args.site!r} has no slope_echo block (no event date)")
    grid = load_grid(site_dir)
    west, south = site.corners[3]
    east, north = site.corners[1]
    start = site.dates[0] - dt.timedelta(days=WINDOW_DAYS)
    search = cmr_search((west, south, east, north), start, dt.date.today())
    ext_dir = run_optical(
        site.id,
        grid,
        site.dates,
        site.slope_echo.event.date,
        EXT_ROOT,
        search,
        cached(hls_reader(token), RAW_DIR / site.id / "hls"),
    )
    log.info("Wrote %s; rerun pipeline.prepare_nisar to add the camera layer", ext_dir)


if __name__ == "__main__":
    main()
