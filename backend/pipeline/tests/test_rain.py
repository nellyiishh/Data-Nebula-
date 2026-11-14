"""IMERG daily rain at one cell: index maths, reading one value, caching, the file."""

import datetime as dt
import io
import json
from pathlib import Path

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from pipeline.rain import (  # noqa: E402
    RainCellError,
    daily_rain,
    imerg_index,
    rain_window,
    read_cell_mm,
)


def _nc4(
    value: float, units: str = "mm/day", fill: float = -9999.9, fill_as_list: bool = False
) -> bytes:
    buffer = io.BytesIO()
    with h5py.File(buffer, "w") as h:
        precipitation = h.create_dataset("precipitation", data=np.array([[[value]]], dtype="f4"))
        precipitation.attrs["units"] = np.bytes_(units)
        # Real OPeNDAP subsets store the fill value as a one-item array.
        fill_attr = np.array([fill], dtype="f4") if fill_as_list else np.float32(fill)
        precipitation.attrs["_FillValue"] = fill_attr
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content, self.status_code = content, status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, by_day: dict[str, bytes]) -> None:
        self.by_day, self.asked = by_day, []

    def get(self, url: str, *, params: dict[str, str], timeout: float) -> FakeResponse:
        self.asked.append((url, params))
        day = next(day for day in self.by_day if day in url)
        return FakeResponse(self.by_day[day])


def test_cell_index_picks_the_0_1_degree_cell_containing_the_point() -> None:
    # Grid centres start at -179.95 / -89.95, 0.1° apart.
    assert imerg_index(73.6266, 40.4721) == (2536, 1304)  # centre 73.65 E, 40.45 N
    assert imerg_index(-179.99, -89.99) == (0, 0)
    assert imerg_index(179.99, 89.99) == (3599, 1799)


def test_reads_one_value_and_treats_fill_as_missing() -> None:
    assert read_cell_mm(_nc4(12.5)) == pytest.approx(12.5)
    assert read_cell_mm(_nc4(-9999.9)) is None


def test_fill_value_stored_as_a_one_item_list_is_handled() -> None:
    assert read_cell_mm(_nc4(7.25, fill_as_list=True)) == pytest.approx(7.25)
    assert read_cell_mm(_nc4(-9999.9, fill_as_list=True)) is None


def test_refuses_unexpected_units() -> None:
    with pytest.raises(RainCellError, match="units"):
        read_cell_mm(_nc4(1.0, units="mm/hr"))


def test_window_starts_30_days_before_the_first_pass() -> None:
    dates = [dt.date(2026, 8, 12), dt.date(2026, 10, 11)]

    assert rain_window(dates) == (dt.date(2026, 7, 13), dt.date(2026, 10, 11))


def test_daily_rain_asks_for_one_cell_per_day_and_caches(tmp_path: Path) -> None:
    days = {"20261009": _nc4(3.0), "20261010": _nc4(41.2)}
    session = FakeSession(days)
    granules = [
        (dt.date(2026, 10, 9), "https://opendap.example/granule-20261009.nc4"),
        (dt.date(2026, 10, 10), "https://opendap.example/granule-20261010.nc4"),
    ]
    cache = tmp_path / "imerg.json"

    series = daily_rain(73.6266, 40.4721, granules, session, cache)
    again = daily_rain(73.6266, 40.4721, granules, FakeSession({}), cache)

    assert series == [{"date": "2026-10-09", "mm": 3.0}, {"date": "2026-10-10", "mm": 41.2}]
    assert again == series  # second run reads only the cache
    url, params = session.asked[0]
    assert url.endswith(".dap.nc4")
    assert params == {"dap4.ce": "/precipitation[0][2536][1304]"}
    assert json.loads(cache.read_text())["2026-10-10"] == 41.2
