"""Reads only a bbox crop of a NISAR GCOV granule, over the network or from a local file.

A GCOV granule is ~0.8-4.5 GB; a site needs a small window of two polarisations. HDF5 is
chunked, so h5py asks only for the chunks the window touches (measured: 80 MB fetched from
an 801 MB file, including the scan that found valid data).

Credentials come from the environment only (EARTHDATA_TOKEN, or EARTHDATA_USERNAME +
EARTHDATA_PASSWORD), never from code.
"""

import datetime as dt
import functools
import hashlib
from collections.abc import Callable, Iterator, Mapping, MutableMapping
from contextlib import AbstractContextManager, closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, cast

import h5py
import numpy as np
from dotenv import dotenv_values
from numpy.typing import NDArray
from rasterio.warp import transform_bounds

from app.core.logging import get_logger

log = get_logger("remote_crop")

GCOV_SHORT_NAME = "NISAR_L2_GCOV_V1"
GRID_GROUP = "/science/LSAR/GCOV/grids/frequencyA"
IDENTIFICATION_GROUP = "/science/LSAR/identification"
RADAR_GRID_GROUP = "/science/LSAR/GCOV/metadata/radarGrid"
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
class ViewGeometry:
    """How the radar looked at the crop centre, at several heights above the ellipsoid
    (NISAR stores it as a coarse 3D cube). LOS points from the ground to the sensor."""

    heights: Array  # metres above the WGS84 ellipsoid, ascending
    los_east: Array
    los_north: Array
    incidence_deg: Array

    def at_height(self, height_m: float) -> tuple[float, float, float]:
        """(LOS east, LOS north, incidence angle in degrees) interpolated to height_m."""
        return (
            float(np.interp(height_m, self.heights, self.los_east)),
            float(np.interp(height_m, self.heights, self.los_north)),
            float(np.interp(height_m, self.heights, self.incidence_deg)),
        )


@dataclass(frozen=True)
class Crop:
    granule_id: str
    acquired: dt.datetime  # UTC start of the acquisition
    epsg: int  # CRS of x / y (UTM)
    x: Array  # column centres, metres, ascending
    y: Array  # row centres, metres, descending
    power: dict[str, Array]  # polarisation → linear power; no-data is NaN
    geometry: ViewGeometry | None = None  # None for granules without radarGrid metadata


EARTHDATA_KEYS = ("EARTHDATA_TOKEN", "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD")


def load_earthdata_env(env_file: Path, environ: MutableMapping[str, str]) -> None:
    """Copy the Earthdata keys from backend/.env into environ, where earthaccess looks.
    Only those keys, and never over a value the shell already set."""
    if not env_file.is_file():
        return
    for key, value in dotenv_values(env_file).items():
        if key in EARTHDATA_KEYS and value and key not in environ:
            environ[key] = value


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

    centre = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
    return Crop(
        granule_id=_as_text(dataset(h5, f"{IDENTIFICATION_GROUP}/granuleId")[()]),
        acquired=_parse_utc(dataset(h5, f"{IDENTIFICATION_GROUP}/zeroDopplerStartTime")[()]),
        epsg=epsg,
        x=x[window.c0 : window.c1],
        y=y[window.r0 : window.r1],
        power=power,
        geometry=_read_geometry(h5, *centre),
    )


def _read_geometry(h5: h5py.File, x: float, y: float) -> ViewGeometry | None:
    """The geometry column nearest to (x, y), in the grid's CRS. Reads 3 x heights values."""
    if RADAR_GRID_GROUP not in h5:
        return None
    gx = np.asarray(dataset(h5, f"{RADAR_GRID_GROUP}/xCoordinates")[:])
    gy = np.asarray(dataset(h5, f"{RADAR_GRID_GROUP}/yCoordinates")[:])
    col, row = int(np.abs(gx - x).argmin()), int(np.abs(gy - y).argmin())

    def column(name: str) -> Array:
        return np.asarray(dataset(h5, f"{RADAR_GRID_GROUP}/{name}")[:, row, col], dtype="f8")

    return ViewGeometry(
        heights=np.asarray(dataset(h5, f"{RADAR_GRID_GROUP}/heightAboveEllipsoid")[:], "f8"),
        los_east=column("losUnitVectorX"),
        los_north=column("losUnitVectorY"),
        incidence_deg=column("incidenceAngle"),
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
    if crop.geometry is not None:
        arrays.update({f"geometry_{k}": v for k, v in vars(crop.geometry).items()})
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
            # Crops cached before geometry was read have no geometry_* arrays.
            geometry=ViewGeometry(
                **{f: data[f"geometry_{f}"] for f in ViewGeometry.__dataclass_fields__}
            )
            if "geometry_heights" in data
            else None,
        )


