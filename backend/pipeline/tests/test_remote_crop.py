"""remote_crop: window maths, crop reading, caching, credential check.

Needs the `pipeline` dependency group (`uv run --group pipeline pytest`); skipped otherwise.
"""

import datetime as dt
import os
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")
pytest.importorskip("rasterio")

from pipeline.remote_crop import (  # noqa: E402
    OPEN_KWARGS,
    CropOutsideFootprintError,
    EmptyCropError,
    MissingCredentialsError,
    Window,
    bbox_to_window,
    crop_granule,
    dataset,
    read_crop,
    require_earthdata_env,
)

GROUP = "science/LSAR/GCOV/grids/frequencyA"
GRANULE = "NISAR_L2_PR_GCOV_TEST_001"
# UTM zone 35N: central meridian 27°E, so lon 27 / lat 0 is x=500000, y=0.
EPSG = 32635


def _make_granule(path: Path, *, nan_block: bool = False) -> Path:
    """A 200x200 grid at 20 m: x = 499000.. (ascending), y = 2000.. (descending)."""
    rows = cols = 200
    r, c = np.indices((rows, cols))
    data = (r * 1000 + c + 1).astype("f4")
    data[0, 0] = 0.0  # zero is NISAR's "no data" in power
    if nan_block:
        data[:] = np.nan
    with h5py.File(path, "w") as h:
        g = h.create_group(GROUP)
        g["HHHH"] = data
        g["HVHV"] = data * 0.1
        g["xCoordinates"] = 499000.0 + 20.0 * np.arange(cols)
        g["yCoordinates"] = 2000.0 - 20.0 * np.arange(rows)
        g["projection"] = np.uint32(EPSG)
        ident = h.create_group("science/LSAR/identification")
        ident["zeroDopplerStartTime"] = np.bytes_("2026-10-21T17:07:21.000000000")
        ident["granuleId"] = np.bytes_(GRANULE)
    return path


def test_window_selects_pixel_centres_inside_bounds() -> None:
    x = 20.0 * np.arange(10)  # 0..180
    y = 180.0 - 20.0 * np.arange(10)  # 180..0

    window = bbox_to_window(x, y, (30.0, 50.0, 110.0, 130.0))

    assert window == Window(r0=3, r1=7, c0=2, c1=6)


def test_window_includes_pixel_centres_exactly_on_the_bounds() -> None:
    x = 20.0 * np.arange(10)
    y = 180.0 - 20.0 * np.arange(10)

    window = bbox_to_window(x, y, (40.0, 60.0, 100.0, 120.0))

    assert window == Window(r0=3, r1=7, c0=2, c1=6)


def test_window_outside_footprint_raises() -> None:
    x = 20.0 * np.arange(10)
    y = 180.0 - 20.0 * np.arange(10)

    with pytest.raises(CropOutsideFootprintError):
        bbox_to_window(x, y, (1000.0, 1000.0, 2000.0, 2000.0))


def test_read_crop_returns_only_the_bbox_slice(tmp_path: Path) -> None:
    path = _make_granule(tmp_path / "g.h5")
    bbox = (26.995, -0.005, 27.005, 0.005)  # ~1.1 km square around x=500000, y=0

    with h5py.File(path, "r") as h5:
        crop = read_crop(h5, bbox)

    assert crop.epsg == EPSG
    assert crop.granule_id == GRANULE
    assert crop.acquired == dt.datetime(2026, 10, 21, 17, 7, 21, tzinfo=dt.UTC)
    assert set(crop.power) == {"HH", "HV"}
    assert abs(crop.power["HH"].shape[0] - 56) <= 3
    assert crop.power["HH"].shape == crop.power["HV"].shape
    assert crop.x.min() <= 500000.0 <= crop.x.max()
    assert crop.y.min() <= 0.0 <= crop.y.max()
    # Pixel (row, col) of the crop must be the matching source pixel, not a shifted one.
    col = int(np.argmin(np.abs(crop.x - 500000.0)))
    row = int(np.argmin(np.abs(crop.y - 0.0)))
    src_col, src_row = round((crop.x[col] - 499000.0) / 20.0), round((2000.0 - crop.y[row]) / 20.0)
    assert crop.power["HH"][row, col] == pytest.approx(src_row * 1000 + src_col + 1)


