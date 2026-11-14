"""A tiny, fully known site shared by the API and pipeline tests.

10x10 pixels over a 1 km square at the equator, so each pixel is 100 m x 100 m
(0.01 km2). Water (HH -25 dB) fills the left WATER_COLUMNS[i] columns on date i;
land is -10 dB. HV is HH - 6 dB. Pixel (row 9, col 9) has no data on the last date.
"""

import datetime as dt
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.features.sites.schemas import Acquisition, PointOfInterest
from pipeline.writer import SiteMeta, write_site

TINY_SITE_ID = "tiny-site"
TINY_DATES = (dt.date(2026, 6, 20), dt.date(2026, 7, 2), dt.date(2026, 7, 14))
TINY_BOUNDS = (0.0, 0.0, 1000.0, 1000.0)
TINY_SIZE = 10
WATER_COLUMNS = (3, 5, 2)
WATER_DB = -25.0
LAND_DB = -10.0
HV_OFFSET_DB = -6.0
FRONTEND_ORIGIN = "http://localhost:5173"


def tiny_stack() -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    hh = np.full((len(TINY_DATES), TINY_SIZE, TINY_SIZE), LAND_DB, dtype=np.float32)
    for i, columns in enumerate(WATER_COLUMNS):
        hh[i, :, :columns] = WATER_DB
    hh[-1, 9, 9] = np.nan
    hv = (hh + HV_OFFSET_DB).astype(np.float32)
    return hh, hv


def build_tiny_site(data_dir: Path) -> Path:
    hh, hv = tiny_stack()
    meta = SiteMeta(
        id=TINY_SITE_ID,
        name="Tiny test site",
        change_type="water",
        source="demo",
        acquisitions=[
            Acquisition(date=d, granule_id=None, band="L", polarizations=["HH", "HV"])
            for d in TINY_DATES
        ],
        points_of_interest=[PointOfInterest(id="p1", name="Shore", lon=0.0005, lat=0.0045)],
        attribution="Synthetic test data",
    )
    return write_site(data_dir, meta, hh=hh, hv=hv, bounds_merc=TINY_BOUNDS)
