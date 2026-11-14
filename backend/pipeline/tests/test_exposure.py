"""Buildings and roads near the slide from OpenStreetMap (no network: Overpass is faked)."""

import json
from pathlib import Path

import pytest

from pipeline.exposure import (
    EXPOSURE_GEOJSON,
    EXPOSURE_NUMBERS,
    Center,
    exposure_center,
    haversine_km,
    run_exposure,
    summarize,
)
from pipeline.prepare_nisar import ManifestSite

# At the equator 1 km is ~0.008983 degrees of longitude.
KM = 1 / 111.195
CENTER = Center(lon=0.0, lat=0.0, label="the test point")


def _square_way(lon: float, lat: float, tags: dict, half_km: float = 0.01) -> dict:
    d = half_km * KM
    ring = [(lon - d, lat - d), (lon + d, lat - d), (lon + d, lat + d), (lon - d, lat + d)]
    ring.append(ring[0])
    return {"type": "way", "tags": tags, "geometry": [{"lon": x, "lat": y} for x, y in ring]}


def _line(points_km: list[tuple[float, float]], highway: str) -> dict:
    geometry = [{"lon": x * KM, "lat": y * KM} for x, y in points_km]
    return {"type": "way", "tags": {"highway": highway}, "geometry": geometry}


def _place(name: str, x_km: float, place: str = "village", **tags: str) -> dict:
    return {
        "type": "node",
        "lon": x_km * KM,
        "lat": 0.0,
        "tags": {"place": place, "name": name, **tags},
    }


ELEMENTS = [
    _square_way(0.5 * KM, 0.0, {"building": "house"}),  # inside, 0.5 km east
    {"type": "node", "lon": 0.0, "lat": 1.0 * KM, "tags": {"building": "yes"}},  # inside
    _square_way(3.0 * KM, 0.0, {"building": "barn"}),  # outside the 2 km circle
    {
        "type": "relation",
        "tags": {"building": "school"},
        "bounds": {
            "minlon": -1.1 * KM,
            "maxlon": -0.9 * KM,
            "minlat": -0.1 * KM,
            "maxlat": 0.1 * KM,
        },
    },  # inside, 1 km west
    _line([(-4.0, 0.0), (4.0, 0.0)], "unclassified"),  # crosses the circle: 4 km inside
    _line([(0.0, -0.5), (0.0, 0.5)], "footway"),  # not a road
    _place("Far village", 6.0),
    _place("Near hamlet", 0.8, place="hamlet", **{"name:en": "Near Hamlet"}),
]


def test_haversine_matches_known_distance() -> None:
    assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.195, rel=1e-3)


def test_counts_buildings_inside_the_circle_once_each() -> None:
    _, exposure = summarize(ELEMENTS, CENTER, radius_km=2.0)

    assert exposure.buildings == 3
    assert exposure.radius_km == 2.0


def test_road_length_is_clipped_to_the_circle_and_skips_paths() -> None:
    _, exposure = summarize(ELEMENTS, CENTER, radius_km=2.0)

    assert exposure.roads_km == pytest.approx(4.0, abs=0.05)


def test_nearest_named_place_prefers_the_english_name() -> None:
    _, exposure = summarize(ELEMENTS, CENTER, radius_km=2.0)

    assert exposure.nearest_settlement == "Near Hamlet"
    assert exposure.distance_km == pytest.approx(0.8, abs=0.01)


def test_geojson_has_building_points_and_road_lines_the_map_can_draw() -> None:
    geojson, _ = summarize(ELEMENTS, CENTER, radius_km=2.0)

    kinds = [(f["geometry"]["type"], f["properties"]["kind"]) for f in geojson["features"]]
    assert kinds.count(("Point", "building")) == 3
    assert ("LineString", "road") in kinds
    for feature in geojson["features"]:
        if feature["geometry"]["type"] == "LineString":
            for lon, lat in feature["geometry"]["coordinates"]:
                assert haversine_km(0.0, 0.0, lon, lat) <= 2.0 + 0.05


def test_method_says_where_it_measured_from_and_what_it_is_not() -> None:
    _, exposure = summarize(ELEMENTS, CENTER, radius_km=2.0)

    assert "the test point" in exposure.method
    assert "not a hazard" in exposure.method
    assert "OpenStreetMap" in exposure.source.name


def test_method_warns_when_not_measured_from_the_slide() -> None:
    _, from_village = summarize(ELEMENTS, CENTER, radius_km=2.0)
    _, from_slide = summarize(ELEMENTS, Center(0.0, 0.0, "the slide", is_slide=True), 2.0)

    assert "not mapped yet" in from_village.method
    assert "not mapped yet" not in from_slide.method


def test_no_named_place_nearby_is_an_error_not_a_made_up_number() -> None:
    with pytest.raises(ValueError, match="named settlement"):
        summarize(ELEMENTS[:2], CENTER, radius_km=2.0)


def _site(points: list[dict]) -> ManifestSite:
    return ManifestSite.model_validate(
        {
            "id": "s",
            "name": "S",
            "change_type": "landslide",
            "bbox": [10.0, 20.0, 12.0, 22.0],
            "granules": ["a", "b"],
            "points_of_interest": points,
        }
    )


def test_centre_is_the_slide_point_then_the_first_point_then_the_bbox() -> None:
    village = {"id": "village", "name": "Village", "lon": 1.0, "lat": 2.0}
    slide = {"id": "slide", "name": "Slide", "lon": 3.0, "lat": 4.0}

    assert exposure_center(_site([village, slide])) == Center(3.0, 4.0, "Slide", is_slide=True)
    assert exposure_center(_site([village])) == Center(1.0, 2.0, "Village")
    assert exposure_center(_site([])) == Center(11.0, 21.0, "the centre of the study area")


def test_run_writes_both_files_for_write_site(tmp_path: Path) -> None:
    queries: list[str] = []

    def fake_overpass(query: str) -> dict:
        queries.append(query)
        return {"elements": ELEMENTS}

    site = _site([{"id": "slide", "name": "Slide", "lon": 0.0, "lat": 0.0}])
    ext_dir = run_exposure(site, tmp_path, radius_km=2.0, fetch=fake_overpass)

    assert len(queries) == 1 and "around:2000" in queries[0]
    numbers = json.loads((ext_dir / EXPOSURE_NUMBERS).read_text())
    assert numbers["buildings"] == 3
    geojson = json.loads((ext_dir / EXPOSURE_GEOJSON).read_text())
    assert geojson["type"] == "FeatureCollection"


def test_a_road_that_leaves_and_reenters_becomes_two_pieces() -> None:
    # A U-shaped road: in at the west, out to 5 km north, back in at the east.
    road = _line([(-1.0, 0.0), (-1.0, 5.0), (1.0, 5.0), (1.0, 0.0)], "track")
    geojson, exposure = summarize([road, _place("V", 0.1)], CENTER, radius_km=2.0)

    lines = [f for f in geojson["features"] if f["geometry"]["type"] == "LineString"]
    assert len(lines) == 2
    # Each vertical leg is inside from y=0 up to sqrt(2² - 1²) ≈ 1.732 km.
    assert exposure.roads_km == pytest.approx(2 * 3**0.5, abs=0.01)
