import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.features.sites.schemas import Acquisition
from app.main import create_app
from pipeline.make_demo_site import DEMO_SITE_ID, build_demo_site
from pipeline.writer import SiteMeta, write_site
from testsupport import TINY_DATES, TINY_SITE_ID, build_tiny_site, tiny_stack

LAYERS = ("hh", "hv", "rgb", "water")


def _pixel(path: Path, x: int, y: int) -> tuple[int, ...]:
    image = Image.open(io.BytesIO(path.read_bytes())).convert("RGBA")
    pixel = image.getpixel((x, y))
    assert isinstance(pixel, tuple)
    return pixel


def test_writes_one_image_per_layer_and_date(tmp_path: Path) -> None:
    site_dir = build_tiny_site(tmp_path)

    for layer in LAYERS:
        for date in TINY_DATES:
            assert (site_dir / "layers" / layer / f"{date.isoformat()}.png").is_file()
    for name in ("site.json", "stats.json", "stack.npz"):
        assert (site_dir / name).is_file()


def test_missing_data_is_transparent(tmp_path: Path) -> None:
    site_dir = build_tiny_site(tmp_path)

    hh_last = site_dir / "layers" / "hh" / f"{TINY_DATES[-1].isoformat()}.png"
    assert _pixel(hh_last, 9, 9)[3] == 0
    assert _pixel(hh_last, 5, 5)[3] == 255


def test_water_layer_only_colours_water(tmp_path: Path) -> None:
    site_dir = build_tiny_site(tmp_path)

    water_first = site_dir / "layers" / "water" / f"{TINY_DATES[0].isoformat()}.png"
    assert _pixel(water_first, 0, 0)[3] > 0  # column 0 is water
    assert _pixel(water_first, 9, 0)[3] == 0  # column 9 is land


def test_rewriting_a_site_removes_stale_files(tmp_path: Path) -> None:
    site_dir = build_tiny_site(tmp_path)
    stale = site_dir / "layers" / "hh" / "2020-01-01.png"
    stale.write_bytes(b"old")

    build_tiny_site(tmp_path)

    assert not stale.exists()


def test_rejects_stack_that_does_not_match_dates(tmp_path: Path) -> None:
    hh, hv = tiny_stack()  # three dates of data...
    meta = SiteMeta(
        id=TINY_SITE_ID,
        name="Mismatch",
        change_type="water",
        source="demo",
        acquisitions=[  # ...but only one acquisition listed
            Acquisition(date=TINY_DATES[0], granule_id=None, band="L", polarizations=["HH"])
        ],
        attribution="test",
    )

    with pytest.raises(ValueError, match="dates"):
        write_site(tmp_path, meta, hh=hh, hv=hv, bounds_merc=(0.0, 0.0, 1.0, 1.0))


def test_demo_site_is_served_and_shows_shrinking_water(tmp_path: Path) -> None:
    build_demo_site(tmp_path, size=64)
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        site = client.get(f"/api/v1/sites/{DEMO_SITE_ID}").json()
        series = client.get(f"/api/v1/sites/{DEMO_SITE_ID}/stats").json()["series"]

    assert site["source"] == "demo"
    assert len(site["dates"]) == len(series) >= 6
    assert series[-1]["water_km2"] < series[0]["water_km2"]
