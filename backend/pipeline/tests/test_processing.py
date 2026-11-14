"""processing: dB conversion, NaN-aware despeckle, shared Mercator grid, reprojection.

Needs the `pipeline` dependency group; skipped otherwise.
"""

import datetime as dt

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("scipy")

from app.core.geo import lonlat_to_mercator  # noqa: E402
from pipeline.processing import (  # noqa: E402
    despeckle,
    mercator_grid,
    to_db,
    to_mercator_grid,
)
from pipeline.remote_crop import Crop  # noqa: E402

EPSG = 32635  # central meridian 27°E: lon 27 / lat 0 is x=500000, y=0


def _crop(value_left: float, value_right: float) -> Crop:
    """200x200 grid at 20 m around x=500000, y=0; left half one value, right half another."""
    x = 498000.0 + 20.0 * np.arange(200)
    y = 2000.0 - 20.0 * np.arange(200)
    power = np.full((200, 200), value_left, dtype="f4")
    power[:, 100:] = value_right
    return Crop(
        granule_id="G",
        acquired=dt.datetime(2026, 10, 21, tzinfo=dt.UTC),
        epsg=EPSG,
        x=x,
        y=y,
        power={"HH": power, "HV": power * 0.1},
    )


def test_to_db_converts_power_and_keeps_nan() -> None:
    out = to_db(np.array([100.0, 1.0, np.nan], dtype="f4"))

    assert out[0] == pytest.approx(20.0)
    assert out[1] == pytest.approx(0.0)
    assert np.isnan(out[2])


def test_despeckle_keeps_nan_and_does_not_bleed_it_into_neighbours() -> None:
    power = np.full((20, 20), 2.0, dtype="f4")
    power[10, 10] = np.nan

    out = despeckle(power, size=3)

    assert np.isnan(out[10, 10])
    assert out[10, 11] == pytest.approx(2.0)  # a NaN neighbour must not pull the mean down
    assert np.isfinite(np.delete(out.ravel(), 10 * 20 + 10)).all()


def test_despeckle_reduces_speckle_variance() -> None:
    rng = np.random.default_rng(0)
    noisy = rng.gamma(1.0, 1.0, size=(100, 100)).astype("f4")  # single-look speckle

    assert despeckle(noisy, size=5).std() < 0.5 * noisy.std()


def test_mercator_grid_is_capped_and_keeps_aspect() -> None:
    bounds, (rows, cols) = mercator_grid((26.0, 0.0, 28.0, 1.0), native_res_m=20.0, max_side=500)

    assert max(rows, cols) == 500
    xmin, ymin, xmax, ymax = bounds
    assert cols / rows == pytest.approx((xmax - xmin) / (ymax - ymin), rel=0.02)


def test_mercator_grid_uses_native_pixels_when_small() -> None:
    # ~1.1 km square at the equator, 20 m pixels -> ~56 px a side, under the cap.
    _, (rows, cols) = mercator_grid((26.995, -0.005, 27.005, 0.005), 20.0, max_side=1000)

    assert 50 <= rows <= 60 and 50 <= cols <= 60


def test_reprojection_puts_values_at_the_right_place_and_nan_outside() -> None:
    crop = _crop(value_left=1.0, value_right=3.0)  # split at x=500000 (lon 27)
    # Destination: lon 26.99..27.03 → right 3/4 of it is the crop's right half; the crop spans
    # only x 498000..501980 (lon 26.982..27.018) so the far-right edge lies outside the crop.
    west, east = 26.99, 27.03
    xmin, _ = lonlat_to_mercator(west, 0.0)
    xmax, _ = lonlat_to_mercator(east, 0.0)
    bounds = (xmin, -500.0, xmax, 500.0)
    shape = (40, 160)

    out = to_mercator_grid(crop, "HH", bounds, shape)

    assert out.shape == shape
    mid_row = 20
    assert out[mid_row, 5] == pytest.approx(1.0)  # lon ~26.9915: left half
    col_at_27 = int(round((lonlat_to_mercator(27.0, 0.0)[0] - xmin) / (xmax - xmin) * 160))
    assert out[mid_row, col_at_27 + 8] == pytest.approx(3.0)  # just east of lon 27
    assert np.isnan(out[mid_row, 158])  # lon ~27.03: beyond the crop


def test_reprojection_keeps_north_at_row_zero() -> None:
    crop = _crop(value_left=1.0, value_right=1.0)
    crop.power["HH"][:100, :] = 5.0  # y > 0 (north) half
    bounds = (
        lonlat_to_mercator(26.99, 0.0)[0],
        -500.0,
        lonlat_to_mercator(27.01, 0.0)[0],
        500.0,
    )

    out = to_mercator_grid(crop, "HH", bounds, (40, 40))

    assert out[2, 20] == pytest.approx(5.0)  # top row = north
    assert out[37, 20] == pytest.approx(1.0)  # bottom row = south