def crop_granule(
    granule_id: str,
    bbox: BBox,
    cache_dir: Path,
    opener: Opener | None = None,
    collection: str = GCOV_SHORT_NAME,
) -> Crop:
    """Crop one granule, reusing the local copy when this granule+bbox was fetched before.

    Cache: owner = this pipeline, files in cache_dir (data/raw/<site>/, gitignored). No TTL:
    granules are immutable. Invalidation: a different bbox is a different file; delete the
    folder to refetch. `collection` is the CMR short name: provisional and validated
    granules live in different collections.
    """
    path = _cache_path(cache_dir, granule_id, bbox)
    if path.is_file():
        log.info("cache hit %s", path.name)
        return _load(path)
    # Looked up at call time (not bound as a default) so tests can replace it.
    open_granule = opener or functools.partial(open_remote_granule, short_name=collection)
    with open_granule(granule_id) as h5:
        crop = read_crop(h5, bbox)
    _save(path, crop)
    log.info("fetched %s %s", granule_id, {k: v.shape for k, v in crop.power.items()})
    return crop


# ---- Interferogram pairs (GUNW) ------------------------------------------------------

GUNW_SHORT_NAME = "NISAR_L2_GUNW_V1"
GUNW_GRIDS = "/science/LSAR/GUNW/grids/frequencyA"
WRAPPED_GROUP = f"{GUNW_GRIDS}/wrappedInterferogram/HH"  # 20 m: coherence
UNWRAPPED_GROUP = f"{GUNW_GRIDS}/unwrappedInterferogram/HH"  # 80 m: phase
SPEED_OF_LIGHT = 299792458.0


@dataclass(frozen=True)
class Raster:
    x: Array  # column centres, metres, ascending
    y: Array  # row centres, metres, descending
    values: Array  # NaN = no data


@dataclass(frozen=True)
class PairCrop:
    """One 12-day interferogram cropped to a bbox, both grids in one UTM CRS."""

    granule_id: str
    reference: dt.datetime  # UTC start of the earlier pass
    secondary: dt.datetime  # UTC start of the later pass
    epsg: int
    wavelength_m: float
    coherence: Raster  # 0..1, 20 m
    # Unwrapped phase minus the ionosphere screen (radians), 80 m. NaN where unwrapping is
    # unreliable or outside the crop's main connected component.
    phase: Raster


def _window_block(h5: h5py.File, group: str, name: str, bbox: BBox) -> tuple[int, Raster]:
    epsg = int(dataset(h5, f"{group}/projection")[()])
    x = np.asarray(dataset(h5, f"{group}/xCoordinates")[:])
    y = np.asarray(dataset(h5, f"{group}/yCoordinates")[:])
    window = bbox_to_window(
        x, y, transform_bounds("EPSG:4326", f"EPSG:{epsg}", *bbox, densify_pts=21)
    )
    block = np.asarray(
        dataset(h5, f"{group}/{name}")[window.r0 : window.r1, window.c0 : window.c1], dtype="f4"
    )
    raster = Raster(x=x[window.c0 : window.c1], y=y[window.r0 : window.r1], values=block)
    return epsg, raster


def _main_component(components: NDArray[np.integer]) -> NDArray[np.bool_]:
    """Pixels of the most common reliable connected component. Each component has its own
    unknown multiple of 2π, so only one of them can be referenced consistently."""
    labels, counts = np.unique(components[components > 0], return_counts=True)
    if labels.size == 0:
        return np.zeros(components.shape, dtype=bool)
    return components == labels[counts.argmax()]


