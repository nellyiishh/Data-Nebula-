"""What write_site derives for a landslide story: validation, raw example, blind overlay."""

import json
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.geo import mercator_to_lonlat
from pipeline.derived import polygon_mask
from testsupport import (
    TINY_BOUNDS,
    TINY_DATES,
    build_tiny_landslide,
    tiny_slope_echo,
    write_tiny_ext,
)


def _square(c0: int, c1: int, r0: int, r1: int) -> dict:
    """GeoJSON polygon around tiny-site pixels [r0, r1) x [c0, c1) (100 m pixels)."""
    xmin, _, _, ymax = TINY_BOUNDS
    west, north = mercator_to_lonlat(xmin + c0 * 100, ymax - r0 * 100)
    east, south = mercator_to_lonlat(xmin + c1 * 100, ymax - r1 * 100)
    ring = [[west, north], [east, north], [east, south], [west, south], [west, north]]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
    }


def _block_with_outlines(ext_dir: Path, event: str = "2026-06-25") -> dict:
    """Scar over columns 3-4 (water arrives there between dates 0 and 1), stable area over
    columns 7-9 (land on every date). Event between the first two passes."""
    (ext_dir / "scar.geojson").write_text(json.dumps(_square(3, 5, 0, 10)))
    (ext_dir / "stable.geojson").write_text(json.dumps(_square(7, 10, 0, 10)))
    block = tiny_slope_echo()
    block["event"]["date"] = event
    block["raw_example"] = None
    source = {"name": "test"}
    block["overlays"] = [
        {
            "id": "scar",
            "kind": "polygon",
            "title": "Scar",
            "file": "ext/scar.geojson",
            "description": "d",
            "source": source,
        },
        {
            "id": "stable",
            "kind": "polygon",
            "title": "Stable",
            "file": "ext/stable.geojson",
            "description": "d",
            "source": source,
        },
    ]
    return block


def _site_json(site_dir: Path) -> dict:
    return json.loads((site_dir / "site.json").read_text())["slope_echo"]


def test_polygon_mask_covers_exactly_the_pixels_inside() -> None:
    mask = polygon_mask(_square(3, 5, 2, 6), TINY_BOUNDS, (10, 10))

    expected = np.zeros((10, 10), bool)
    expected[2:6, 3:5] = True
    assert (mask == expected).all()


def test_validation_compares_scar_with_stable_area(tmp_path: Path) -> None:
    ext_dir = write_tiny_ext(tmp_path / "ext")
    site_dir = build_tiny_landslide(tmp_path / "d", ext_dir, _block_with_outlines(ext_dir))

    validation = _site_json(site_dir)["validation"]
    assert validation["pair"] == [TINY_DATES[0].isoformat(), TINY_DATES[1].isoformat()]
    assert validation["threshold_db"] == 3.0
    assert validation["changed_inside_pct"] == 100.0
    assert validation["changed_outside_pct"] == 0.0
    assert "3×3" in validation["method"]


def test_no_validation_without_both_outlines(tmp_path: Path) -> None:
    ext_dir = write_tiny_ext(tmp_path / "ext")
    block = _block_with_outlines(ext_dir)
    block["overlays"] = block["overlays"][:1]  # scar only

    site_dir = build_tiny_landslide(tmp_path / "d", ext_dir, block)

    assert _site_json(site_dir)["validation"] is None


def test_no_validation_when_no_pass_follows_the_event(tmp_path: Path) -> None:
    ext_dir = write_tiny_ext(tmp_path / "ext")
    block = _block_with_outlines(ext_dir, event="2026-12-01")

    site_dir = build_tiny_landslide(tmp_path / "d", ext_dir, block)

    assert _site_json(site_dir)["validation"] is None


def test_raw_example_uses_the_last_pass_before_the_event(tmp_path: Path) -> None:
    ext_dir = write_tiny_ext(tmp_path / "ext")
    block = _block_with_outlines(ext_dir, event="2026-07-10")

    site_dir = build_tiny_landslide(tmp_path / "d", ext_dir, block)

    raw = _site_json(site_dir)["raw_example"]
    before = TINY_DATES[1].isoformat()
    assert raw == {
        "linear": f"ext/raw/{before}_linear.png",
        "db": f"layers/hh/{before}.png",
        "date": before,
    }
    assert (site_dir / raw["linear"]).is_file()


def test_a_given_raw_example_is_kept(tmp_path: Path) -> None:
    site_dir = build_tiny_landslide(tmp_path / "d", write_tiny_ext(tmp_path / "ext"))

    assert _site_json(site_dir)["raw_example"]["linear"] == "ext/raw/2026-06-20_linear.png"


def test_blind_mask_becomes_an_overlay_and_is_left_out_of_validation(tmp_path: Path) -> None:
    ext_dir = write_tiny_ext(tmp_path / "ext")
    blind = np.zeros((10, 10), bool)
    blind[:, 3] = True  # half of the scar is in radar shadow

    site_dir = build_tiny_landslide(
        tmp_path / "d", ext_dir, _block_with_outlines(ext_dir), blind_mask=blind
    )

    block = _site_json(site_dir)
    overlay = next(o for o in block["overlays"] if o["id"] == "radar_blind")
    assert overlay["kind"] == "image" and overlay["file"] == "ext/radar_blind.png"
    image = Image.open(site_dir / overlay["file"]).convert("RGBA")
    shadowed, visible = image.getpixel((3, 0)), image.getpixel((4, 0))
    assert isinstance(shadowed, tuple) and isinstance(visible, tuple)
    assert shadowed[3] > 0 and visible[3] == 0
    assert block["validation"]["changed_inside_pct"] == 100.0  # only column 4 counted
