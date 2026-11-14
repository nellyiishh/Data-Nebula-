"""Reads only a bbox crop of a NISAR GCOV granule, over the network or from a local file.

A GCOV granule is ~0.8-4.5 GB; a site needs a small window of two polarisations. HDF5 is
chunked, so h5py asks only for the chunks the window touches (measured: 80 MB fetched from
an 801 MB file, including the scan that found valid data).

Credentials come from the environment only (EARTHDATA_TOKEN, or EARTHDATA_USERNAME +
EARTHDATA_PASSWORD), never from code.
"""

import datetime as dt
import hashlib
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, cast

import h5py
import numpy as np
from numpy.typing import NDArray
from rasterio.warp import transform_bounds

from app.core.logging import get_logger

log = get_logger("remote_crop")

GCOV_SHORT_NAME = "NISAR_L2_GCOV_V1"
GRID_GROUP = "/science/LSAR/GCOV/grids/frequencyA"
IDENTIFICATION_GROUP = "/science/LSAR/identification"
# GCOV dataset name → polarisation label. The diagonal terms are the backscatter power.
POLARISATIONS = {"HH": "HHHH", "HV": "HVHV"}

# Why these settings: fsspec's default read cache made h5py issue thousands of tiny HTTP
# requests (~3 s latency each from a laptop) and a real run timed out. Fetching 8 MB blocks
# keeps it to a few dozen requests.
OPEN_KWARGS: dict[str, Any] = {"cache_type": "blockcache", "block_size": 8 * 1024 * 1024}

BBox = tuple[float, float, float, float]  # west, south, east, north in lon/lat degrees
Array = NDArray[np.floating]


class CropOutsideFootprintError(ValueError):
    """The bbox does not overlap the granule's grid."""


class EmptyCropError(ValueError):
    """The window is inside the grid but holds no valid pixels (scene edge or masked area)."""


class GranuleNotFoundError(LookupError):
    """CMR returned no (or several) granules for the ID."""


class MissingCredentialsError(RuntimeError):
    """No Earthdata credentials in the environment."""


class Window(NamedTuple):
    r0: int
    r1: int
    c0: int
    c1: int


@dataclass(frozen=True)
class Crop:
    granule_id: str
    acquired: dt.datetime  # UTC start of the acquisition
    epsg: int  # CRS of x / y (UTM)
    x: Array  # column centres, metres, ascending
    y: Array  # row centres, metres, descending
    power: dict[str, Array]  # polarisation → linear power; no-data is NaN


def require_earthdata_env(environ: Mapping[str, str]) -> None:
    """Fail early and name the variables, never their values."""
    if environ.get("EARTHDATA_TOKEN"):
        return
    if environ.get("EARTHDATA_USERNAME") and environ.get("EARTHDATA_PASSWORD"):
        return
    raise MissingCredentialsError(
        "Set EARTHDATA_TOKEN (preferred) or EARTHDATA_USERNAME and EARTHDATA_PASSWORD "
        "in backend/.env or the shell."
    )


def bbox_to_window(x: Array, y: Array, bounds: BBox) -> Window:
    """Rows/columns whose pixel centres fall inside bounds (xmin, ymin, xmax, ymax), in the
    grid's own CRS. x ascends, y descends, as in NISAR GCOV."""
    xmin, ymin, xmax, ymax = bounds
    c0 = np.searchsorted(x, xmin, side="left")
    c1 = np.searchsorted(x, xmax, side="right")
    # y descends, so search its negation (ascending).
    r0 = np.searchsorted(-y, -ymax, side="left")
    r1 = np.searchsorted(-y, -ymin, side="right")
    if c1 <= c0 or r1 <= r0:
        raise CropOutsideFootprintError(f"bounds {bounds} do not overlap the granule grid")
    return Window(r0=int(r0), r1=int(r1), c0=int(c0), c1=int(c1))


def _parse_utc(raw: bytes | str) -> dt.datetime:
    text = raw.decode() if isinstance(raw, bytes) else raw
    # NISAR writes nanoseconds; whole seconds are enough for a revisit-scale product.
    return dt.datetime.fromisoformat(text[:19]).replace(tzinfo=dt.UTC)


def _as_text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def dataset(h5: h5py.File, path: str) -> h5py.Dataset:
    """h5py types `h5[path]` as Group | Dataset | Datatype; every path we read is a dataset."""
    node = h5[path]
    if not isinstance(node, h5py.Dataset):
        raise TypeError(f"{path} is not a dataset")
    return node


