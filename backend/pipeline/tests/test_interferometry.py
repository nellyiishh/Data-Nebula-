import numpy as np
import pytest

from pipeline.interferometry import MIN_COHERENCE, los_cm, prepare_pair_layers

WAVELENGTH = 0.2384  # NISAR L-band, metres


def test_phase_converts_to_centimetres_toward_the_satellite_positive() -> None:
    # MintPy's convention for NISAR: range change = -phase * wavelength / (4π).
    assert los_cm(np.array([np.pi]), WAVELENGTH)[0] == pytest.approx(-100 * WAVELENGTH / 4)
    assert los_cm(np.array([-np.pi]), WAVELENGTH)[0] == pytest.approx(100 * WAVELENGTH / 4)


def test_each_pair_is_referenced_to_the_site_median() -> None:
    phase = np.full((1, 10, 10), 5.0)
    phase[0, 0, 0] = 5.0 + np.pi  # one pixel moved
    coherence = np.full((1, 10, 10), 0.9)

    _, los = prepare_pair_layers(coherence, phase, WAVELENGTH)

    assert los[0, 5, 5] == pytest.approx(0.0)
    assert los[0, 0, 0] == pytest.approx(-100 * WAVELENGTH / 4)


def test_low_coherence_hides_motion_but_keeps_coherence() -> None:
    phase = np.zeros((1, 4, 4))
    coherence = np.full((1, 4, 4), 0.9)
    coherence[0, 0, 0] = MIN_COHERENCE / 2

    coh, los = prepare_pair_layers(coherence, phase, WAVELENGTH)

    assert np.isnan(los[0, 0, 0]) and not np.isnan(los[0, 1, 1])
    assert coh[0, 0, 0] == pytest.approx(MIN_COHERENCE / 2)
