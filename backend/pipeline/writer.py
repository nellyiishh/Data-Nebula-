"""Writes one prepared site in the layout app/features/sites/repository.py reads.

Both the demo generator and the real NISAR pipeline end by calling write_site(), so the
API never needs to know where the numbers came from.
"""

import datetime as dt
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.core.geo import mercator_to_lonlat
from app.features.sites.models import MercatorBounds
from app.features.sites.rendering import (
    WATER_THRESHOLD_DB,
    encode_png,
    false_colour_rgba,
    grayscale_rgba,
    water_mask,
    water_rgba,
)
from app.features.sites.repository import LAYERS_DIR, SITE_FILE, STACK_FILE, STATS_FILE
from app.features.sites.schemas import (
    LAYER_NAMES,
    Acquisition,
    ChangeType,
    DataSource,
    PointOfInterest,
    SiteDetail,
    SiteStats,
    StatsEntry,
)

Cube = NDArray[np.floating]


@dataclass(frozen=True)
class SiteMeta:
    id: str
    name: str
    change_type: ChangeType
    source: DataSource
    acquisitions: list[Acquisition]
    attribution: str
    points_of_interest: list[PointOfInterest] = field(default_factory=list)


def write_site(
    data_dir: Path, meta: SiteMeta, *, hh: Cube, hv: Cube, bounds_merc: MercatorBounds
) -> Path:
    """hh/hv: (dates, rows, cols) in dB, NaN = no data, row 0 = north, on one shared
    EPSG:3857 grid covering bounds_merc. Replaces any earlier output for this site."""
    _validate(meta, hh, hv, bounds_merc)
    site_dir = data_dir / meta.id
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)

    detail = _site_detail(meta, bounds_merc)
    (site_dir / SITE_FILE).write_text(detail.model_dump_json(indent=2))
    stats = _site_stats(meta, hh, hv, bounds_merc)
    (site_dir / STATS_FILE).write_text(stats.model_dump_json(indent=2))
    _write_layers(site_dir, detail.dates, hh, hv)
    np.savez_compressed(
        site_dir / STACK_FILE,
        hh=hh.astype(np.float32),
        hv=hv.astype(np.float32),
        bounds_merc=np.asarray(bounds_merc, dtype=np.float64),
        dates=np.array([d.isoformat() for d in detail.dates]),
    )
    return site_dir


def _validate(meta: SiteMeta, hh: Cube, hv: Cube, bounds_merc: MercatorBounds) -> None:
    if hh.ndim != 3 or hh.shape != hv.shape:
        raise ValueError(f"hh {hh.shape} and hv {hv.shape} must share one (dates, rows, cols)")
    dates = [a.date for a in meta.acquisitions]
    if len(dates) != hh.shape[0]:
        raise ValueError(f"{len(dates)} acquisition dates but {hh.shape[0]} layers in the stack")
    if dates != sorted(set(dates)):
        raise ValueError("acquisition dates must be unique and in order")
    xmin, ymin, xmax, ymax = bounds_merc
    if not (xmin < xmax and ymin < ymax):
        raise ValueError(f"bounds must be (xmin, ymin, xmax, ymax): {bounds_merc}")


def _site_detail(meta: SiteMeta, bounds_merc: MercatorBounds) -> SiteDetail:
    xmin, ymin, xmax, ymax = bounds_merc
    return SiteDetail(
        id=meta.id,
        name=meta.name,
        center=mercator_to_lonlat((xmin + xmax) / 2, (ymin + ymax) / 2),
        change_type=meta.change_type,
        source=meta.source,
        corners=(
            mercator_to_lonlat(xmin, ymax),
            mercator_to_lonlat(xmax, ymax),
            mercator_to_lonlat(xmax, ymin),
            mercator_to_lonlat(xmin, ymin),
        ),
        layers=list(LAYER_NAMES),
        acquisitions=meta.acquisitions,
        points_of_interest=meta.points_of_interest,
        attribution=meta.attribution,
    )


def _pixel_area_km2_by_row(
    shape: tuple[int, ...], bounds_merc: MercatorBounds
) -> NDArray[np.float64]:
    """True ground area of one pixel in each row. Mercator stretches distances by
    1/cos(latitude), so each Mercator square metre covers cos²(lat) real square metres."""
    _, rows, cols = shape
    xmin, ymin, xmax, ymax = bounds_merc
    width, height = (xmax - xmin) / cols, (ymax - ymin) / rows
    lats = [mercator_to_lonlat(0.0, ymax - (r + 0.5) * height)[1] for r in range(rows)]
    return np.array([width * height * math.cos(math.radians(lat)) ** 2 / 1e6 for lat in lats])


def _mean_db(layer: NDArray[np.floating]) -> float | None:
    finite = layer[np.isfinite(layer)]
    if finite.size == 0:
        return None
    return round(float(10 * np.log10(np.mean(10 ** (finite / 10)))), 3)


def _site_stats(meta: SiteMeta, hh: Cube, hv: Cube, bounds_merc: MercatorBounds) -> SiteStats:
    row_area = _pixel_area_km2_by_row(hh.shape, bounds_merc)
    series = [
        StatsEntry(
            date=acquisition.date,
            water_km2=round(float((water_mask(hh[t]).sum(axis=1) * row_area).sum()), 4),
            mean_hh_db=_mean_db(hh[t]),
            mean_hv_db=_mean_db(hv[t]),
        )
        for t, acquisition in enumerate(meta.acquisitions)
    ]
    return SiteStats(site_id=meta.id, water_threshold_db=WATER_THRESHOLD_DB, series=series)


def _write_layers(site_dir: Path, dates: list[dt.date], hh: Cube, hv: Cube) -> None:
    for t, date in enumerate(dates):
        images = {
            "hh": grayscale_rgba(hh[t], "hh"),
            "hv": grayscale_rgba(hv[t], "hv"),
            "rgb": false_colour_rgba(hh[t], hv[t]),
            "water": water_rgba(hh[t]),
        }
        for layer, rgba in images.items():
            path = site_dir / LAYERS_DIR / layer / f"{date.isoformat()}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encode_png(rgba))
