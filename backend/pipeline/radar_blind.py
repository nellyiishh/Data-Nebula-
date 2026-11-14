"""Radar blind spots: slopes NISAR cannot see from its look direction.

- Layover: ground rising toward the sensor more steeply than the incidence angle. The top
  of the slope echoes before its foot, so the pixels fold over each other.
- Shadow: ground falling away from the sensor more steeply than the grazing angle
  (90° - incidence). The beam never reaches it.

This is the local-slope test only: a ridge that hides a valley further away is not caught.
GCOV has no layover/shadow layer of its own (its `mask` is the valid-subswath mask).
"""

import hashlib
import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.core.geo import mercator_to_lonlat
from app.core.logging import get_logger
from app.features.sites.models import MercatorBounds

log = get_logger("radar_blind")

Array = NDArray[np.floating]
DemSource = Callable[[MercatorBounds, tuple[int, int]], Array]
COPERNICUS_DEM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"  # AWS Open Data, no key
)


def blind_mask(
    dem: Array,
    bounds_merc: MercatorBounds,
    los_east: float,
    los_north: float,
    incidence_deg: float,
) -> NDArray[np.bool_]:
    """dem: heights (m) on the site's Mercator grid, row 0 = north, NaN = unknown.
    los_east/los_north: horizontal part of the unit vector from the ground to the sensor."""
    horizontal = math.hypot(los_east, los_north)
    if horizontal < 1e-6:
        raise ValueError("the look direction needs a horizontal part")
    toward_east, toward_north = los_east / horizontal, los_north / horizontal

    rows, cols = dem.shape
    xmin, ymin, xmax, ymax = bounds_merc
    # A Mercator metre covers cos(latitude) real metres, so ground spacing shrinks by row.
    row_lats = [
        mercator_to_lonlat(0.0, ymax - (r + 0.5) * (ymax - ymin) / rows)[1] for r in range(rows)
    ]
    shrink = np.cos(np.radians(row_lats))[:, None]
    dx = (xmax - xmin) / cols * shrink
    dy = (ymax - ymin) / rows * shrink

    dz_drow, dz_dcol = np.gradient(dem)
    rise_east = dz_dcol / dx
    rise_north = -dz_drow / dy  # row index grows southward
    # Slope angle along the horizontal look direction; positive = faces the sensor.
    facing = np.degrees(np.arctan(rise_east * toward_east + rise_north * toward_north))
    with np.errstate(invalid="ignore"):
        layover = facing > incidence_deg
        shadow = -facing > 90.0 - incidence_deg
    return np.isfinite(facing) & (layover | shadow)


def _tile_names(bounds_merc: MercatorBounds) -> list[str]:
    west, south = mercator_to_lonlat(bounds_merc[0], bounds_merc[1])
    east, north = mercator_to_lonlat(bounds_merc[2], bounds_merc[3])
    names = []
    for lat in range(math.floor(south), math.floor(north) + 1):
        for lon in range(math.floor(west), math.floor(east) + 1):
            ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
            names.append(f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM")
    return names


def fetch_copernicus_dem(bounds_merc: MercatorBounds, shape: tuple[int, int]) -> Array:
    """Copernicus GLO-30 heights resampled onto the site grid. Reads only the window it
    needs from each 1°x1° cloud-optimised tile; NaN where no tile exists (sea)."""
    import rasterio
    from rasterio.errors import RasterioIOError
    from rasterio.transform import from_bounds
    from rasterio.warp import Resampling, reproject

    rows, cols = shape
    dem = np.full(shape, np.nan, dtype="f8")
    transform = from_bounds(*bounds_merc, width=cols, height=rows)
    for name in _tile_names(bounds_merc):
        tile = np.full(shape, np.nan, dtype="f8")
        try:
            with rasterio.open(COPERNICUS_DEM_URL.format(name=name)) as src:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=tile,
                    dst_transform=transform,
                    dst_crs="EPSG:3857",
                    dst_nodata=np.nan,
                    resampling=Resampling.bilinear,
                )
        except RasterioIOError:
            log.info("no DEM tile %s (open sea or outside coverage)", name)
            continue
        dem = np.where(np.isfinite(tile), tile, dem)
    return dem


def cached_dem(
    bounds_merc: MercatorBounds, shape: tuple[int, int], cache_dir: Path, source: DemSource
) -> Array:
    """Cache: owner = this pipeline, data/raw/<site>/ (gitignored). No TTL: the DEM does not
    change. Invalidation: a different grid is a different file; delete it to refetch."""
    key = hashlib.sha256(repr((tuple(round(v, 3) for v in bounds_merc), shape)).encode())
    path = cache_dir / f"dem.{key.hexdigest()[:10]}.npy"
    if path.is_file():
        return np.load(path)
    dem = source(bounds_merc, shape)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, dem)
    return dem