def read_crop(h5: h5py.File, bbox: BBox) -> Crop:
    """Crop the granule to a lon/lat bbox. Only the window's chunks are read."""
    epsg = int(dataset(h5, f"{GRID_GROUP}/projection")[()])
    x = np.asarray(dataset(h5, f"{GRID_GROUP}/xCoordinates")[:])
    y = np.asarray(dataset(h5, f"{GRID_GROUP}/yCoordinates")[:])
    bounds = transform_bounds("EPSG:4326", f"EPSG:{epsg}", *bbox, densify_pts=21)
    window = bbox_to_window(x, y, bounds)

    power: dict[str, Array] = {}
    for label, name in POLARISATIONS.items():
        source = dataset(h5, f"{GRID_GROUP}/{name}")
        block = np.asarray(source[window.r0 : window.r1, window.c0 : window.c1], dtype="f4")
        # 0 is NISAR's fill value in power; it would become -inf in dB.
        block[(block == 0) | ~np.isfinite(block)] = np.nan
        power[label] = block
    if not any(np.isfinite(block).any() for block in power.values()):
        raise EmptyCropError("the bbox is inside the grid but holds no valid pixels")

    return Crop(
        granule_id=_as_text(dataset(h5, f"{IDENTIFICATION_GROUP}/granuleId")[()]),
        acquired=_parse_utc(dataset(h5, f"{IDENTIFICATION_GROUP}/zeroDopplerStartTime")[()]),
        epsg=epsg,
        x=x[window.c0 : window.c1],
        y=y[window.r0 : window.r1],
        power=power,
    )


@contextmanager
def open_remote_granule(granule_id: str, short_name: str = GCOV_SHORT_NAME) -> Iterator[h5py.File]:
    """Open one granule from the ASF archive without downloading it."""
    import os

    import earthaccess

    require_earthdata_env(os.environ)
    earthaccess.login(strategy="environment")
    results = earthaccess.search_data(short_name=short_name, granule_ur=granule_id)
    if len(results) != 1:
        raise GranuleNotFoundError(f"{granule_id}: CMR returned {len(results)} granules")
    # earthaccess types this as AbstractFileSystem, but each item is an open file object.
    (remote,) = cast(list[Any], earthaccess.open(results, open_kwargs=OPEN_KWARGS))
    with closing(remote), h5py.File(remote, "r") as h5:
        yield h5


Opener = Callable[[str], AbstractContextManager[h5py.File]]


def _cache_path(cache_dir: Path, granule_id: str, bbox: BBox) -> Path:
    key = hashlib.sha256(repr(tuple(round(v, 6) for v in bbox)).encode()).hexdigest()[:10]
    return cache_dir / f"{granule_id}.{key}.npz"


def _save(path: Path, crop: Crop) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, Any] = {
        "granule_id": crop.granule_id,
        "acquired": crop.acquired.isoformat(),
        "epsg": crop.epsg,
        "x": crop.x,
        "y": crop.y,
    }
    arrays.update({f"power_{label}": block for label, block in crop.power.items()})
    np.savez_compressed(path, **arrays)


def _load(path: Path) -> Crop:
    with np.load(path) as data:
        return Crop(
            granule_id=str(data["granule_id"]),
            acquired=dt.datetime.fromisoformat(str(data["acquired"])),
            epsg=int(data["epsg"]),
            x=data["x"],
            y=data["y"],
            power={label: data[f"power_{label}"] for label in POLARISATIONS},
        )


def crop_granule(
    granule_id: str,
    bbox: BBox,
    cache_dir: Path,
    opener: Opener = open_remote_granule,
) -> Crop:
    """Crop one granule, reusing the local copy when this granule+bbox was fetched before.

    Cache: owner = this pipeline, files in cache_dir (data/raw/<site>/, gitignored). No TTL:
    granules are immutable. Invalidation: a different bbox is a different file; delete the
    folder to refetch.
    """
    path = _cache_path(cache_dir, granule_id, bbox)
    if path.is_file():
        log.info("cache hit %s", path.name)
        return _load(path)
    with opener(granule_id) as h5:
        crop = read_crop(h5, bbox)
    _save(path, crop)
    log.info("fetched %s %s", granule_id, {k: v.shape for k, v in crop.power.items()})
    return crop
