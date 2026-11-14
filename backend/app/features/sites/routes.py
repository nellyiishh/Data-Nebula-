import datetime as dt
import mimetypes
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query
from fastapi.responses import FileResponse, Response

from app.core.errors import ErrorResponse
from app.features.sites.dependencies import SiteServiceDep
from app.features.sites.repository import SITE_ID_PATTERN
from app.features.sites.schemas import (
    ChangeStats,
    LayerName,
    PointTimeseries,
    Polarization,
    SiteDetail,
    SiteStats,
    SiteSummary,
)

router = APIRouter(prefix="/sites", tags=["sites"])

SiteId = Annotated[str, Path(pattern=SITE_ID_PATTERN, description="Site ID, e.g. demo-reservoir")]
_PNG = {"content": {"image/png": {}}, "description": "Transparent PNG over the site corners."}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Unknown site, date or layer."}
}
_INVALID: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Invalid parameters."}
}
_ERRORS = {**_NOT_FOUND, **_INVALID}
_IMAGE_CACHE = {"Cache-Control": "public, max-age=3600"}
# GeoJSON is not in every platform's mimetypes table.
_EXTRA_TYPES = {".geojson": "application/geo+json"}


@router.get(
    "",
    summary="List prepared sites",
    description="Every study area the pipeline has prepared. Empty until a site is built.",
    response_model=list[SiteSummary],
)
def list_sites(service: SiteServiceDep) -> list[SiteSummary]:
    return service.list_sites()


@router.get(
    "/{site_id}",
    summary="Get one site",
    description="Corners, dates, layers, provenance and points of interest for one site.",
    response_model=SiteDetail,
    responses=_ERRORS,
)
def get_site(site_id: SiteId, service: SiteServiceDep) -> SiteDetail:
    return service.get_site(site_id)


@router.get(
    "/{site_id}/stats",
    summary="Site statistics per date",
    description="Open-water area and mean backscatter for each acquisition date.",
    response_model=SiteStats,
    responses=_ERRORS,
)
def get_stats(site_id: SiteId, service: SiteServiceDep) -> SiteStats:
    return service.get_stats(site_id)


@router.get(
    "/{site_id}/layers/{layer}/{date}.png",
    summary="Layer image for one date",
    description="hh/hv: grayscale backscatter · rgb: HH/HV/ratio colour mix · water: water mask.",
    response_class=FileResponse,
    responses={200: _PNG, **_ERRORS},
)
def get_layer(
    site_id: SiteId, layer: LayerName, date: dt.date, service: SiteServiceDep
) -> FileResponse:
    path = service.layer_path(site_id, layer, date)
    return FileResponse(path, media_type="image/png", headers=_IMAGE_CACHE)


@router.get(
    "/{site_id}/change.png",
    summary="Change between two dates",
    description="Red: surface got darker to radar (e.g. new water, harvest). "
    "Blue: got brighter (e.g. water retreat, crop growth). Unchanged pixels are transparent.",
    response_class=Response,
    responses={200: _PNG, **_ERRORS},
)
def get_change(
    site_id: SiteId,
    service: SiteServiceDep,
    date_from: Annotated[dt.date, Query(alias="from", description="Earlier date")],
    date_to: Annotated[dt.date, Query(alias="to", description="Later date")],
    polarization: Polarization = "hh",
) -> Response:
    png = service.change_png(site_id, date_from, date_to, polarization)
    return Response(content=png, media_type="image/png", headers=_IMAGE_CACHE)


@router.get(
    "/{site_id}/change-stats",
    summary="Change between two dates as numbers",
    description="The same comparison as change.png, counted: share and ground area of pixels "
    "that got darker or brighter by at least the threshold, and the mean change in dB. "
    "A changed pixel is a reason to look, not proof of a landslide.",
    response_model=ChangeStats,
    responses=_ERRORS,
)
def get_change_stats(
    site_id: SiteId,
    service: SiteServiceDep,
    date_from: Annotated[dt.date, Query(alias="from", description="Earlier date")],
    date_to: Annotated[dt.date, Query(alias="to", description="Later date")],
    polarization: Polarization = "hh",
) -> ChangeStats:
    return service.change_stats(site_id, date_from, date_to, polarization)


@router.get(
    "/{site_id}/timeseries",
    summary="Backscatter over time at a point",
    description="HH and HV in dB at a clicked point (3x3 pixel average) for every date.",
    response_model=PointTimeseries,
    responses=_ERRORS,
)
def get_timeseries(
    site_id: SiteId,
    service: SiteServiceDep,
    lon: Annotated[float, Query(ge=-180, le=180)],
    lat: Annotated[float, Query(ge=-85, le=85)],
) -> PointTimeseries:
    return service.point_timeseries(site_id, lon, lat)


@router.get(
    "/{site_id}/files/{file_path:path}",
    summary="A file of the site's story",
    description="Files the slope_echo block points at (ext/…), plus layer images (layers/…). "
    "Paths are the same as in the static export, relative to the site folder.",
    response_class=FileResponse,
    responses=_ERRORS,
)
def get_site_file(site_id: SiteId, file_path: str, service: SiteServiceDep) -> FileResponse:
    path = service.site_file(site_id, file_path)
    media_type = _EXTRA_TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0]
    return FileResponse(path, media_type=media_type or "application/octet-stream")