def test_zero_power_becomes_nan(tmp_path: Path) -> None:
    path = _make_granule(tmp_path / "g.h5")
    # Bbox around the grid's top-left corner so pixel [0, 0] (value 0) is in the crop.
    bbox = (26.9905, 0.0175, 26.9935, 0.0185)

    with h5py.File(path, "r") as h5:
        crop = read_crop(h5, bbox)

    assert np.isnan(crop.power["HH"][0, 0])
    assert np.isfinite(crop.power["HH"][1:, 1:]).all()


def test_all_empty_crop_raises(tmp_path: Path) -> None:
    path = _make_granule(tmp_path / "g.h5", nan_block=True)

    with h5py.File(path, "r") as h5, pytest.raises(EmptyCropError):
        read_crop(h5, (26.995, -0.005, 27.005, 0.005))


def test_crop_granule_caches_and_does_not_reopen(tmp_path: Path) -> None:
    source = _make_granule(tmp_path / "g.h5")
    opened: list[str] = []

    @contextmanager
    def fake_opener(granule_id: str):
        opened.append(granule_id)
        with h5py.File(source, "r") as h5:
            yield h5

    bbox = (26.995, -0.005, 27.005, 0.005)
    cache = tmp_path / "cache"

    first = crop_granule(GRANULE, bbox, cache, opener=fake_opener)
    second = crop_granule(GRANULE, bbox, cache, opener=fake_opener)

    assert opened == [GRANULE]  # the second call came from the cache
    assert second.acquired == first.acquired
    assert second.epsg == first.epsg
    np.testing.assert_array_equal(second.power["HH"], first.power["HH"])
    np.testing.assert_array_equal(second.x, first.x)


def test_different_bbox_is_a_different_cache_entry(tmp_path: Path) -> None:
    source = _make_granule(tmp_path / "g.h5")
    opened: list[str] = []

    @contextmanager
    def fake_opener(granule_id: str):
        opened.append(granule_id)
        with h5py.File(source, "r") as h5:
            yield h5

    cache = tmp_path / "cache"
    crop_granule(GRANULE, (26.995, -0.005, 27.005, 0.005), cache, opener=fake_opener)
    crop_granule(GRANULE, (26.996, -0.004, 27.004, 0.004), cache, opener=fake_opener)

    assert len(opened) == 2


def test_credentials_accept_token_or_user_and_password() -> None:
    require_earthdata_env({"EARTHDATA_TOKEN": "t"})
    require_earthdata_env({"EARTHDATA_USERNAME": "u", "EARTHDATA_PASSWORD": "p"})


def test_missing_credentials_fail_without_leaking_values() -> None:
    with pytest.raises(MissingCredentialsError) as err:
        require_earthdata_env({"EARTHDATA_USERNAME": "someone", "EARTHDATA_PASSWORD": ""})

    assert "EARTHDATA_TOKEN" in str(err.value)
    assert "someone" not in str(err.value)


def test_remote_reads_use_large_blocks() -> None:
    # Default fsspec caching makes h5py issue thousands of tiny requests (~3 s each), which
    # hung a real run. Keep this guard.
    assert OPEN_KWARGS["cache_type"] == "blockcache"
    assert OPEN_KWARGS["block_size"] >= 4 * 1024 * 1024


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("EARTHDATA_TOKEN"), reason="needs EARTHDATA_TOKEN")
def test_live_granule_crop(tmp_path: Path) -> None:
    from pipeline.remote_crop import open_remote_granule

    granule = (
        "NISAR_L2_PR_GCOV_033_137_D_073_2005_DHDH_A_20261021T170721_20261021T170733"
        "_P05036_N_P_J_001"
    )
    with open_remote_granule(granule) as h5:
        # A small window on valid data (found by the earlier probe), not a lon/lat bbox.
        window = Window(r0=3072, r1=3072 + 256, c0=6656, c1=6656 + 256)
        block = dataset(h5, "/science/LSAR/GCOV/grids/frequencyA/HHHH")[
            window.r0 : window.r1, window.c0 : window.c1
        ]
    assert np.isfinite(block).mean() > 0.9
