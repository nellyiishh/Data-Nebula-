"""prepare_site: manifest entry → crops → one shared grid → write_site.

Needs the `pipeline` dependency group; skipped otherwise.
"""

import datetime as dt
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("scipy")

from app.features.sites.repository import SITE_FILE, STACK_FILE  # noqa: E402
from pipeline.prepare_nisar import ManifestSite, prepare_site  # noqa: E402
from pipeline.remote_crop import BBox, Crop  # noqa: E402

BBOX: BBox = (26.995, -0.005, 27.005, 0.005)
ACQUIRED = {
    "G_B": dt.datetime(2026, 10, 21, 17, 7, tzinfo=dt.UTC),
    "G_C": dt.datetime(2026, 11, 2, 17, 7, tzinfo=dt.UTC),
    "G_D": dt.datetime(2026, 11, 14, 17, 7, tzinfo=dt.UTC),
}
POWER = {"G_B": 0.1, "G_C": 0.2, "G_D": 0.4}  # -10, -7, -4 dB


def _fake_cropper(epsg: int = 32635):
    calls: list[str] = []

    def cropper(granule_id: str, bbox: BBox, cache_dir: Path) -> Crop:
        calls.append(granule_id)
        x = 498000.0 + 20.0 * np.arange(200)
        y = 2000.0 - 20.0 * np.arange(200)
        hh = np.full((200, 200), POWER[granule_id], dtype="f4")
        return Crop(granule_id, ACQUIRED[granule_id], epsg, x, y, {"HH": hh, "HV": hh * 0.1})

    return cropper, calls


def _site(granules: list[str]) -> ManifestSite:
    return ManifestSite(
        id="test-site", name="Test site", change_type="water", bbox=BBOX, granules=granules
    )


def test_prepare_site_writes_a_sorted_nisar_site(tmp_path: Path) -> None:
    cropper, calls = _fake_cropper()

    # Manifest lists the dates out of order; the site must still be chronological.
    site_dir = prepare_site(
        _site(["G_D", "G_B", "G_C"]), tmp_path / "derived", tmp_path / "raw", cropper=cropper
    )

    assert sorted(calls) == ["G_B", "G_C", "G_D"]
    detail = (site_dir / SITE_FILE).read_text()
    assert '"source": "nisar"' in detail
    stack = np.load(site_dir / STACK_FILE)
    assert stack["hh"].shape[0] == 3
    assert list(stack["dates"]) == ["2026-10-21", "2026-11-02", "2026-11-14"]
    means = np.nanmean(stack["hh"], axis=(1, 2))
    assert means == pytest.approx([-10.0, 10 * np.log10(0.2), 10 * np.log10(0.4)], abs=0.1)
    assert np.nanmean(stack["hv"][0]) == pytest.approx(-20.0, abs=0.1)


def test_prepare_site_records_granule_provenance(tmp_path: Path) -> None:
    cropper, _ = _fake_cropper()

    site_dir = prepare_site(
        _site(["G_B", "G_C"]), tmp_path / "derived", tmp_path / "raw", cropper=cropper
    )

    text = (site_dir / SITE_FILE).read_text()
    assert '"granule_id": "G_B"' in text and '"granule_id": "G_C"' in text
    assert '"band": "L"' in text and '"HH"' in text and '"HV"' in text


def test_prepare_site_rejects_mixed_projections(tmp_path: Path) -> None:
    ok, _ = _fake_cropper(epsg=32635)
    other, _ = _fake_cropper(epsg=32636)

    def mixed(granule_id: str, bbox: BBox, cache_dir: Path) -> Crop:
        return (ok if granule_id == "G_B" else other)(granule_id, bbox, cache_dir)

    with pytest.raises(ValueError, match="same track and frame"):
        prepare_site(_site(["G_B", "G_C"]), tmp_path / "d", tmp_path / "r", cropper=mixed)


def test_prepare_site_needs_at_least_two_dates(tmp_path: Path) -> None:
    cropper, _ = _fake_cropper()

    with pytest.raises(ValueError, match="at least two"):
        prepare_site(_site(["G_B"]), tmp_path / "d", tmp_path / "r", cropper=cropper)
