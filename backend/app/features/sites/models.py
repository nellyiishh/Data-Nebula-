import datetime as dt
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

MercatorBounds = tuple[float, float, float, float]  # xmin, ymin, xmax, ymax in EPSG:3857 metres


def pixel_at(
    bounds_merc: MercatorBounds, shape: tuple[int, int], x: float, y: float
) -> tuple[int, int] | None:
    """(row, col) of the grid pixel containing Mercator point (x, y), or None if outside."""
    xmin, ymin, xmax, ymax = bounds_merc
    if not (xmin <= x <= xmax and ymin <= y <= ymax):
        return None
    rows, cols = shape
    col = min(int((x - xmin) / (xmax - xmin) * cols), cols - 1)
    row = min(int((ymax - y) / (ymax - ymin) * rows), rows - 1)
    return row, col


@dataclass(frozen=True)
class SiteStack:
    """Backscatter cubes for one site: shape (dates, rows, cols), values in dB, NaN = no data.
    Row 0 is the northern edge."""

    hh: NDArray[np.float32]
    hv: NDArray[np.float32]
    bounds_merc: MercatorBounds
    dates: tuple[dt.date, ...]

    def index_of(self, date: dt.date) -> int | None:
        return self.dates.index(date) if date in self.dates else None

    def pixel_at(self, x: float, y: float) -> tuple[int, int] | None:
        """(row, col) of the pixel containing Mercator point (x, y), or None if outside."""
        _, rows, cols = self.hh.shape
        return pixel_at(self.bounds_merc, (rows, cols), x, y)
