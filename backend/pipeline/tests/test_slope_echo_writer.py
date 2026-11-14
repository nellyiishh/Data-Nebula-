import json
from pathlib import Path

import pytest

from testsupport import (
    TINY_EXT_FILES,
    TINY_SLIDE_ID,
    build_tiny_landslide,
    tiny_slope_echo,
    write_tiny_ext,
)


def test_ext_files_are_copied_into_the_site(tmp_path: Path) -> None:
    site_dir = build_tiny_landslide(tmp_path / "derived", write_tiny_ext(tmp_path / "ext"))

    for relative in TINY_EXT_FILES:
        assert (site_dir / "ext" / relative).is_file()
    assert not (site_dir / "layers" / "water").exists()


def test_a_missing_referenced_file_fails_and_leaves_nothing(tmp_path: Path) -> None:
    ext_dir = write_tiny_ext(tmp_path / "ext")
    (ext_dir / "rain.json").unlink()

    with pytest.raises(ValueError, match="ext/rain.json"):
        build_tiny_landslide(tmp_path / "derived", ext_dir)
    assert not (tmp_path / "derived" / TINY_SLIDE_ID).exists()


def test_a_reference_to_a_missing_layer_date_fails(tmp_path: Path) -> None:
    block = tiny_slope_echo()
    block["raw_example"]["db"] = "layers/hh/2030-01-01.png"

    with pytest.raises(ValueError, match="2030-01-01"):
        build_tiny_landslide(tmp_path / "derived", write_tiny_ext(tmp_path / "ext"), block)


@pytest.mark.parametrize("bad", ["/etc/passwd", "../secrets.json", "ext/../../x", ""])
def test_paths_outside_the_site_folder_are_rejected(tmp_path: Path, bad: str) -> None:
    block = tiny_slope_echo()
    block["rain"]["file"] = bad

    with pytest.raises(ValueError, match="inside the site folder"):
        build_tiny_landslide(tmp_path / "derived", write_tiny_ext(tmp_path / "ext"), block)


def test_site_json_keeps_the_web_field_names(tmp_path: Path) -> None:
    site_dir = build_tiny_landslide(tmp_path / "derived", write_tiny_ext(tmp_path / "ext"))

    block = json.loads((site_dir / "site.json").read_text())["slope_echo"]
    assert block["layers"][0]["frames"][0]["from"] == "2026-06-20"
