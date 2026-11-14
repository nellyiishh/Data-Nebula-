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


def _landslide_site(granules: list[str]) -> ManifestSite:
    from app.features.sites.slope_echo import SlopeEcho
    from testsupport import tiny_slope_echo

    block = tiny_slope_echo()
    block.update(layers=[], overlays=[], rain=None, raw_example=None, point_extras={})
    return ManifestSite(
        id="slide-site",
        name="Slide",
        change_type="landslide",
        bbox=BBOX,
        granules=granules,
        slope_echo=SlopeEcho.model_validate(block),
    )


def _with_geometry(cropper):
    from pipeline.remote_crop import ViewGeometry

    looks_from_east = ViewGeometry(
        heights=np.array([0.0, 4000.0]),
        los_east=np.array([0.8, 0.8]),
        los_north=np.array([0.0, 0.0]),
        incidence_deg=np.array([35.0, 35.0]),
    )

    def wrapped(granule_id: str, bbox: BBox, cache_dir: Path) -> Crop:
        crop = cropper(granule_id, bbox, cache_dir)
        return Crop(**{**vars(crop), "geometry": looks_from_east})

    return wrapped


def test_landslide_site_gets_a_radar_blind_overlay(tmp_path: Path) -> None:
    import json

    cropper, _ = _fake_cropper()
    asked: list[tuple[int, int]] = []

    def steep_east_slope(bounds, shape):
        asked.append(shape)
        cols = np.arange(shape[1]) * 1.0
        return np.broadcast_to(cols * 100.0, shape).astype("f8")  # very steep, faces east

    site_dir = prepare_site(
        _landslide_site(["G_B", "G_C"]),
        tmp_path / "d",
        tmp_path / "r",
        cropper=_with_geometry(cropper),
        dem_source=steep_east_slope,
    )

    block = json.loads((site_dir / SITE_FILE).read_text())["slope_echo"]
    assert [o["id"] for o in block["overlays"]] == ["radar_blind"]
    assert (site_dir / "ext" / "radar_blind.png").is_file()
    assert len(asked) == 1


def test_no_geometry_means_no_dem_fetch_and_no_overlay(tmp_path: Path) -> None:
    import json

    cropper, _ = _fake_cropper()

    def must_not_be_called(bounds, shape):
        raise AssertionError("DEM fetched without geometry")

    site_dir = prepare_site(
        _landslide_site(["G_B", "G_C"]),
        tmp_path / "d",
        tmp_path / "r",
        cropper=cropper,
        dem_source=must_not_be_called,
    )

    assert json.loads((site_dir / SITE_FILE).read_text())["slope_echo"]["overlays"] == []


def test_a_failing_dem_download_does_not_stop_the_site(tmp_path: Path) -> None:
    cropper, _ = _fake_cropper()

    def offline(bounds, shape):
        raise OSError("network down")

    site_dir = prepare_site(
        _landslide_site(["G_B", "G_C"]),
        tmp_path / "d",
        tmp_path / "r",
        cropper=_with_geometry(cropper),
        dem_source=offline,
    )

    assert (site_dir / SITE_FILE).is_file()
    assert not (site_dir / "ext" / "radar_blind.png").exists()


def _fake_pair_cropper(epsg: int = 32635):
    from pipeline.remote_crop import PairCrop, Raster

    def cropper(granule_id: str, bbox: BBox, cache_dir: Path) -> PairCrop:
        reference, secondary = {"P_BC": ("G_B", "G_C"), "P_CD": ("G_C", "G_D")}[granule_id]
        coherence = Raster(
            x=498000.0 + 20.0 * np.arange(200),
            y=2000.0 - 20.0 * np.arange(200),
            values=np.full((200, 200), 0.8, dtype="f4"),
        )
        phase = Raster(
            x=498000.0 + 80.0 * np.arange(50),
            y=2000.0 - 80.0 * np.arange(50),
            values=np.zeros((50, 50), dtype="f4"),
        )
        return PairCrop(
            granule_id, ACQUIRED[reference], ACQUIRED[secondary], epsg, 0.2384, coherence, phase
        )

    return cropper


def test_landslide_site_gets_coherence_and_motion_from_pairs(tmp_path: Path) -> None:
    import json

    cropper, _ = _fake_cropper()
    site = _landslide_site(["G_B", "G_C", "G_D"]).model_copy(update={"pairs": ["P_CD", "P_BC"]})

    site_dir = prepare_site(
        site, tmp_path / "d", tmp_path / "r", cropper=cropper, pair_cropper=_fake_pair_cropper()
    )

    block = json.loads((site_dir / SITE_FILE).read_text())["slope_echo"]
    layers = {layer["id"]: layer for layer in block["layers"]}
    assert [f["from"] for f in layers["coherence"]["frames"]] == ["2026-10-21", "2026-11-02"]
    assert (site_dir / layers["displacement"]["frames"][0]["file"]).is_file()


def test_pairs_must_join_the_site_dates(tmp_path: Path) -> None:
    cropper, _ = _fake_cropper()
    site = _landslide_site(["G_B", "G_C"]).model_copy(update={"pairs": ["P_CD"]})  # G_D missing

    with pytest.raises(ValueError, match="2026-11-14"):
        prepare_site(
            site, tmp_path / "d", tmp_path / "r", cropper=cropper, pair_cropper=_fake_pair_cropper()
        )


def test_pairs_on_another_projection_are_rejected(tmp_path: Path) -> None:
    cropper, _ = _fake_cropper()
    site = _landslide_site(["G_B", "G_C"]).model_copy(update={"pairs": ["P_BC"]})

    with pytest.raises(ValueError, match="same track and frame"):
        prepare_site(
            site,
            tmp_path / "d",
            tmp_path / "r",
            cropper=cropper,
            pair_cropper=_fake_pair_cropper(epsg=32636),
        )
