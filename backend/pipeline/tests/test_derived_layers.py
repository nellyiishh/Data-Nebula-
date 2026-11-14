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


# ---- Interferogram pairs ------------------------------------------------------------


def _pair_layers():
    from pipeline.interferometry import PairLayers

    coherence = np.full((2, 10, 10), 0.9)
    coherence[1, :, :3] = 0.1  # the second pair decorrelated over columns 0-2
    los = np.stack([np.full((10, 10), 1.0), np.full((10, 10), 0.5)])
    los[1, :, :3] = np.nan  # motion is blank where coherence is low
    pairs = [(TINY_DATES[0], TINY_DATES[1]), (TINY_DATES[1], TINY_DATES[2])]
    return PairLayers(pairs=pairs, coherence=coherence, los_cm=los)


def _build_with_pairs(tmp_path: Path) -> Path:
    from app.features.sites.schemas import Acquisition, PointOfInterest
    from app.features.sites.slope_echo import SlopeEcho
    from pipeline.writer import SiteMeta, write_site
    from testsupport import TINY_SLIDE_ID, tiny_stack

    hh, hv = tiny_stack()
    meta = SiteMeta(
        id=TINY_SLIDE_ID,
        name="Tiny landslide",
        change_type="landslide",
        source="demo",
        acquisitions=[
            Acquisition(date=d, granule_id=None, band="L", polarizations=["HH"]) for d in TINY_DATES
        ],
        points_of_interest=[PointOfInterest(id="p1", name="Scar", lon=0.0005, lat=0.0045)],
        attribution="test",
        slope_echo=SlopeEcho.model_validate(tiny_slope_echo()),
        ext_dir=write_tiny_ext(tmp_path / "ext"),
    )
    return write_site(
        tmp_path / "d", meta, hh=hh, hv=hv, bounds_merc=TINY_BOUNDS, pairs=_pair_layers()
    )


def test_pairs_become_coherence_and_displacement_layers(tmp_path: Path) -> None:
    site_dir = _build_with_pairs(tmp_path)

    layers = {layer["id"]: layer for layer in _site_json(site_dir)["layers"]}
    assert set(layers) == {"coherence", "displacement"}
    frames = layers["displacement"]["frames"]
    assert [(f["from"], f["to"]) for f in frames] == [
        (TINY_DATES[0].isoformat(), TINY_DATES[1].isoformat()),
        (TINY_DATES[1].isoformat(), TINY_DATES[2].isoformat()),
    ]
    for layer in layers.values():
        assert layer["legend"] is not None
        for frame in layer["frames"]:
            assert (site_dir / frame["file"]).is_file()
    assert layers["displacement"]["unit"] == "cm"


def test_displacement_is_blank_where_coherence_is_low(tmp_path: Path) -> None:
    site_dir = _build_with_pairs(tmp_path)

    layers = {layer["id"]: layer for layer in _site_json(site_dir)["layers"]}
    image = Image.open(site_dir / layers["displacement"]["frames"][1]["file"]).convert("RGBA")
    blank, moved = image.getpixel((0, 0)), image.getpixel((5, 0))
    assert isinstance(blank, tuple) and isinstance(moved, tuple)
    assert blank[3] == 0 and moved[3] > 0
    assert moved[2] > moved[0]  # blue = toward the satellite


def test_points_get_coherence_and_cumulative_motion(tmp_path: Path) -> None:
    site_dir = _build_with_pairs(tmp_path)

    block = _site_json(site_dir)
    series = json.loads((site_dir / block["point_extras"]["p1"]).read_text())["series"]
    assert series[0] == {
        "from": TINY_DATES[0].isoformat(),
        "to": TINY_DATES[1].isoformat(),
        "coherence": 0.9,
        "los_cm": 1.0,
    }
    # The point decorrelated in the second pair: no motion value, and the running total
    # stops rather than pretending nothing moved.
    assert series[1]["coherence"] == 0.1 and series[1]["los_cm"] is None
