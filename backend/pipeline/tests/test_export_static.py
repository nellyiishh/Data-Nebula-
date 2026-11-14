import json
from itertools import pairwise
from pathlib import Path

import pytest

from pipeline.export_static import export_static
from testsupport import (
    TINY_DATES,
    TINY_SITE_ID,
    TINY_SLIDE_ID,
    build_tiny_landslide,
    build_tiny_site,
    write_tiny_ext,
)


@pytest.fixture
def derived(tmp_path: Path) -> Path:
    data_dir = tmp_path / "derived"
    build_tiny_landslide(data_dir, write_tiny_ext(tmp_path / "ext"))
    build_tiny_site(data_dir)
    return data_dir


def test_export_writes_the_web_static_layout(derived: Path, tmp_path: Path) -> None:
    out = tmp_path / "web-data"

    export_static(derived, out, [TINY_SLIDE_ID])

    site_dir = out / "sites" / TINY_SLIDE_ID
    detail = json.loads((out / "sites" / f"{TINY_SLIDE_ID}.json").read_text())
    assert detail["slope_echo"]["layers"][0]["frames"][0]["from"] == "2026-06-20"
    for date in TINY_DATES:
        assert (site_dir / "layers" / "hh" / f"{date.isoformat()}.png").is_file()
    names = [f"{a.isoformat()}_{b.isoformat()}" for a, b in pairwise(TINY_DATES)]
    assert sorted(p.name for p in (site_dir / "change").glob("*.png")) == [
        f"{n}.png" for n in names
    ]
    change = json.loads((site_dir / "change" / f"{names[0]}.json").read_text())
    assert change["from"] == "2026-06-20" and change["darker_pct"] == 40.0
    point = json.loads((site_dir / "points" / "p1.json").read_text())
    assert [entry["date"] for entry in point["series"]] == [d.isoformat() for d in TINY_DATES]
    assert (site_dir / "ext" / "rain.json").is_file()
    assert (site_dir / "stats.json").is_file()


def test_export_keeps_other_sites_in_the_index(derived: Path, tmp_path: Path) -> None:
    out = tmp_path / "web-data"
    out.mkdir()
    others = [{"id": "fake-site", "name": "Fake"}, {"id": TINY_SLIDE_ID, "name": "Old name"}]
    (out / "sites.json").write_text(json.dumps(others))

    export_static(derived, out, [TINY_SLIDE_ID])

    index = json.loads((out / "sites.json").read_text())
    assert [site["id"] for site in index] == ["fake-site", TINY_SLIDE_ID]
    assert index[1]["name"] == "Tiny landslide"


def test_export_without_ids_exports_every_site(derived: Path, tmp_path: Path) -> None:
    exported = export_static(derived, tmp_path / "web-data")

    assert sorted(exported) == sorted([TINY_SITE_ID, TINY_SLIDE_ID])


def test_export_rejects_an_unknown_site(derived: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no-such-site"):
        export_static(derived, tmp_path / "web-data", ["no-such-site"])
