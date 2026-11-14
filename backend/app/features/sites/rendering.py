"""Turns dB arrays into RGBA images. Used offline by the pipeline (per-date layers) and
online by the change endpoint, so both look identical."""

import io

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from app.features.sites.display import (
    BRIGHTER_RGB,
    CHANGE_THRESHOLD_DB,
    DARKER_RGB,
    DB_RANGE,
    RATIO_RANGE_DB,
    WATER_RGBA,
    WATER_THRESHOLD_DB,
)
from app.features.sites.schemas import Polarization

FloatArray = NDArray[np.floating]
RGBA = NDArray[np.uint8]


def _scale(db: FloatArray, low: float, high: float) -> NDArray[np.uint8]:
    scaled = (np.nan_to_num(db, nan=low) - low) / (high - low)
    return (np.clip(scaled, 0.0, 1.0) * 255).astype(np.uint8)


def _opaque_where(mask: NDArray[np.bool_]) -> NDArray[np.uint8]:
    return np.where(mask, 255, 0).astype(np.uint8)


def grayscale_rgba(db: FloatArray, polarization: Polarization) -> RGBA:
    gray = _scale(db, *DB_RANGE[polarization])
    return np.dstack([gray, gray, gray, _opaque_where(np.isfinite(db))])


def false_colour_rgba(hh: FloatArray, hv: FloatArray) -> RGBA:
    """Red = HH, green = HV (volume scattering: vegetation), blue = HH/HV ratio."""
    red = _scale(hh, *DB_RANGE["hh"])
    green = _scale(hv, *DB_RANGE["hv"])
    blue = _scale(hh - hv, *RATIO_RANGE_DB)
    return np.dstack([red, green, blue, _opaque_where(np.isfinite(hh) & np.isfinite(hv))])


def water_mask(hh: FloatArray, threshold_db: float = WATER_THRESHOLD_DB) -> NDArray[np.bool_]:
    finite = np.isfinite(hh)
    return finite & (np.where(finite, hh, np.inf) < threshold_db)


def water_rgba(hh: FloatArray) -> RGBA:
    rgba = np.zeros((*hh.shape, 4), dtype=np.uint8)
    rgba[water_mask(hh)] = WATER_RGBA
    return rgba


def _box_mean_3x3(values: FloatArray) -> FloatArray:
    """Mean of each pixel's 3x3 neighbourhood, ignoring NaN."""
    rows, cols = values.shape
    padded = np.pad(values, 1, constant_values=np.nan)
    windows = np.stack([padded[r : r + rows, c : c + cols] for r in range(3) for c in range(3)])
    finite = np.isfinite(windows)
    count = finite.sum(axis=0)
    total = np.where(finite, windows, 0.0).sum(axis=0)
    return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def smoothed_difference(before: FloatArray, after: FloatArray) -> FloatArray:
    """after - before in dB, averaged over 3x3 pixels; NaN where either date has no data.

    Radar speckle alone moves single pixels by more than 3 dB between dates, so change is
    always judged on this smoothed difference (change images and validation alike)."""
    diff = after - before
    return np.where(np.isfinite(diff), _box_mean_3x3(diff), np.nan)


def change_rgba(
    before: FloatArray, after: FloatArray, threshold_db: float = CHANGE_THRESHOLD_DB
) -> RGBA:
    """Colours only pixels whose smoothed backscatter moved by at least threshold_db."""
    diff = smoothed_difference(before, after)
    finite = np.isfinite(diff)
    delta = np.where(finite, diff, 0.0)
    darker = finite & (delta <= -threshold_db)
    brighter = finite & (delta >= threshold_db)
    strength = np.clip(np.abs(delta) / (3 * threshold_db), 0.4, 1.0)

    rgba = np.zeros((*diff.shape, 4), dtype=np.uint8)
    rgba[darker, :3] = DARKER_RGB
    rgba[brighter, :3] = BRIGHTER_RGB
    rgba[..., 3] = np.where(darker | brighter, strength * 255, 0).astype(np.uint8)
    return rgba


def encode_png(rgba: RGBA) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(rgba).save(buffer, format="PNG")
    return buffer.getvalue()
