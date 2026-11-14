"""Turns cropped NISAR power into dB images on one shared Web Mercator grid.

Order matters: speckle filtering and reprojection both average pixels, so they must work in
linear power. Converting to dB first would bias every average low.
"""

import math

import numpy as np
from numpy.typing import NDArray
from rasterio.transform import Affine, from_bounds
from rasterio.warp import Resampling, reproject
from scipy.ndimage import uniform_filter

from app.core.geo import lonlat_to_mercator
from app.features.sites.models import MercatorBounds
from pipeline.remote_crop import BBox, Crop

Array = NDArray[np.floating]


def to_db(power: Array) -> Array:
    """Linear power → dB. NaN stays NaN; callers have already turned zeros into NaN."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(power)


def despeckle(power: Array, size: int = 3) -> Array:
    """Boxcar multilook on linear power that ignores no-data pixels.

    A plain box filter would drag values near a NaN toward 0, so it is normalised by the
    count of valid pixels in each window. Pixels that were NaN stay NaN.
    """
    valid = np.isfinite(power)
    total = uniform_filter(np.where(valid, power, 0.0).astype("f8"), size, mode="nearest")
    count = uniform_filter(valid.astype("f8"), size, mode="nearest")
    with np.errstate(divide="ignore", invalid="ignore"):
        smoothed = np.where(count > 0, total / count, np.nan)
    smoothed[~valid] = np.nan
    return smoothed.astype("f4")


def mercator_grid(
    bbox: BBox, native_res_m: float, max_side: int = 1024
) -> tuple[MercatorBounds, tuple[int, int]]:
    """Bounds and (rows, cols) of the site's output grid.

    Pixels are about the radar's native size on the ground, but the longest side is capped:
    the browser downloads one PNG per layer and date, so size matters more than the last
    few metres of detail.
    """
    west, south, east, north = bbox
    xmin, ymin = lonlat_to_mercator(west, south)
    xmax, ymax = lonlat_to_mercator(east, north)
    # Mercator stretches distances by 1/cos(lat), so a ground metre is longer on the grid.
    pixel = native_res_m / math.cos(math.radians((south + north) / 2))
    rows, cols = math.ceil((ymax - ymin) / pixel), math.ceil((xmax - xmin) / pixel)
    scale = min(1.0, max_side / max(rows, cols))
    return (xmin, ymin, xmax, ymax), (max(1, round(rows * scale)), max(1, round(cols * scale)))


def to_mercator_grid(
    crop: Crop, polarisation: str, bounds: MercatorBounds, shape: tuple[int, int]
) -> Array:
    """Resample one polarisation of a UTM crop onto the shared EPSG:3857 grid (row 0 = north).

    Area-averages when shrinking, and leaves NaN where the crop has no data.
    """
    return resample_to_mercator(
        crop.power[polarisation], crop.x, crop.y, crop.epsg, bounds, shape, Resampling.average
    )


def resample_to_mercator(
    values: Array,
    x: Array,
    y: Array,
    epsg: int,
    bounds: MercatorBounds,
    shape: tuple[int, int],
    resampling: Resampling,
) -> Array:
    """Any UTM raster (pixel-centre x ascending, y descending) onto the site grid.
    Use average for same-or-finer sources, bilinear to upsample a coarser one."""
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])  # dy is negative
    # x / y are pixel centres; an affine transform wants the top-left corner of the grid.
    source_transform = Affine(dx, 0.0, float(x[0]) - dx / 2, 0.0, dy, float(y[0]) - dy / 2)
    xmin, ymin, xmax, ymax = bounds
    rows, cols = shape
    out = np.full(shape, np.nan, dtype="f4")
    reproject(
        source=np.ascontiguousarray(values, dtype="f4"),
        destination=out,
        src_transform=source_transform,
        src_crs=f"EPSG:{epsg}",
        dst_transform=from_bounds(xmin, ymin, xmax, ymax, cols, rows),
        dst_crs="EPSG:3857",
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return out
