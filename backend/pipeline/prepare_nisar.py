"""Turns real NISAR GCOV granules into a prepared site (same files as the demo).

    uv sync --group pipeline
    uv run python -m pipeline.prepare_nisar

TODO(nisar-pipeline): not implemented yet. Steps, in order:
  1. Add the site to data/manifest.json: id, name, change_type, bbox [west, south, east,
     north], and the GCOV granule IDs. Every date must share one track and frame, or
     viewing-angle differences show up as fake change.
  2. Download each granule into data/raw/<site_id>/ from ASF (needs an Earthdata login).
  3. Read /science/LSAR/GCOV/grids/frequencyA/HHHH and .../HVHV with h5py, plus the
     xCoordinates / yCoordinates / projection datasets of the same group.
  4. Crop to the bbox. Power → dB with 10*log10; zeros and fill values → NaN.
  5. Reduce speckle with scipy.ndimage.median_filter (size 3–5).
  6. Reproject every date onto ONE shared EPSG:3857 grid (rasterio.warp.reproject).
  7. Call pipeline.writer.write_site(...) with source="nisar" and real granule IDs.
"""

import json
from typing import Literal

from pydantic import BaseModel

from app.core.config import REPO_ROOT
from app.core.logging import configure_logging, get_logger
from app.features.sites.schemas import ChangeType

MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"
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


def main() -> None:
    configure_logging()
    manifest = load_manifest()
    if not manifest.sites:
        log.warning("No sites in %s yet; add one (see this module's docstring).", MANIFEST_PATH)
        return
    raise NotImplementedError("TODO(nisar-pipeline): steps 2-7 in this module's docstring")


if __name__ == "__main__":
    main()
