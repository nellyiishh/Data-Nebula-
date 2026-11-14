"""Turns real NISAR GCOV granules into a prepared site (same files as the demo).

    uv sync --group pipeline
    uv run python -m pipeline.prepare_nisar

Add a site to data/manifest.json (id, name, change_type, bbox [west, south, east, north],
band, granules). Every granule must come from one track and frame, or viewing-angle
differences show up as fake change. EARTHDATA_TOKEN must be set (backend/.env).

Per granule: remote_crop reads only the bbox of HH/HV (no full download), then this module
despeckles in linear power, resamples onto one shared EPSG:3857 grid, converts to dB and
hands the stack to writer.write_site.
"""

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel

from app.core.config import REPO_ROOT, Settings
from app.core.logging import configure_logging, get_logger
from app.features.sites.schemas import Acquisition, ChangeType
from pipeline.processing import despeckle, mercator_grid, to_db, to_mercator_grid
from pipeline.remote_crop import BBox, Crop, crop_granule
from pipeline.writer import SiteMeta, write_site

MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"
RAW_DIR = REPO_ROOT / "data" / "raw"
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


class Manifest(BaseModel):
    sites: list[ManifestSite]


def load_manifest() -> Manifest:
    return Manifest.model_validate(json.loads(MANIFEST_PATH.read_text()))


Cropper = Callable[[str, BBox, Path], Crop]


def prepare_site(
    site: ManifestSite,
    data_dir: Path,
    raw_dir: Path,
    cropper: Cropper = crop_granule,
    max_side: int = 1024,
) -> Path:
    if len(site.granules) < 2:
        raise ValueError(f"{site.id}: a change map needs at least two dates")
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
    )
    return write_site(data_dir, meta, hh=stacks["HH"], hv=stacks["HV"], bounds_merc=bounds)


def _despeckled(crop: Crop) -> Crop:
    return dataclasses.replace(
        crop, power={pol: despeckle(block) for pol, block in crop.power.items()}
    )


def main() -> None:
    configure_logging()
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
