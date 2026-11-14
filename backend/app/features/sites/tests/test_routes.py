import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.geo import mercator_to_lonlat
from testsupport import (
    FRONTEND_ORIGIN,
    HV_OFFSET_DB,
    TINY_DATES,
    TINY_SITE_ID,
    WATER_COLUMNS,
    WATER_DB,
)

BASE = "/api/v1/sites"
SITE = f"{BASE}/{TINY_SITE_ID}"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ISO_DATES = [d.isoformat() for d in TINY_DATES]


def _error_code(response) -> str:
    return response.json()["error"]["code"]


def test_list_sites_returns_each_prepared_site(client: TestClient) -> None:
    response = client.get(BASE)

    assert response.status_code == 200
    sites = response.json()
    assert [s["id"] for s in sites] == [TINY_SITE_ID]
    assert sites[0]["source"] == "demo"
    assert sites[0]["change_type"] == "water"
    assert sites[0]["center"] == pytest.approx(list(mercator_to_lonlat(500.0, 500.0)))


def test_get_site_returns_dates_corners_layers_and_provenance(client: TestClient) -> None:
    response = client.get(SITE)

    assert response.status_code == 200
    site = response.json()
    assert site["dates"] == ISO_DATES
    assert site["layers"] == ["hh", "hv", "rgb", "water"]
    west, south = mercator_to_lonlat(0.0, 0.0)
    east, north = mercator_to_lonlat(1000.0, 1000.0)
    flat_corners = [value for corner in site["corners"] for value in corner]
    assert flat_corners == pytest.approx([west, north, east, north, east, south, west, south])
    assert site["acquisitions"][0] == {
        "date": ISO_DATES[0],
        "granule_id": None,
        "band": "L",
        "polarizations": ["HH", "HV"],
    }
    assert site["points_of_interest"][0]["id"] == "p1"


def test_unknown_site_returns_error_envelope(client: TestClient) -> None:
    response = client.get(f"{BASE}/no-such-site")

    assert response.status_code == 404
    assert _error_code(response) == "site.not_found"
    assert response.json()["error"]["details"] == {"site_id": "no-such-site"}


def test_malformed_site_id_is_rejected(client: TestClient) -> None:
    response = client.get(f"{BASE}/Not_A_Site")

    assert response.status_code == 422
    assert _error_code(response) == "request.invalid"


def test_stats_report_water_area_per_date(client: TestClient) -> None:
    response = client.get(f"{SITE}/stats")

    assert response.status_code == 200
    series = response.json()["series"]
    assert [entry["date"] for entry in series] == ISO_DATES
    expected_km2 = [columns * 10 * 0.01 for columns in WATER_COLUMNS]
    assert [entry["water_km2"] for entry in series] == pytest.approx(expected_km2, rel=1e-3)


def test_layer_image_is_served_as_png(client: TestClient) -> None:
    response = client.get(f"{SITE}/layers/hh/{ISO_DATES[0]}.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(PNG_SIGNATURE)


def test_layer_image_for_unknown_date_is_404(client: TestClient) -> None:
    response = client.get(f"{SITE}/layers/hh/2026-01-01.png")

    assert response.status_code == 404
    assert _error_code(response) == "date.not_found"


def test_unknown_layer_name_is_rejected(client: TestClient) -> None:
    response = client.get(f"{SITE}/layers/ndvi/{ISO_DATES[0]}.png")

    assert response.status_code == 422
    assert _error_code(response) == "request.invalid"


def test_change_image_marks_new_water_as_darker(client: TestClient) -> None:
    response = client.get(f"{SITE}/change.png", params={"from": ISO_DATES[0], "to": ISO_DATES[1]})

    assert response.status_code == 200
    image = Image.open(io.BytesIO(response.content)).convert("RGBA")
    newly_flooded = image.getpixel((3, 0))  # column 3 turned to water between dates 0 and 1
    unchanged = image.getpixel((8, 0))
    assert isinstance(newly_flooded, tuple) and isinstance(unchanged, tuple)
    assert newly_flooded[3] > 0
    assert newly_flooded[0] > newly_flooded[2]  # red = got darker to radar
    assert unchanged[3] == 0


def test_change_image_for_unknown_date_is_404(client: TestClient) -> None:
    response = client.get(f"{SITE}/change.png", params={"from": ISO_DATES[0], "to": "2026-01-01"})

    assert response.status_code == 404
    assert _error_code(response) == "date.not_found"


def test_point_timeseries_inside_site(client: TestClient) -> None:
    lon, lat = mercator_to_lonlat(50.0, 450.0)  # centre of row 5, column 0: water on every date

    response = client.get(f"{SITE}/timeseries", params={"lon": lon, "lat": lat})

    assert response.status_code == 200
    series = response.json()["series"]
    assert [entry["date"] for entry in series] == ISO_DATES
    assert [entry["hh_db"] for entry in series] == pytest.approx([WATER_DB] * 3, abs=0.01)
    assert [entry["hv_db"] for entry in series] == pytest.approx(
        [WATER_DB + HV_OFFSET_DB] * 3, abs=0.01
    )


def test_point_timeseries_outside_site_is_422(client: TestClient) -> None:
    response = client.get(f"{SITE}/timeseries", params={"lon": 10.0, "lat": 10.0})

    assert response.status_code == 422
    assert _error_code(response) == "point.outside_site"


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    echoed = client.get(BASE, headers={"X-Request-ID": "abc-123"})
    generated = client.get(BASE)

    assert echoed.headers["X-Request-ID"] == "abc-123"
    assert len(generated.headers["X-Request-ID"]) == 32


def test_cors_allows_the_configured_frontend(client: TestClient) -> None:
    response = client.get(BASE, headers={"Origin": FRONTEND_ORIGIN})

    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN


def test_change_stats_measure_new_water_as_darker(client: TestClient) -> None:
    response = client.get(f"{SITE}/change-stats", params={"from": ISO_DATES[0], "to": ISO_DATES[1]})

    assert response.status_code == 200
    stats = response.json()
    # Columns 3-4 turned to water (-15 dB); the 3x3 mean spreads that over columns 2-5.
    assert stats["from"] == ISO_DATES[0] and stats["to"] == ISO_DATES[1]
    assert stats["polarization"] == "hh"
    assert stats["threshold_db"] == 3.0
    assert stats["valid_pct"] == 100.0
    assert stats["darker_pct"] == 40.0
    assert stats["brighter_pct"] == 0.0
    assert stats["changed_pct"] == 40.0
    assert stats["darker_km2"] == pytest.approx(0.4, rel=1e-3)
    assert stats["changed_km2"] == pytest.approx(0.4, rel=1e-3)
    assert stats["mean_delta_db"] == pytest.approx(-3.0, abs=0.01)


def test_change_stats_ignore_pixels_without_data(client: TestClient) -> None:
    response = client.get(f"{SITE}/change-stats", params={"from": ISO_DATES[1], "to": ISO_DATES[2]})

    stats = response.json()
    # Pixel (9, 9) has no data on the last date: 99 valid pixels, 50 of them brighter.
    assert stats["valid_pct"] == 99.0
    assert stats["brighter_pct"] == pytest.approx(100 * 50 / 99, abs=0.05)
    assert stats["darker_pct"] == 0.0
    assert stats["brighter_km2"] == pytest.approx(0.5, rel=1e-3)


def test_change_stats_for_unknown_date_is_404(client: TestClient) -> None:
    response = client.get(f"{SITE}/change-stats", params={"from": ISO_DATES[0], "to": "2026-01-01"})

    assert response.status_code == 404
    assert _error_code(response) == "date.not_found"
