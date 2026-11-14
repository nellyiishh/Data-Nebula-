"""Interferogram pairs → coherence and line-of-sight motion on the site grid.

Sign: MintPy's convention for NISAR, range change = -phase x wavelength / (4π), so positive
centimetres mean the ground moved TOWARD the satellite and negative ones AWAY from it.
"""

import datetime as dt
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.floating]

# Below this the phase is mostly noise: motion is left blank there, coherence is still shown.
MIN_COHERENCE = 0.3


def los_cm(phase_rad: Array, wavelength_m: float) -> Array:
    return -phase_rad * wavelength_m / (4 * np.pi) * 100.0


def prepare_pair_layers(
    coherence: Array, phase_rad: Array, wavelength_m: float
) -> tuple[Array, Array]:
    """coherence, phase: (pairs, rows, cols) on the site grid. Returns (coherence, los_cm).

    Unwrapped phase has an arbitrary offset per pair, so each pair is referenced to the
    median over the site: we assume most of a few-km site did not move in 12 days.
    """
    los = los_cm(phase_rad, wavelength_m)
    los = np.where(coherence >= MIN_COHERENCE, los, np.nan)
    for i in range(los.shape[0]):
        if np.isfinite(los[i]).any():
            los[i] -= np.nanmedian(los[i])
    return coherence, los


@dataclass(frozen=True)
class PairLayers:
    """Consecutive pairs on the site grid, ready to draw. los_cm is per pair, not summed."""

    pairs: list[tuple[dt.date, dt.date]]
    coherence: Array  # (pairs, rows, cols), 0..1, NaN = no data
    los_cm: Array  # (pairs, rows, cols), + toward the satellite, NaN = blank
