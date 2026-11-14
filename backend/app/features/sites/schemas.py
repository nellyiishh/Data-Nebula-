"""Response shapes for the sites API. site.json and stats.json on disk use these same
models, so the pipeline and the API cannot drift apart."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.features.sites.display import (
    BRIGHTER_RGB,
    CHANGE_THRESHOLD_DB,
    DARKER_RGB,
    DB_RANGE,
    RATIO_RANGE_DB,
    WATER_RGBA,
    WATER_THRESHOLD_DB,
    hex_color,
)
from app.features.sites.slope_echo import SlopeEcho

LayerName = Literal["hh", "hv", "rgb", "water"]
LAYER_NAMES: tuple[LayerName, ...] = ("hh", "hv", "rgb", "water")
Polarization = Literal["hh", "hv"]
ChangeType = Literal["water", "crops", "forest", "ice", "deformation", "landslide"]
DataSource = Literal["demo", "nisar"]
LonLat = tuple[float, float]


def layers_for(change_type: ChangeType) -> list[LayerName]:
    """The water mask only means something for a water story."""
    return [name for name in LAYER_NAMES if name != "water" or change_type == "water"]


class DbRange(BaseModel):
    min_db: float
    max_db: float


class Display(BaseModel):
    """How the site's images were drawn: the web legend must use these numbers."""

    hh: DbRange
    hv: DbRange
    ratio: DbRange = Field(description="Blue channel of the colour mix: HH minus HV")
    change_threshold_db: float = Field(description="Change images colour |ΔdB| above this")
    water_threshold_db: float
    darker_color: str
    brighter_color: str
    water_color: str


def current_display() -> Display:
    return Display(
        hh=DbRange(min_db=DB_RANGE["hh"][0], max_db=DB_RANGE["hh"][1]),
        hv=DbRange(min_db=DB_RANGE["hv"][0], max_db=DB_RANGE["hv"][1]),
        ratio=DbRange(min_db=RATIO_RANGE_DB[0], max_db=RATIO_RANGE_DB[1]),
        change_threshold_db=CHANGE_THRESHOLD_DB,
        water_threshold_db=WATER_THRESHOLD_DB,
        darker_color=hex_color(DARKER_RGB),
        brighter_color=hex_color(BRIGHTER_RGB),
        water_color=hex_color(WATER_RGBA),
    )


class PointOfInterest(BaseModel):
    id: str
    name: str
    lon: float
    lat: float
    note: str = ""


class Acquisition(BaseModel):
    """Provenance for one date: which radar product the layers for that date came from."""

    date: dt.date
    granule_id: str | None = Field(description="Source product ID; null for demo data.")
    band: Literal["L", "S", "C"]
    polarizations: list[str]


class SiteSummary(BaseModel):
    id: str
    name: str
    center: LonLat = Field(description="[lon, lat]")
    change_type: ChangeType
    source: DataSource = Field(description="'demo' is synthetic data; the UI must label it.")


class SiteDetail(SiteSummary):
    corners: tuple[LonLat, LonLat, LonLat, LonLat] = Field(
        description="Image corners as [lon, lat]: top-left, top-right, bottom-right, bottom-left."
        " Every layer and date of the site shares these corners."
    )
    layers: list[LayerName]
    acquisitions: list[Acquisition]
    points_of_interest: list[PointOfInterest] = Field(default_factory=list)
    attribution: str
    display: Display = Field(default_factory=current_display)
    slope_echo: SlopeEcho | None = Field(
        default=None, description="Landslide story extras (Slope Echo); null for other sites."
    )

    @computed_field
    @property
    def dates(self) -> list[dt.date]:
        return [acquisition.date for acquisition in self.acquisitions]


class StatsEntry(BaseModel):
    date: dt.date
    water_km2: float
    mean_hh_db: float | None = Field(description="Null when the date has no valid pixels.")
    mean_hv_db: float | None


class SiteStats(BaseModel):
    site_id: str
    water_threshold_db: float = Field(description="HH below this counts as open water.")
    series: list[StatsEntry]


class TimeseriesEntry(BaseModel):
    date: dt.date
    hh_db: float | None = Field(description="Null when the point has no data on this date.")
    hv_db: float | None


class PointTimeseries(BaseModel):
    site_id: str
    lon: float
    lat: float
    series: list[TimeseriesEntry]
