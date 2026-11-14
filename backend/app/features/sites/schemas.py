"""Response shapes for the sites API. site.json and stats.json on disk use these same
models, so the pipeline and the API cannot drift apart."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, computed_field

LayerName = Literal["hh", "hv", "rgb", "water"]
LAYER_NAMES: tuple[LayerName, ...] = ("hh", "hv", "rgb", "water")
Polarization = Literal["hh", "hv"]
ChangeType = Literal["water", "crops", "forest", "ice", "deformation"]
DataSource = Literal["demo", "nisar"]
LonLat = tuple[float, float]


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
