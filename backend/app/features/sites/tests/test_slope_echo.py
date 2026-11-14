"""Landslide sites: the Slope Echo block, per-type layers, display ranges, site files."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.features.sites.display import CHANGE_THRESHOLD_DB, DB_RANGE
from app.main import create_app
from testsupport import TINY_SLIDE_ID, build_tiny_landslide, write_tiny_ext

SITE = f"/api/v1/sites/{TINY_SLIDE_ID}"


@pytest.fixture
def slide_client(tmp_path: Path) -> Iterator[TestClient]:
    build_tiny_landslide(tmp_path / "derived", write_tiny_ext(tmp_path / "ext"))
    with TestClient(create_app(Settings(data_dir=tmp_path / "derived"))) as client:
        yield client


def test_landslide_site_serves_its_slope_echo_block(slide_client: TestClient) -> None:
    site = slide_client.get(SITE).json()

    assert site["change_type"] == "landslide"
    block = site["slope_echo"]
    assert block["event"]["label"] == "Test slide"
    assert set(block["story"]) == {"place", "rain", "radar", "tracking", "exposure"}
    # "from" is a Python keyword; the JSON must still use the web's field name.
    # Unused optional fields are left out, as in the web's static files (not null).
    assert block["layers"][0]["frames"][0] == {
        "from": "2026-06-20",
        "to": "2026-07-02",
        "file": "ext/coherence/2026-06-20_2026-07-02.png",
    }


def test_landslide_site_has_no_water_layer(slide_client: TestClient) -> None:
    site = slide_client.get(SITE).json()

    assert site["layers"] == ["hh", "hv", "rgb"]
    assert slide_client.get(f"{SITE}/layers/water/2026-06-20.png").status_code == 404


def test_site_reports_the_display_ranges_its_images_use(slide_client: TestClient) -> None:
    display = slide_client.get(SITE).json()["display"]

    assert (display["hh"]["min_db"], display["hh"]["max_db"]) == DB_RANGE["hh"]
    assert (display["hv"]["min_db"], display["hv"]["max_db"]) == DB_RANGE["hv"]
    assert display["change_threshold_db"] == CHANGE_THRESHOLD_DB
    assert display["darker_color"].startswith("#")


def test_ext_files_are_served(slide_client: TestClient) -> None:
    rain = slide_client.get(f"{SITE}/files/ext/rain.json")
    scar = slide_client.get(f"{SITE}/files/ext/scar.geojson")
    layer = slide_client.get(f"{SITE}/files/layers/hh/2026-06-20.png")

    assert rain.status_code == 200 and rain.json()["series"][0]["mm"] == 4.2
    assert scar.headers["content-type"] == "application/geo+json"
    assert layer.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    "relative",
    ["stack.npz", "site.json", "ext/missing.json", "ext/../stack.npz", "ext/%2e%2e/stack.npz"],
)
def test_only_existing_ext_and_layer_files_are_served(
    slide_client: TestClient, relative: str
) -> None:
    response = slide_client.get(f"{SITE}/files/{relative}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] in {"file.not_found", "route.not_found"}


def test_web_example_site_round_trips_unchanged() -> None:
    """The web team's own example file must pass through the backend byte-for-byte."""
    import json

    from app.core.config import REPO_ROOT
    from app.features.sites.schemas import SiteDetail

    example = REPO_ROOT / "web" / "public" / "data" / "sites" / "togus-bulak.json"
    if not example.is_file():
        pytest.skip("web example data not present")
    raw = json.loads(example.read_text())

    served = json.loads(SiteDetail.model_validate(raw).model_dump_json())

    assert served["slope_echo"] == raw["slope_echo"]
