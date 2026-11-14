import numpy as np

from app.features.sites.rendering import change_rgba


def _speckled(base_db: float, rng: np.random.Generator, looks: int = 8) -> np.ndarray:
    linear = 10 ** (base_db / 10) * rng.gamma(looks, 1 / looks, size=(200, 200))
    return 10 * np.log10(linear)


def test_speckle_alone_is_not_reported_as_change() -> None:
    # Two images of the same unchanged surface differ only by radar speckle.
    rng = np.random.default_rng(0)
    before, after = _speckled(-9.0, rng), _speckled(-9.0, rng)

    coloured = change_rgba(before, after)[..., 3] > 0

    assert coloured.mean() < 0.01


def test_real_change_survives_the_smoothing() -> None:
    rng = np.random.default_rng(1)
    before = _speckled(-9.0, rng)
    after = _speckled(-9.0, rng)
    after[50:150, 50:150] -= 12.0  # a block that became water

    alpha = change_rgba(before, after)[..., 3]

    assert (alpha[60:140, 60:140] > 0).mean() > 0.99
