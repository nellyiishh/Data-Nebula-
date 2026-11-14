import datetime as dt
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.core.errors import ErrorCode, NotFoundError, UnprocessableError
from app.core.geo import lonlat_to_mercator
from app.features.sites.display import CHANGE_THRESHOLD_DB
from app.features.sites.models import SiteStack, pixel_area_km2_by_row
from app.features.sites.rendering import change_masks, change_rgba, encode_png
from app.features.sites.repository import SiteRepository
from app.features.sites.schemas import (
    ChangeStats,
    LayerName,
    PointTimeseries,
    Polarization,
    SiteDetail,
    SiteStats,
    SiteSummary,
    TimeseriesEntry,
)

# Radius (in pixels) averaged around a clicked point; one pixel alone is mostly speckle.
POINT_WINDOW_RADIUS = 1


class SiteService:
    def __init__(self, repository: SiteRepository) -> None:
        self._repository = repository

    def list_sites(self) -> list[SiteSummary]:
        return [_summary(site) for site in self._repository.list_sites()]

    def get_site(self, site_id: str) -> SiteDetail:
        site = self._repository.get_site(site_id)
        if site is None:
            raise _site_not_found(site_id)
        return site

    def get_stats(self, site_id: str) -> SiteStats:
        stats = self._repository.get_stats(site_id)
        if stats is None:
            raise _site_not_found(site_id)
        return stats

    def layer_path(self, site_id: str, layer: LayerName, date: dt.date) -> Path:
        _require_date(self.get_site(site_id), date)
        path = self._repository.layer_path(site_id, layer, date)
        if path is None:
            raise NotFoundError(
                ErrorCode.LAYER_NOT_FOUND,
                f"Layer '{layer}' was not prepared for {date.isoformat()}.",
                {"site_id": site_id, "layer": layer, "date": date.isoformat()},
            )
        return path

    def site_file(self, site_id: str, relative: str) -> Path:
        self.get_site(site_id)
        path = self._repository.site_file(site_id, relative)
        if path is None:
            raise NotFoundError(
                ErrorCode.FILE_NOT_FOUND,
                f"No file '{relative}' for site '{site_id}'.",
                {"site_id": site_id, "path": relative},
            )
        return path

    def change_png(
        self, site_id: str, date_from: dt.date, date_to: dt.date, polarization: Polarization
    ) -> bytes:
        _, before, after = self._pair(site_id, date_from, date_to, polarization)
        return encode_png(change_rgba(before, after))

    def change_stats(
        self, site_id: str, date_from: dt.date, date_to: dt.date, polarization: Polarization
    ) -> ChangeStats:
        stack, before, after = self._pair(site_id, date_from, date_to, polarization)
        diff, darker, brighter = change_masks(before, after)
        valid = np.isfinite(diff)
        n_valid = int(valid.sum())
        row_area = pixel_area_km2_by_row(diff.shape, stack.bounds_merc)

        def pct(mask: NDArray[np.bool_]) -> float:
            return round(100.0 * int(mask.sum()) / n_valid, 1) if n_valid else 0.0

        def km2(mask: NDArray[np.bool_]) -> float:
            return round(float((mask.sum(axis=1) * row_area).sum()), 4)

        return ChangeStats(
            site_id=site_id,
            date_from=date_from,
            to=date_to,
            polarization=polarization,
            threshold_db=CHANGE_THRESHOLD_DB,
            valid_pct=round(100.0 * n_valid / valid.size, 1),
            darker_pct=pct(darker),
            brighter_pct=pct(brighter),
            changed_pct=pct(darker | brighter),
            darker_km2=km2(darker),
            brighter_km2=km2(brighter),
            changed_km2=km2(darker | brighter),
            mean_delta_db=round(float(diff[valid].mean()), 2) if n_valid else None,
        )

    def _pair(
        self, site_id: str, date_from: dt.date, date_to: dt.date, polarization: Polarization
    ) -> tuple[SiteStack, NDArray[np.float32], NDArray[np.float32]]:
        """The stack and its two layers for a pair of dates; 404 if either date is unknown."""
        site = self.get_site(site_id)
        _require_date(site, date_from)
        _require_date(site, date_to)
        stack = self._stack(site_id)
        cube = stack.hh if polarization == "hh" else stack.hv
        return stack, cube[stack.dates.index(date_from)], cube[stack.dates.index(date_to)]

    def point_timeseries(self, site_id: str, lon: float, lat: float) -> PointTimeseries:
        stack = self._stack(site_id)
        pixel = stack.pixel_at(*lonlat_to_mercator(lon, lat))
        if pixel is None:
            raise UnprocessableError(
                ErrorCode.POINT_OUTSIDE_SITE,
                "That point is outside the area prepared for this site.",
                {"site_id": site_id, "lon": lon, "lat": lat},
            )
        rows, cols = _window(pixel, stack)
        series = [
            TimeseriesEntry(
                date=date,
                hh_db=_mean_db(stack.hh[t, rows, cols]),
                hv_db=_mean_db(stack.hv[t, rows, cols]),
            )
            for t, date in enumerate(stack.dates)
        ]
        return PointTimeseries(site_id=site_id, lon=lon, lat=lat, series=series)

    def _stack(self, site_id: str) -> SiteStack:
        stack = self._repository.get_stack(site_id)
        if stack is None:
            raise _site_not_found(site_id)
        return stack


def _summary(site: SiteDetail) -> SiteSummary:
    return SiteSummary.model_validate(site.model_dump(include=set(SiteSummary.model_fields)))


def _site_not_found(site_id: str) -> NotFoundError:
    return NotFoundError(
        ErrorCode.SITE_NOT_FOUND, f"No prepared site '{site_id}'.", {"site_id": site_id}
    )


def _require_date(site: SiteDetail, date: dt.date) -> None:
    if date not in site.dates:
        raise NotFoundError(
            ErrorCode.DATE_NOT_FOUND,
            f"No acquisition on {date.isoformat()} for site '{site.id}'.",
            {"site_id": site.id, "date": date.isoformat(), "available": site.dates},
        )


def _window(pixel: tuple[int, int], stack: SiteStack) -> tuple[slice, slice]:
    row, col = pixel
    _, height, width = stack.hh.shape
    r = POINT_WINDOW_RADIUS
    return (
        slice(max(row - r, 0), min(row + r + 1, height)),
        slice(max(col - r, 0), min(col + r + 1, width)),
    )


def _mean_db(values_db: NDArray[np.floating]) -> float | None:
    """Average in linear power (the physically meaningful mean), then back to dB."""
    finite = values_db[np.isfinite(values_db)]
    if finite.size == 0:
        return None
    return round(float(10 * np.log10(np.mean(10 ** (finite / 10)))), 2)
