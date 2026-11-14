"""Layers derived for a landslide story while a site is written: the raw linear-power
example, the radar-blind overlay and the scar-vs-stable validation numbers."""

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.core.geo import mercator_to_lonlat
from app.features.sites.display import CHANGE_THRESHOLD_DB
from app.features.sites.models import MercatorBounds
from app.features.sites.rendering import encode_png, smoothed_difference
from app.features.sites.slope_echo import ExtOverlay, RawExample, SlopeEcho, SourceRef, Validation

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


def derive_slope_echo(
    site_dir: Path,
    block: SlopeEcho,
    dates: list[dt.date],
    hh: Cube,
    bounds_merc: MercatorBounds,
    blind: Mask | None,
) -> SlopeEcho:
    """Fills what the block leaves empty and the stack can answer. Writes files under ext/."""
    update: dict[str, Any] = {}
    if block.raw_example is None:
        update["raw_example"] = _write_raw_example(site_dir, dates, hh, block.event.date)
    if blind is not None:
        (site_dir / BLIND_FILE).parent.mkdir(parents=True, exist_ok=True)
        (site_dir / BLIND_FILE).write_bytes(encode_png(_mask_rgba(blind, BLIND_RGBA)))
        others = [overlay for overlay in block.overlays if overlay.id != BLIND_ID]
        update["overlays"] = [*others, BLIND_OVERLAY]
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
