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
from app.features.sites.slope_echo import SlopeEcho
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


# ---- A tiny landslide site with a full Slope Echo block ---------------------------------

TINY_SLIDE_ID = "tiny-slide"
# Every file the block below references under ext/, with its content.
TINY_EXT_FILES = {
    "coherence/2026-06-20_2026-07-02.png": b"\x89PNG fake",
    "scar.geojson": b'{"type": "FeatureCollection", "features": []}',
    "rain.json": b'{"series": [{"date": "2026-06-20", "mm": 4.2}]}',
    "raw/2026-06-20_linear.png": b"\x89PNG fake",
    "points/p1.json": b'{"series": []}',
}


def tiny_slope_echo() -> dict:
    source = {"name": "Test source"}
    return {
        "region": "Test region",
        "country": "Kyrgyzstan",
        "event": {"date": "2026-07-01", "label": "Test slide", "source": source},
        "facts": [{"text": "One fact", "source": source}],
        "story": {
            key: {"explore": f"{key} plain", "research": f"{key} detail"}
            for key in ("place", "rain", "radar", "tracking", "exposure")
        },
        "layers": [
            {
                "id": "coherence",
                "kind": "coherence",
                "title": "Coherence",
                "unit": "0–1",
                "description": "How alike two passes are.",
                "source": source,
                "frames": [
                    {
                        "from": "2026-06-20",
                        "to": "2026-07-02",
                        "file": "ext/coherence/2026-06-20_2026-07-02.png",
                    }
                ],
                "legend": {"colors": ["#000000", "#ffffff"], "labels": ["changed", "stable"]},
            }
        ],
        "overlays": [
            {
                "id": "scar",
                "kind": "polygon",
                "title": "Scar",
                "file": "ext/scar.geojson",
                "description": "Mapped scar.",
                "source": source,
            }
        ],
        "rain": {"file": "ext/rain.json", "source": source, "note": "Regional rain."},
        "raw_example": {
            "linear": "ext/raw/2026-06-20_linear.png",
            "db": "layers/hh/2026-06-20.png",
            "date": "2026-06-20",
        },
        "point_extras": {"p1": "ext/points/p1.json"},
        "exposure": None,
        "validation": None,
        "limitations": ["Test limit"],
    }


def write_tiny_ext(ext_dir: Path) -> Path:
    for relative, content in TINY_EXT_FILES.items():
        path = ext_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return ext_dir


def build_tiny_landslide(data_dir: Path, ext_dir: Path, slope_echo: dict | None = None) -> Path:
    hh, hv = tiny_stack()
    meta = SiteMeta(
        id=TINY_SLIDE_ID,
        name="Tiny landslide",
        change_type="landslide",
        source="demo",
        acquisitions=[
            Acquisition(date=d, granule_id=None, band="L", polarizations=["HH", "HV"])
            for d in TINY_DATES
        ],
        points_of_interest=[PointOfInterest(id="p1", name="Scar", lon=0.0005, lat=0.0045)],
        attribution="Synthetic test data",
        slope_echo=SlopeEcho.model_validate(slope_echo or tiny_slope_echo()),
        ext_dir=ext_dir,
    )
    return write_site(data_dir, meta, hh=hh, hv=hv, bounds_merc=TINY_BOUNDS)
