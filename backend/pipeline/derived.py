"""Layers derived for a landslide story while a site is written: the raw linear-power
example, the radar-blind overlay, the scar-vs-stable validation numbers and the exposure
block (from pipeline/exposure.py output)."""

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.core.geo import lonlat_to_mercator, mercator_to_lonlat
from app.features.sites.display import CHANGE_THRESHOLD_DB, hex_color
from app.features.sites.models import MercatorBounds, pixel_at
from app.features.sites.rendering import encode_png, smoothed_difference
from app.features.sites.schemas import PointOfInterest
from app.features.sites.slope_echo import (
    Exposure,
    ExtFrame,
    ExtLayer,
    ExtOverlay,
    Legend,
    RawExample,
    SlopeEcho,
    SourceRef,
    Validation,
)
from pipeline.interferometry import PairLayers

Cube = NDArray[np.floating]
Mask = NDArray[np.bool_]

SCAR_ID, STABLE_ID, BLIND_ID = "scar", "stable", "radar_blind"
BLIND_FILE = "ext/radar_blind.png"
BLIND_RGBA = (30, 30, 30, 160)
BLIND_OVERLAY = ExtOverlay(
    id=BLIND_ID,
    kind="image",
    title="Radar blind spots",
    file=BLIND_FILE,
    description="Slopes the radar cannot see from this track: layover (steep slopes facing the "
    "radar) and shadow (steep slopes facing away). From local terrain slope only; a ridge "
    "hiding a valley further away is not marked.",
    source=SourceRef(
        name="Copernicus DEM GLO-30 (© DLR e.V., © Airbus; provided under COPERNICUS by the EU "
        "and ESA) + NISAR GCOV look geometry",
        url="https://registry.opendata.aws/copernicus-dem/",
    ),
)


# Written by pipeline/exposure.py into data/ext/<site>/, copied here by write_site.
EXPOSURE_ID = "exposure"
EXPOSURE_FILE = "ext/exposure.geojson"
EXPOSURE_NUMBERS_FILE = "ext/exposure.json"
EXPOSURE_OVERLAY = ExtOverlay(
    id=EXPOSURE_ID,
    kind="exposure",
    title="Buildings and roads nearby",
    file=EXPOSURE_FILE,
    description="Buildings (points) and drivable roads (lines) mapped in OpenStreetMap near "
    "the slide. Rural buildings are often missing from the map.",
    source=SourceRef(
        name="© OpenStreetMap contributors", url="https://www.openstreetmap.org/copyright"
    ),
)


def _read_exposure(site_dir: Path) -> Exposure | None:
    path = site_dir / EXPOSURE_NUMBERS_FILE
    return Exposure.model_validate_json(path.read_text()) if path.is_file() else None


def derive_slope_echo(
    site_dir: Path,
    block: SlopeEcho,
    dates: list[dt.date],
    hh: Cube,
    bounds_merc: MercatorBounds,
    blind: Mask | None,
    pairs: PairLayers | None = None,
    points: list[PointOfInterest] | None = None,
) -> SlopeEcho:
    """Fills what the block leaves empty and the stack can answer. Writes files under ext/."""
    update: dict[str, Any] = {}
    if pairs is not None:
        update["layers"] = _write_pair_layers(site_dir, block, pairs)
        update["point_extras"] = {
            **block.point_extras,
            **_write_point_extras(site_dir, pairs, points or [], bounds_merc),
        }
    if block.raw_example is None:
        update["raw_example"] = _write_raw_example(site_dir, dates, hh, block.event.date)
    if blind is not None:
        (site_dir / BLIND_FILE).parent.mkdir(parents=True, exist_ok=True)
        (site_dir / BLIND_FILE).write_bytes(encode_png(_mask_rgba(blind, BLIND_RGBA)))
        others = [overlay for overlay in block.overlays if overlay.id != BLIND_ID]
        update["overlays"] = [*others, BLIND_OVERLAY]
    if block.exposure is None and (exposure := _read_exposure(site_dir)) is not None:
        update["exposure"] = exposure
        overlays = update.get("overlays", block.overlays)
        if (site_dir / EXPOSURE_FILE).is_file() and all(o.id != EXPOSURE_ID for o in overlays):
            update["overlays"] = [*overlays, EXPOSURE_OVERLAY]
    if block.validation is None:
        update["validation"] = _validate(site_dir, block, dates, hh, bounds_merc, blind)
    return block.model_copy(update=update)


