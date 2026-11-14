"""Interferogram (GUNW) crops: coherence at 20 m, corrected unwrapped phase at 80 m.

Needs the `pipeline` dependency group; skipped otherwise.
"""

import datetime as dt
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")
pytest.importorskip("rasterio")

from pipeline.remote_crop import crop_pair, read_pair_crop  # noqa: E402

ROOT = "science/LSAR/GUNW/grids/frequencyA"
GRANULE = "NISAR_L2_PR_GUNW_TEST_001"
EPSG = 32635  # lon 27 / lat 0 is x=500000, y=0
BBOX = (26.995, -0.005, 27.005, 0.005)  # ~1.1 km square around x=500000, y=0
CENTER_FREQUENCY = 1.2575e9


def _make_pair(path: Path) -> Path:
    with h5py.File(path, "w") as h:
        h[f"{ROOT}/centerFrequency"] = CENTER_FREQUENCY
        wrapped = h.create_group(f"{ROOT}/wrappedInterferogram/HH")
        wrapped["xCoordinates"] = 498000.0 + 20.0 * np.arange(200)
        wrapped["yCoordinates"] = 2000.0 - 20.0 * np.arange(200)
        wrapped["projection"] = np.uint32(EPSG)
        coherence = np.full((200, 200), 0.8, dtype="f4")
        coherence[100, 100] = 0.0  # fill value
        wrapped["coherenceMagnitude"] = coherence

        unwrapped = h.create_group(f"{ROOT}/unwrappedInterferogram/HH")
        unwrapped["xCoordinates"] = 498000.0 + 80.0 * np.arange(50)
        unwrapped["yCoordinates"] = 2000.0 - 80.0 * np.arange(50)
        unwrapped["projection"] = np.uint32(EPSG)
        unwrapped["unwrappedPhase"] = np.full((50, 50), 3.0, dtype="f4")
        unwrapped["ionospherePhaseScreen"] = np.full((50, 50), 1.0, dtype="f4")
        components = np.ones((50, 50), dtype="u2")
        components[25, 25] = 0  # unreliable unwrapping
        components[24, 24] = 2  # a small separate component: its 2π offset is unknown
        unwrapped["connectedComponents"] = components

        ident = h.create_group("science/LSAR/identification")
        ident["granuleId"] = np.bytes_(GRANULE)
        ident["referenceZeroDopplerStartTime"] = np.bytes_("2026-09-29T00:15:58.000000000")
        ident["secondaryZeroDopplerStartTime"] = np.bytes_("2026-10-11T00:15:58.000000000")
    return path


def _crop(tmp_path: Path):
    with h5py.File(_make_pair(tmp_path / "pair.h5"), "r") as h5:
        return read_pair_crop(h5, BBOX)


def test_pair_crop_keeps_both_dates_and_wavelength(tmp_path: Path) -> None:
    crop = _crop(tmp_path)

    assert crop.granule_id == GRANULE
    assert crop.reference == dt.datetime(2026, 9, 29, 0, 15, 58, tzinfo=dt.UTC)
    assert crop.secondary == dt.datetime(2026, 10, 11, 0, 15, 58, tzinfo=dt.UTC)
    assert crop.wavelength_m == pytest.approx(299792458.0 / CENTER_FREQUENCY)
    assert crop.epsg == EPSG


def test_coherence_is_read_at_20_m_and_phase_at_80_m(tmp_path: Path) -> None:
    crop = _crop(tmp_path)

    assert float(crop.coherence.x[1] - crop.coherence.x[0]) == 20.0
    assert float(crop.phase.x[1] - crop.phase.x[0]) == 80.0
    assert crop.coherence.values.shape[0] > crop.phase.values.shape[0]


def test_phase_has_the_ionosphere_removed(tmp_path: Path) -> None:
    crop = _crop(tmp_path)

    assert np.nanmedian(crop.phase.values) == pytest.approx(2.0)


def test_unreliable_and_minority_components_become_nan(tmp_path: Path) -> None:
    crop = _crop(tmp_path)
    x, y = crop.phase.x, crop.phase.y

    def at(easting: float, northing: float) -> float:
        return float(crop.phase.values[np.abs(y - northing).argmin(), np.abs(x - easting).argmin()])

    assert np.isnan(at(498000.0 + 80 * 25, 2000.0 - 80 * 25))  # component 0
    assert np.isnan(at(498000.0 + 80 * 24, 2000.0 - 80 * 24))  # minority component
    assert at(498000.0 + 80 * 26, 2000.0 - 80 * 26) == pytest.approx(2.0)


def test_zero_coherence_is_no_data(tmp_path: Path) -> None:
    crop = _crop(tmp_path)

    assert np.isnan(crop.coherence.values).sum() == 1


def test_pair_crop_is_cached(tmp_path: Path) -> None:
    path = _make_pair(tmp_path / "pair.h5")
    opened: list[str] = []

    @contextmanager
    def opener(granule_id: str):
        opened.append(granule_id)
        with h5py.File(path, "r") as h5:
            yield h5

    first = crop_pair(GRANULE, BBOX, tmp_path / "cache", opener=opener)
    second = crop_pair(GRANULE, BBOX, tmp_path / "cache", opener=opener)

    assert opened == [GRANULE]
    assert second.reference == first.reference
    assert np.array_equal(second.phase.values, first.phase.values, equal_nan=True)