def read_pair_crop(h5: h5py.File, bbox: BBox) -> PairCrop:
    """Crop a GUNW granule to a lon/lat bbox. Only the window's chunks are read."""
    epsg, coherence = _window_block(h5, WRAPPED_GROUP, "coherenceMagnitude", bbox)
    phase_epsg, unwrapped = _window_block(h5, UNWRAPPED_GROUP, "unwrappedPhase", bbox)
    if phase_epsg != epsg:
        raise ValueError(f"coherence (EPSG:{epsg}) and phase (EPSG:{phase_epsg}) grids differ")
    _, ionosphere = _window_block(h5, UNWRAPPED_GROUP, "ionospherePhaseScreen", bbox)
    _, components = _window_block(h5, UNWRAPPED_GROUP, "connectedComponents", bbox)

    coherence.values[(coherence.values <= 0) | ~np.isfinite(coherence.values)] = np.nan
    # MintPy treats the ionosphere screen as a correction subtracted from the phase.
    phase = unwrapped.values - ionosphere.values
    phase[~_main_component(components.values.astype("u4"))] = np.nan

    frequency = float(dataset(h5, f"{GUNW_GRIDS}/centerFrequency")[()])
    return PairCrop(
        granule_id=_as_text(dataset(h5, f"{IDENTIFICATION_GROUP}/granuleId")[()]),
        reference=_parse_utc(
            dataset(h5, f"{IDENTIFICATION_GROUP}/referenceZeroDopplerStartTime")[()]
        ),
        secondary=_parse_utc(
            dataset(h5, f"{IDENTIFICATION_GROUP}/secondaryZeroDopplerStartTime")[()]
        ),
        epsg=epsg,
        wavelength_m=SPEED_OF_LIGHT / frequency,
        coherence=coherence,
        phase=Raster(x=unwrapped.x, y=unwrapped.y, values=phase.astype("f4")),
    )


def _save_pair(path: Path, crop: PairCrop) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, Any] = {
        "granule_id": crop.granule_id,
        "reference": crop.reference.isoformat(),
        "secondary": crop.secondary.isoformat(),
        "epsg": crop.epsg,
        "wavelength_m": crop.wavelength_m,
    }
    for name in ("coherence", "phase"):
        raster: Raster = getattr(crop, name)
        arrays.update(
            {f"{name}_x": raster.x, f"{name}_y": raster.y, f"{name}_values": raster.values}
        )
    np.savez_compressed(path, **arrays)


def _load_pair(path: Path) -> PairCrop:
    with np.load(path) as data:
        rasters = {
            name: Raster(x=data[f"{name}_x"], y=data[f"{name}_y"], values=data[f"{name}_values"])
            for name in ("coherence", "phase")
        }
        return PairCrop(
            granule_id=str(data["granule_id"]),
            reference=dt.datetime.fromisoformat(str(data["reference"])),
            secondary=dt.datetime.fromisoformat(str(data["secondary"])),
            epsg=int(data["epsg"]),
            wavelength_m=float(data["wavelength_m"]),
            **rasters,
        )


def crop_pair(
    granule_id: str,
    bbox: BBox,
    cache_dir: Path,
    opener: Opener | None = None,
    collection: str = GUNW_SHORT_NAME,
) -> PairCrop:
    """Like crop_granule, for interferograms. Same cache rules (data/raw/<site>/, no TTL)."""
    path = _cache_path(cache_dir, granule_id, bbox)
    if path.is_file():
        log.info("cache hit %s", path.name)
        return _load_pair(path)
    open_granule = opener or functools.partial(open_remote_granule, short_name=collection)
    with open_granule(granule_id) as h5:
        crop = read_pair_crop(h5, bbox)
    _save_pair(path, crop)
    log.info(
        "fetched %s coherence %s phase %s",
        granule_id,
        crop.coherence.values.shape,
        crop.phase.values.shape,
    )
    return crop
