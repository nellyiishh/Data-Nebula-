"""Turns real NISAR GCOV granules into a prepared site (same files as the demo).

    uv sync --group pipeline
    uv run python -m pipeline.prepare_nisar

Add a site to data/manifest.json (id, name, change_type, bbox [west, south, east, north],
band, granules, optional slope_echo). Extra files the slope_echo block points at go in
data/ext/<site_id>/ and are copied to the site's ext/ folder. Every granule must come from
one track and frame, or viewing-angle differences show up as fake change.
EARTHDATA_TOKEN must be set (backend/.env).

Per granule: remote_crop reads only the bbox of HH/HV (no full download), then this module
despeckles in linear power, resamples onto one shared EPSG:3857 grid, converts to dB and
hands the stack to writer.write_site.
"""

import dataclasses
import functools
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel
from rasterio.warp import Resampling

from app.core.config import REPO_ROOT, Settings
from app.core.logging import configure_logging, get_logger
from app.features.sites.models import MercatorBounds
from app.features.sites.schemas import Acquisition, ChangeType, PointOfInterest
from app.features.sites.slope_echo import SlopeEcho
from pipeline.interferometry import PairLayers, prepare_pair_layers
from pipeline.processing import (
    despeckle,
    mercator_grid,
    resample_to_mercator,
    to_db,
    to_mercator_grid,
)
from pipeline.radar_blind import DemSource, blind_mask, cached_dem, fetch_copernicus_dem
from pipeline.remote_crop import (
    GCOV_SHORT_NAME,
    GUNW_SHORT_NAME,
    BBox,
    Crop,
    PairCrop,
    crop_granule,
    crop_pair,
    load_earthdata_env,
)
from pipeline.writer import SiteMeta, write_site

MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"
BACKEND_DIR = REPO_ROOT / "backend"
RAW_DIR = REPO_ROOT / "data" / "raw"
# data/ext/<site_id>/: files made by teammates (coherence, GeoJSON, rain…), committed.
EXT_ROOT = REPO_ROOT / "data" / "ext"
ATTRIBUTION = (
    "Contains NISAR L-band data (NASA/ISRO), distributed by the ASF DAAC. Processed by Data Nebula."
)
log = get_logger("nisar")


class ManifestSite(BaseModel):
    id: str
    name: str
    change_type: ChangeType
    bbox: tuple[float, float, float, float]
    band: Literal["L", "S"] = "L"
    granules: list[str]
    # CMR collection the granules belong to. Before 21 Oct 2026 only PROVISIONAL exists;
    # keep one collection per site so every date shares one processing version.
    collection: str = GCOV_SHORT_NAME
    points_of_interest: list[PointOfInterest] = []
    # GUNW interferogram IDs, one per consecutive pair of the dates above (landslide sites).
    pairs: list[str] = []
    pair_collection: str = GUNW_SHORT_NAME
    slope_echo: SlopeEcho | None = None


class Manifest(BaseModel):
    sites: list[ManifestSite]


def load_manifest() -> Manifest:
    return Manifest.model_validate(json.loads(MANIFEST_PATH.read_text()))


Cropper = Callable[[str, BBox, Path], Crop]
PairCropper = Callable[[str, BBox, Path], PairCrop]


def prepare_site(
    site: ManifestSite,
    data_dir: Path,
    raw_dir: Path,
    cropper: Cropper | None = None,
    max_side: int = 1024,
    ext_root: Path = EXT_ROOT,
    dem_source: DemSource = fetch_copernicus_dem,
    pair_cropper: PairCropper | None = None,
) -> Path:
    if len(site.granules) < 2:
        raise ValueError(f"{site.id}: a change map needs at least two dates")
    cropper = cropper or functools.partial(crop_granule, collection=site.collection)
    crops = sorted(
        (cropper(granule, site.bbox, raw_dir / site.id) for granule in site.granules),
        key=lambda crop: crop.acquired,
    )
    if len({crop.epsg for crop in crops}) != 1:
        raise ValueError(
            f"{site.id}: granules are not on the same track and frame (UTM zones differ)"
        )

    native_res = float(abs(crops[0].x[1] - crops[0].x[0]))
    bounds, shape = mercator_grid(site.bbox, native_res, max_side)
    stacks = {
        pol: np.stack(
            [to_db(to_mercator_grid(_despeckled(crop), pol, bounds, shape)) for crop in crops]
        )
        for pol in ("HH", "HV")
    }
    meta = SiteMeta(
        id=site.id,
        name=site.name,
        change_type=site.change_type,
        source="nisar",
        acquisitions=[
            Acquisition(
                date=crop.acquired.date(),
                granule_id=crop.granule_id,
                band=site.band,
                polarizations=["HH", "HV"],
            )
            for crop in crops
        ],
        attribution=ATTRIBUTION,
        points_of_interest=site.points_of_interest,
        slope_echo=site.slope_echo,
        ext_dir=ext_dir if (ext_dir := ext_root / site.id).is_dir() else None,
    )
    blind = (
        _radar_blind(crops, bounds, shape, raw_dir / site.id, dem_source)
        if site.slope_echo is not None
        else None
    )
    pair_cropper = pair_cropper or functools.partial(crop_pair, collection=site.pair_collection)
    pairs = _pair_layers(site, crops, bounds, shape, raw_dir / site.id, pair_cropper)
    return write_site(
        data_dir,
        meta,
        hh=stacks["HH"],
        hv=stacks["HV"],
        bounds_merc=bounds,
        blind_mask=blind,
        pairs=pairs,
    )


