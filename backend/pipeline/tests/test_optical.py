"""Camera (optical) pictures from NASA HLS: scene choice, cloud check, colours, files.
No network: the catalogue search and the image reader are faked."""

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pipeline.optical import (
    OPTICAL_NUMBERS,
    Scene,
    SiteGrid,
    cached,
    choose_frames,
    clear_fraction,
    run_optical,
    true_colour_rgba,
)

EVENT = dt.date(2026, 10, 10)
RADAR = [dt.date(2026, 9, 29), dt.date(2026, 10, 11)]


def _scene(day: str, hour: int = 6) -> Scene:
    date = dt.date.fromisoformat(day)
    acquired = dt.datetime.combine(date, dt.time(hour), tzinfo=dt.UTC)
    return Scene(scene_id=f"HLS.{day}", acquired=acquired, band_urls={})


def test_clear_fraction_counts_cloud_shadow_and_their_edges_as_not_clear() -> None:
    # 0 clear · 2 cloud · 4 next to cloud · 8 shadow · 16 snow · 32 water · NaN no data
    fmask = np.array([0, 2, 4, 8, 16, 32, np.nan, np.nan], dtype=np.float32)

    assert clear_fraction(fmask) == pytest.approx(3 / 6)  # clear, snow, water


def test_clear_fraction_of_an_empty_window_is_zero() -> None:
    assert clear_fraction(np.full(4, np.nan, dtype=np.float32)) == 0.0


def test_each_radar_pass_gets_the_clearest_scene_on_its_side_of_the_event() -> None:
    candidates = [
        (_scene("2026-09-27"), 0.95),
        (_scene("2026-09-30"), 0.99),  # clearest before → for 29 Sep
        (_scene("2026-10-09"), 1.00),  # clear, but before the slide: never for 11 Oct
        (_scene("2026-10-11"), 0.90),  # after the slide → for 11 Oct
    ]

    chosen = choose_frames(candidates, RADAR, EVENT)

    assert [s.scene_id for s, _ in chosen] == ["HLS.2026-09-30", "HLS.2026-10-11"]


def test_cloudy_or_far_scenes_are_not_used() -> None:
    candidates = [(_scene("2026-09-28"), 0.40), (_scene("2026-09-01"), 1.0)]

    assert choose_frames(candidates, RADAR[:1], EVENT) == []


def test_first_clear_scene_after_the_event_is_added_when_no_pass_matches_it() -> None:
    candidates = [(_scene("2026-10-12"), 0.5), (_scene("2026-10-19"), 0.98)]

    chosen = choose_frames(candidates, RADAR[:1], EVENT)

    assert [s.scene_id for s, _ in chosen] == ["HLS.2026-10-19"]


def test_one_scene_serving_two_passes_appears_once() -> None:
    passes = [dt.date(2026, 9, 1), dt.date(2026, 9, 5)]

    chosen = choose_frames([(_scene("2026-09-03"), 1.0)], passes, EVENT)

    assert len(chosen) == 1


def test_true_colour_is_transparent_where_there_is_no_data() -> None:
    band = np.array([[0.0, 0.35, np.nan]], dtype=np.float32)

    rgba = true_colour_rgba(band, band, band)

    assert rgba[0, 0].tolist() == [0, 0, 0, 255]
    assert rgba[0, 1].tolist() == [255, 255, 255, 255]
    assert rgba[0, 2, 3] == 0


def test_run_writes_one_picture_per_chosen_scene_and_a_provenance_file(tmp_path: Path) -> None:
    grid = SiteGrid(bounds_merc=(0.0, 0.0, 1000.0, 1000.0), shape=(4, 5))
    scenes = [_scene("2026-09-30"), _scene("2026-10-11")]

    def fake_read(scene: Scene, band: str, _grid: SiteGrid) -> np.ndarray:
        if band == "Fmask":
            return np.zeros(_grid.shape, dtype=np.float32)
        return np.full(_grid.shape, 0.1, dtype=np.float32)

    ext_dir = run_optical("s", grid, RADAR, EVENT, tmp_path, search=lambda: scenes, read=fake_read)

    numbers = json.loads((ext_dir / OPTICAL_NUMBERS).read_text())
    assert [f["date"] for f in numbers["frames"]] == ["2026-09-30", "2026-10-11"]
    assert numbers["frames"][0]["scene_id"] == "HLS.2026-09-30"
    assert numbers["frames"][0]["clear_pct"] == 100.0
    picture = Image.open(ext_dir / "optical" / "2026-10-11.png")
    assert picture.size == (5, 4)


def test_no_clear_scene_is_an_error_not_an_empty_layer(tmp_path: Path) -> None:
    grid = SiteGrid(bounds_merc=(0.0, 0.0, 1000.0, 1000.0), shape=(2, 2))

    def cloudy(_scene: Scene, _band: str, g: SiteGrid) -> np.ndarray:
        return np.full(g.shape, 2.0, dtype=np.float32)

    with pytest.raises(ValueError, match="clear"):
        run_optical(
            "s", grid, RADAR, EVENT, tmp_path, search=lambda: [_scene("2026-09-30")], read=cloudy
        )


def test_an_unreadable_scene_is_skipped_not_fatal(tmp_path: Path) -> None:
    grid = SiteGrid(bounds_merc=(0.0, 0.0, 1000.0, 1000.0), shape=(2, 2))
    scenes = [_scene("2026-09-28"), _scene("2026-09-30")]

    def flaky(scene: Scene, band: str, g: SiteGrid) -> np.ndarray:
        if scene.scene_id == "HLS.2026-09-28":
            raise OSError("502 Bad Gateway")
        return np.zeros(g.shape, dtype=np.float32)

    ext_dir = run_optical("s", grid, RADAR, EVENT, tmp_path, search=lambda: scenes, read=flaky)

    frames = json.loads((ext_dir / OPTICAL_NUMBERS).read_text())["frames"]
    assert [f["date"] for f in frames] == ["2026-09-30"]


def test_cached_reader_fetches_each_window_once(tmp_path: Path) -> None:
    grid = SiteGrid(bounds_merc=(0.0, 0.0, 1000.0, 1000.0), shape=(2, 3))
    calls: list[str] = []

    def inner(scene: Scene, band: str, g: SiteGrid) -> np.ndarray:
        calls.append(band)
        return np.ones(g.shape, dtype=np.float32)

    read = cached(inner, tmp_path / "cache")
    first = read(_scene("2026-09-30"), "B04", grid)
    again = read(_scene("2026-09-30"), "B04", grid)

    assert calls == ["B04"]
    assert np.array_equal(first, again)