def event_pair(dates: list[dt.date], event: dt.date) -> tuple[int, int] | None:
    """Indices of the last pass before the event day and the first pass after it."""
    before = [i for i, d in enumerate(dates) if d < event]
    after = [i for i, d in enumerate(dates) if d > event]
    return (before[-1], after[0]) if before and after else None


def polygon_mask(
    geojson: dict[str, Any], bounds_merc: MercatorBounds, shape: tuple[int, int]
) -> Mask:
    """Pixels whose centre lies inside any polygon of a GeoJSON object (holes respected)."""
    rows, cols = shape
    xmin, ymin, xmax, ymax = bounds_merc
    lons = [
        mercator_to_lonlat(xmin + (c + 0.5) * (xmax - xmin) / cols, 0.0)[0] for c in range(cols)
    ]
    lats = [
        mercator_to_lonlat(0.0, ymax - (r + 0.5) * (ymax - ymin) / rows)[1] for r in range(rows)
    ]
    lon, lat = np.meshgrid(np.array(lons), np.array(lats))
    inside = np.zeros(shape, dtype=bool)
    for polygon in _polygons(geojson):
        in_polygon = np.zeros(shape, dtype=bool)
        for ring in polygon:  # even-odd over the outer ring and its holes
            in_polygon ^= _inside_ring(lon, lat, np.asarray(ring, dtype="f8"))
        inside |= in_polygon
    return inside


def _polygons(geojson: dict[str, Any]) -> list[list[list[list[float]]]]:
    kind = geojson.get("type")
    if kind == "FeatureCollection":
        return [p for feature in geojson["features"] for p in _polygons(feature)]
    if kind == "Feature":
        return _polygons(geojson["geometry"]) if geojson.get("geometry") else []
    if kind == "Polygon":
        return [geojson["coordinates"]]
    if kind == "MultiPolygon":
        return list(geojson["coordinates"])
    return []


def _inside_ring(lon: Cube, lat: Cube, ring: Cube) -> Mask:
    inside = np.zeros(lon.shape, dtype=bool)
    xs, ys = ring[:, 0], ring[:, 1]
    for i in range(len(ring)):
        xi, yi, xj, yj = xs[i], ys[i], xs[i - 1], ys[i - 1]
        crosses = (yi > lat) != (yj > lat)
        if yi == yj:
            continue  # horizontal edge: never crossed by a horizontal ray
        x_at = (xj - xi) * (lat - yi) / (yj - yi) + xi
        inside ^= crosses & (lon < x_at)
    return inside


def _validate(
    site_dir: Path,
    block: SlopeEcho,
    dates: list[dt.date],
    hh: Cube,
    bounds_merc: MercatorBounds,
    blind: Mask | None,
) -> Validation | None:
    outlines = {o.id: o.file for o in block.overlays if o.kind == "polygon"}
    pair = event_pair(dates, block.event.date)
    if SCAR_ID not in outlines or STABLE_ID not in outlines or pair is None:
        return None
    before, after = pair
    diff = smoothed_difference(hh[before], hh[after])
    usable = np.isfinite(diff) if blind is None else np.isfinite(diff) & ~blind
    changed = usable & (np.abs(np.nan_to_num(diff)) > CHANGE_THRESHOLD_DB)
    shape = (hh.shape[1], hh.shape[2])

    def pct_changed(file: str) -> float | None:
        region = polygon_mask(json.loads((site_dir / file).read_text()), bounds_merc, shape)
        region &= usable
        return round(100.0 * changed[region].mean(), 1) if region.any() else None

    inside, outside = pct_changed(outlines[SCAR_ID]), pct_changed(outlines[STABLE_ID])
    if inside is None or outside is None:
        return None
    blind_note = "; radar blind spots excluded" if blind is not None else ""
    return Validation(
        threshold_db=CHANGE_THRESHOLD_DB,
        pair=(dates[before], dates[after]),
        changed_inside_pct=inside,
        changed_outside_pct=outside,
        method=f"|ΔHH| > {CHANGE_THRESHOLD_DB:g} dB after a 3×3 mean, between the last pass "
        f"before ({dates[before]}) and the first pass after ({dates[after]}) the event"
        f"{blind_note}. Scar and stable areas from the site's outlines.",
    )