def _pair_layers(
    site: ManifestSite,
    crops: list[Crop],
    bounds: MercatorBounds,
    shape: tuple[int, int],
    cache_dir: Path,
    pair_cropper: PairCropper,
) -> PairLayers | None:
    """Coherence and motion for each listed pair, on the same grid as the brightness."""
    if not site.pairs:
        return None
    pair_crops = sorted(
        (pair_cropper(granule, site.bbox, cache_dir) for granule in site.pairs),
        key=lambda crop: crop.reference,
    )
    dates = {crop.acquired.date() for crop in crops}
    for pair in pair_crops:
        if pair.epsg != crops[0].epsg:
            raise ValueError(f"{pair.granule_id} is not on the same track and frame as the passes")
        missing = {pair.reference.date(), pair.secondary.date()} - dates
        if missing:
            raise ValueError(
                f"{pair.granule_id} uses date(s) {sorted(str(d) for d in missing)} that the "
                "site's passes do not include"
            )
    coherence = np.stack(
        [
            resample_to_mercator(
                p.coherence.values,
                p.coherence.x,
                p.coherence.y,
                p.epsg,
                bounds,
                shape,
                Resampling.average,
            )
            for p in pair_crops
        ]
    )
    # 80 m phase onto a ~20 m grid: interpolate rather than paint 4x4 blocks.
    phase = np.stack(
        [
            resample_to_mercator(
                p.phase.values, p.phase.x, p.phase.y, p.epsg, bounds, shape, Resampling.bilinear
            )
            for p in pair_crops
        ]
    )
    coherence, los = prepare_pair_layers(coherence, phase, pair_crops[0].wavelength_m)
    return PairLayers(
        pairs=[(p.reference.date(), p.secondary.date()) for p in pair_crops],
        coherence=coherence,
        los_cm=los,
    )


def _radar_blind(
    crops: list[Crop],
    bounds: MercatorBounds,
    shape: tuple[int, int],
    cache_dir: Path,
    dem_source: DemSource,
) -> NDArray[np.bool_] | None:
    """Layover/shadow on the site grid. Every crop is on one track, so the first one's look
    geometry stands for all. A missing DEM only costs the overlay, never the site."""
    geometry = crops[0].geometry
    if geometry is None:
        log.info("no look geometry in %s; skipping radar blind spots", crops[0].granule_id)
        return None
    try:
        dem = cached_dem(bounds, shape, cache_dir, dem_source)
    except Exception as exc:  # network or tile errors: log and carry on without the overlay
        log.warning("DEM unavailable (%s); skipping radar blind spots", exc)
        return None
    # DEM heights are above the geoid, geometry heights above the ellipsoid: tens of metres
    # apart here, far below the cube's height spacing.
    los_east, los_north, incidence = geometry.at_height(float(np.nanmedian(dem)))
    mask = blind_mask(dem, bounds, los_east, los_north, incidence)
    log.info(
        "radar blind spots: %.1f%% of the site (incidence %.1f°)", 100 * mask.mean(), incidence
    )
    return mask


def _despeckled(crop: Crop) -> Crop:
    return dataclasses.replace(
        crop, power={pol: despeckle(block) for pol, block in crop.power.items()}
    )


def main() -> None:
    configure_logging()
    load_earthdata_env(BACKEND_DIR / ".env", os.environ)
    manifest = load_manifest()
    if not manifest.sites:
        log.warning("No sites in %s yet; add one (see this module's docstring).", MANIFEST_PATH)
        return
    for site in manifest.sites:
        log.info("Preparing %s from %d granules", site.id, len(site.granules))
        site_dir = prepare_site(site, Settings().data_dir, RAW_DIR)
        log.info("Wrote %s", site_dir)


if __name__ == "__main__":
    main()
