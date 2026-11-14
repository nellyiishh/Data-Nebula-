"""Registered landslides near a site from NASA COOLR (no network: the service is faked)."""

import json
from pathlib import Path

import pytest

from pipeline.catalog import CATALOG_FILE, catalog_entries, compass, run_catalog
from pipeline.exposure import Center
from pipeline.prepare_nisar import ManifestSite

CENTER = Center(lon=0.0, lat=0.0, label="the village")
DEG_PER_KM = 1 / 111.195


def _report(day_ms: int, title: str, x_km: float, y_km: float, **attrs: object) -> dict:
    return {
        "attributes": {
            "event_date": day_ms,
            "event_title": title,
            "landslide_category": "landslide",
            "landslide_trigger": "rain",
            "source_name": "AKI Press",
            "source_link": "http://example.org/news",
            "event_import_source": "GLC",
            **attrs,
        },
        "geometry": {"x": x_km * DEG_PER_KM, "y": y_km * DEG_PER_KM},
    }


MS_2017_04_23 = 1492905600000
MS_2019_05_01 = 1556668800000
MS_2010_01_01 = 1262304000000


def test_entries_are_newest_first_with_distance_and_direction() -> None:
    features = [
        _report(MS_2017_04_23, "Kurbu-Tash slide", 0.0, 30.0),
        _report(MS_2019_05_01, "Ayu slide", -20.0, 0.0, landslide_trigger="downpour"),
    ]

    entries = catalog_entries(features, CENTER)

    assert [e.date.isoformat() for e in entries] == ["2019-05-01", "2017-04-23"]
    assert entries[0].name == "Ayu slide (20 km W)"
    assert entries[1].name == "Kurbu-Tash slide (30 km N)"
    assert entries[0].type == "landslide, downpour"


def test_source_names_the_catalogue_and_the_original_report() -> None:
    entry = catalog_entries([_report(MS_2017_04_23, "A", 1.0, 1.0)], CENTER)[0]

    assert entry.source.name == "NASA COOLR (GLC) · AKI Press"
    assert entry.source.url == "http://example.org/news"


def test_only_the_newest_ones_are_kept() -> None:
    features = [_report(MS_2010_01_01 + i * 86_400_000, f"E{i}", 5.0, 0.0) for i in range(15)]

    entries = catalog_entries(features, CENTER, limit=10)

    assert len(entries) == 10
    assert entries[0].name.startswith("E14")


def test_a_report_without_a_date_or_link_is_still_usable_or_skipped() -> None:
    no_link = _report(MS_2017_04_23, "No link", 1.0, 0.0, source_link=None)
    no_date = _report(MS_2017_04_23, "No date", 1.0, 0.0, event_date=None)

    entries = catalog_entries([no_link, no_date], CENTER)

    assert [e.name.split(" (")[0] for e in entries] == ["No link"]
    assert entries[0].source.url is None


@pytest.mark.parametrize(
    ("dx", "dy", "expected"), [(0, 1, "N"), (1, 1, "NE"), (1, 0, "E"), (0, -1, "S"), (-1, 1, "NW")]
)
def test_compass_direction(dx: float, dy: float, expected: str) -> None:
    assert compass(0.0, 0.0, dx * DEG_PER_KM, dy * DEG_PER_KM) == expected


def test_run_writes_the_catalogue_file_for_write_site(tmp_path: Path) -> None:
    queries: list[dict] = []

    def fake_query(params: dict) -> dict:
        queries.append(params)
        return {"features": [_report(MS_2017_04_23, "Kurbu-Tash slide", 0.0, 30.0)]}

    site = ManifestSite.model_validate(
        {
            "id": "s",
            "name": "S",
            "change_type": "landslide",
            "bbox": [-1.0, -1.0, 1.0, 1.0],
            "granules": ["a", "b"],
        }
    )
    ext_dir = run_catalog(site, tmp_path, radius_km=100, query=fake_query)

    assert queries[0]["distance"] == 100_000
    written = json.loads((ext_dir / CATALOG_FILE).read_text())
    assert written["entries"][0]["name"] == "Kurbu-Tash slide (30 km N)"
    assert written["radius_km"] == 100