def _write_raw_example(
    site_dir: Path, dates: list[dt.date], hh: Cube, event: dt.date
) -> RawExample:
    """HH of the last pass before the event (else the first pass) as raw linear power with a
    plain 0..max stretch: mostly black, which is why the layers use a dB stretch."""
    pair = event_pair(dates, event)
    before = [i for i, d in enumerate(dates) if d < event]
    index = pair[0] if pair else (before[-1] if before else 0)
    date = dates[index]
    linear = 10 ** (hh[index] / 10)
    finite = np.isfinite(linear)
    peak = float(np.nanmax(linear)) if finite.any() else 1.0
    gray = (np.clip(np.nan_to_num(linear) / peak, 0, 1) * 255).astype(np.uint8)
    rgba = np.dstack([gray, gray, gray, np.where(finite, 255, 0).astype(np.uint8)])
    relative = f"ext/raw/{date.isoformat()}_linear.png"
    (site_dir / relative).parent.mkdir(parents=True, exist_ok=True)
    (site_dir / relative).write_bytes(encode_png(rgba))
    return RawExample(linear=relative, db=f"layers/hh/{date.isoformat()}.png", date=date)


def _mask_rgba(mask: Mask, rgba: tuple[int, int, int, int]) -> NDArray[np.uint8]:
    image = np.zeros((*mask.shape, 4), dtype=np.uint8)
    image[mask] = rgba
    return image


# ---- Interferogram pair layers ---------------------------------------------------------

COHERENCE_LOW_RGB = (0, 0, 255)  # 0: the surface changed between the two passes
COHERENCE_HIGH_RGB = (255, 217, 163)  # 1: unchanged
DISPLACEMENT_RANGE_CM = 1.5  # colour saturates beyond ± this
AWAY_RGB = (230, 60, 50)
TOWARD_RGB = (50, 110, 240)
NISAR_GUNW = SourceRef(
    name="NISAR L2 GUNW (NASA/ISRO), ASF DAAC", url="https://nisar-docs.asf.alaska.edu/gunw/"
)
POINT_WINDOW = 1  # pixels around a point: 3x3


def _coherence_rgba(coherence: Cube) -> NDArray[np.uint8]:
    t = np.clip(np.nan_to_num(coherence), 0.0, 1.0)[..., None]
    low, high = np.array(COHERENCE_LOW_RGB), np.array(COHERENCE_HIGH_RGB)
    rgb = (low + (high - low) * t).astype(np.uint8)
    alpha = np.where(np.isfinite(coherence), 255, 0).astype(np.uint8)
    return np.dstack([rgb, alpha])


def _displacement_rgba(los: Cube) -> NDArray[np.uint8]:
    t = np.clip(np.nan_to_num(los) / DISPLACEMENT_RANGE_CM, -1.0, 1.0)
    rgba = np.zeros((*los.shape, 4), dtype=np.uint8)
    rgba[t < 0, :3] = AWAY_RGB
    rgba[t >= 0, :3] = TOWARD_RGB
    rgba[..., 3] = np.where(np.isfinite(los), np.abs(t) * 230, 0).astype(np.uint8)
    return rgba


