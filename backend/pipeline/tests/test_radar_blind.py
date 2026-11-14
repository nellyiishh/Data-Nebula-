"""Layover / shadow from terrain slope and the radar's look direction."""

import numpy as np
import pytest

from pipeline.radar_blind import blind_mask

# 30 m ground pixels at the equator: Mercator metres equal ground metres there.
BOUNDS = (0.0, 0.0, 3000.0, 3000.0)
SHAPE = (100, 100)
# Radar looks from the east (the sensor is east of the ground), 35° incidence.
LOS_EAST, LOS_NORTH, INCIDENCE = 1.0, 0.0, 35.0


def _plane(slope_deg: float, rises_toward: str) -> np.ndarray:
    """Ground that rises at slope_deg toward the east or the west."""
    cols = np.arange(SHAPE[1]) * 30.0
    height = np.tan(np.radians(slope_deg)) * (cols if rises_toward == "east" else -cols)
    return np.broadcast_to(height, SHAPE).astype("f8")


def _mask(dem: np.ndarray) -> np.ndarray:
    return blind_mask(dem, BOUNDS, LOS_EAST, LOS_NORTH, INCIDENCE)


def test_flat_ground_is_visible() -> None:
    assert not _mask(np.zeros(SHAPE)).any()


def test_gentle_slopes_are_visible() -> None:
    assert not _mask(_plane(20, "east")).any()
    assert not _mask(_plane(20, "west")).any()


def test_slope_facing_the_radar_steeper_than_incidence_is_layover() -> None:
    # Rises toward the sensor at 45° > 35° incidence: the top echoes before the foot.
    assert _mask(_plane(45, "east"))[5:-5, 5:-5].all()


def test_slope_facing_away_steeper_than_grazing_is_shadow() -> None:
    # Falls away from the sensor at 60° > 90° - 35° = 55°: the beam never reaches it.
    assert _mask(_plane(60, "west"))[5:-5, 5:-5].all()


def test_missing_terrain_is_not_called_blind() -> None:
    dem = _plane(45, "east").copy()
    dem[:, :50] = np.nan

    mask = _mask(dem)

    assert not mask[:, :49].any()


def test_look_direction_must_have_a_horizontal_part() -> None:
    with pytest.raises(ValueError, match="horizontal"):
        blind_mask(np.zeros(SHAPE), BOUNDS, 0.0, 0.0, INCIDENCE)
