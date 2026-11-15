"""The optional Slope Echo block of a landslide site: event, story text, extra layers,
overlays, rain, exposure and validation.

Field names mirror web/src/features/sites/model/types.ts (SlopeEcho) and web/README.md.
Every file path is relative to the site folder and must stay inside it.
"""

import datetime as dt
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def _is_none(value: object) -> bool:
    return value is None


# Optional fields the web types as "may be absent" (`url?: string`) are left out of the
# JSON when empty, rather than sent as null, so API output equals the static files.
_OMIT_IF_NONE = {"default": None, "exclude_if": _is_none}


def _inside_site_folder(value: str) -> str:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{value!r} must be a relative path inside the site folder")
    return value


SitePath = Annotated[str, AfterValidator(_inside_site_folder)]
StoryKey = Literal["place", "rain", "radar", "tracking", "exposure"]


class SourceRef(BaseModel):
    name: str
    url: str | None = Field(**_OMIT_IF_NONE)


class DualText(BaseModel):
    """The same text in two registers: plain language and research detail."""

    explore: str
    research: str


class NewsImage(BaseModel):
    """Small photo from a news report; `file` lives in web/public/news/ (site-independent)."""

    file: str = Field(pattern=r"^[A-Za-z0-9_-]+\.(jpg|png)$")
    alt: str


class Event(BaseModel):
    date: dt.date
    label: str
    source: SourceRef
    image: NewsImage | None = Field(**_OMIT_IF_NONE)


class Fact(BaseModel):
    text: str
    source: SourceRef | None = Field(**_OMIT_IF_NONE)
    image: NewsImage | None = Field(**_OMIT_IF_NONE)


class ExtFrame(BaseModel):
    """One image of an extra layer: either one date, or a pair of dates (from → to)."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    date: dt.date | None = Field(**_OMIT_IF_NONE)
    date_from: dt.date | None = Field(alias="from", **_OMIT_IF_NONE)
    to: dt.date | None = Field(**_OMIT_IF_NONE)
    file: SitePath

    @model_validator(mode="after")
    def _one_date_or_a_pair(self) -> "ExtFrame":
        is_pair = self.date_from is not None and self.to is not None
        if (self.date is None) == (not is_pair):
            raise ValueError("a frame has either 'date', or both 'from' and 'to'")
        return self


class Legend(BaseModel):
    colors: list[str]
    labels: list[str]


class ExtLayer(BaseModel):
    id: str
    kind: str = Field(description="coherence, displacement or optical (others allowed)")
    title: str
    unit: str
    description: str
    source: SourceRef
    frames: list[ExtFrame]
    legend: Legend | None


class ExtOverlay(BaseModel):
    id: str
    kind: Literal["image", "polygon", "exposure", "outline"]
    title: str
    file: SitePath
    description: str
    source: SourceRef


class Rain(BaseModel):
    file: SitePath = Field(description='File with {"series": [{"date", "mm"}]}')
    source: SourceRef
    note: str


class CatalogEntry(BaseModel):
    date: dt.date
    type: str
    name: str
    source: SourceRef


class RawExample(BaseModel):
    linear: SitePath
    db: SitePath
    date: dt.date


class Exposure(BaseModel):
    radius_km: float
    buildings: int
    roads_km: float
    nearest_settlement: str
    distance_km: float
    method: str
    source: SourceRef


class Validation(BaseModel):
    threshold_db: float
    pair: tuple[dt.date, dt.date]
    changed_inside_pct: float
    changed_outside_pct: float
    method: str


class SlopeEcho(BaseModel):
    region: str
    country: str
    event: Event
    facts: list[Fact]
    story: dict[StoryKey, DualText]
    layers: list[ExtLayer]
    overlays: list[ExtOverlay]
    rain: Rain | None
    catalog: list[CatalogEntry] | None = None
    raw_example: RawExample | None = None
    point_extras: dict[str, SitePath] = Field(
        description="Point-of-interest id → file with per-pair coherence and LOS (cm)"
    )
    exposure: Exposure | None
    validation: Validation | None
    limitations: list[str]

    def referenced_files(self) -> list[str]:
        files = [frame.file for layer in self.layers for frame in layer.frames]
        files += [overlay.file for overlay in self.overlays]
        files += list(self.point_extras.values())
        if self.rain:
            files.append(self.rain.file)
        if self.raw_example:
            files += [self.raw_example.linear, self.raw_example.db]
        return files