def _write_pair_layers(site_dir: Path, block: SlopeEcho, pairs: PairLayers) -> list[ExtLayer]:
    frames: dict[str, list[ExtFrame]] = {"coherence": [], "displacement": []}
    for i, (before, after) in enumerate(pairs.pairs):
        name = f"{before.isoformat()}_{after.isoformat()}.png"
        images = {
            "coherence": _coherence_rgba(pairs.coherence[i]),
            "displacement": _displacement_rgba(pairs.los_cm[i]),
        }
        for layer_id, rgba in images.items():
            relative = f"ext/{layer_id}/{name}"
            (site_dir / relative).parent.mkdir(parents=True, exist_ok=True)
            (site_dir / relative).write_bytes(encode_png(rgba))
            frame = {"from": before, "to": after, "file": relative}  # "from" is the JSON name
            frames[layer_id].append(ExtFrame.model_validate(frame))

    r = DISPLACEMENT_RANGE_CM
    made = [
        ExtLayer(
            id="coherence",
            kind="coherence",
            title="Coherence",
            unit="0–1",
            description="How alike two passes 12 days apart are. Low means the surface changed "
            "(sliding ground, but also snow, wet soil or growing plants).",
            source=NISAR_GUNW,
            frames=frames["coherence"],
            legend=Legend(
                colors=[hex_color(COHERENCE_LOW_RGB), hex_color(COHERENCE_HIGH_RGB)],
                labels=["0 changed", "1 unchanged"],
            ),
        ),
        ExtLayer(
            id="displacement",
            kind="displacement",
            title="Ground motion",
            unit="cm",
            description="Movement toward or away from the satellite in 12 days, relative to the "
            "site median. Blank where coherence is too low to trust.",
            source=NISAR_GUNW,
            frames=frames["displacement"],
            legend=Legend(
                colors=[hex_color(AWAY_RGB), "#00000000", hex_color(TOWARD_RGB)],
                labels=[f"−{r:g} cm away", "0", f"+{r:g} cm toward"],
            ),
        ),
    ]
    made_ids = {layer.id for layer in made}
    return [layer for layer in block.layers if layer.id not in made_ids] + made


def _window_mean(values: Cube, pixel: tuple[int, int]) -> float | None:
    row, col = pixel
    r = POINT_WINDOW
    block = values[max(row - r, 0) : row + r + 1, max(col - r, 0) : col + r + 1]
    finite = block[np.isfinite(block)]
    return float(finite.mean()) if finite.size else None


def _write_point_extras(
    site_dir: Path, pairs: PairLayers, points: list[PointOfInterest], bounds_merc: MercatorBounds
) -> dict[str, str]:
    """Per point: coherence and CUMULATIVE motion after each pair. Once a pair has no motion
    value at the point, the running total stops (None): skipping it would hide movement."""
    shape = (pairs.coherence.shape[1], pairs.coherence.shape[2])
    files: dict[str, str] = {}
    for point in points:
        pixel = pixel_at(bounds_merc, shape, *lonlat_to_mercator(point.lon, point.lat))
        if pixel is None:
            continue
        total: float | None = 0.0
        series = []
        for i, (before, after) in enumerate(pairs.pairs):
            coherence = _window_mean(pairs.coherence[i], pixel)
            step = _window_mean(pairs.los_cm[i], pixel)
            total = None if total is None or step is None else total + step
            series.append(
                {
                    "from": before.isoformat(),
                    "to": after.isoformat(),
                    "coherence": None if coherence is None else round(coherence, 2),
                    "los_cm": None if total is None else round(total, 2),
                }
            )
        relative = f"ext/points/{point.id}.json"
        (site_dir / relative).parent.mkdir(parents=True, exist_ok=True)
        (site_dir / relative).write_text(json.dumps({"series": series}, indent=2) + "\n")
        files[point.id] = relative
    return files
