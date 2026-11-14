"""Reads pipeline output. Layout per site (written by pipeline/writer.py):

<data_dir>/<site_id>/site.json            SiteDetail
<data_dir>/<site_id>/stats.json           SiteStats
<data_dir>/<site_id>/stack.npz            hh, hv, bounds_merc, dates
<data_dir>/<site_id>/layers/<layer>/<YYYY-MM-DD>.png
"""

import datetime as dt
import functools
import re
from pathlib import Path, PurePosixPath

import numpy as np

from app.features.sites.models import SiteStack
from app.features.sites.schemas import LayerName, SiteDetail, SiteStats

SITE_FILE = "site.json"
STATS_FILE = "stats.json"
STACK_FILE = "stack.npz"
LAYERS_DIR = "layers"
EXT_DIR = "ext"
# Only these folders of a site are served as plain files (never stack.npz or site.json).
SERVED_DIRS = (EXT_DIR, LAYERS_DIR)
SITE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"
_SITE_ID = re.compile(SITE_ID_PATTERN)


class SiteRepository:
    """Read-only access to prepared sites. Never writes; the pipeline owns the files."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def list_sites(self) -> list[SiteDetail]:
        if not self._data_dir.is_dir():
            return []
        sites = (self.get_site(path.name) for path in sorted(self._data_dir.iterdir()))
        return [site for site in sites if site is not None]

    def get_site(self, site_id: str) -> SiteDetail | None:
        path = self._file(site_id, SITE_FILE)
        return SiteDetail.model_validate_json(path.read_text()) if path else None

    def get_stats(self, site_id: str) -> SiteStats | None:
        path = self._file(site_id, STATS_FILE)
        return SiteStats.model_validate_json(path.read_text()) if path else None

    def layer_path(self, site_id: str, layer: LayerName, date: dt.date) -> Path | None:
        return self._file(site_id, f"{LAYERS_DIR}/{layer}/{date.isoformat()}.png")

    def site_file(self, site_id: str, relative: str) -> Path | None:
        """A file under ext/ or layers/ of the site, or None. Refuses anything that would
        resolve outside the site folder (.., symlinks)."""
        parts = PurePosixPath(relative).parts
        if len(parts) < 2 or parts[0] not in SERVED_DIRS or ".." in parts:
            return None
        path = self._file(site_id, relative)
        if path is None:
            return None
        site_dir = (self._data_dir / site_id).resolve()
        return path if path.resolve().is_relative_to(site_dir) else None

    def get_stack(self, site_id: str) -> SiteStack | None:
        path = self._file(site_id, STACK_FILE)
        return _load_stack(str(path), path.stat().st_mtime_ns) if path else None

    def _file(self, site_id: str, relative: str) -> Path | None:
        # The ID check keeps a crafted site_id from reading outside data_dir.
        if not _SITE_ID.match(site_id):
            return None
        path = self._data_dir / site_id / relative
        return path if path.is_file() else None


# Cache owner: SiteRepository.get_stack. No TTL: entries are keyed on the file's mtime,
# so re-running the pipeline is picked up on the next request; restart clears the rest.
@functools.lru_cache(maxsize=8)
def _load_stack(path: str, mtime_ns: int) -> SiteStack:
    del mtime_ns  # only part of the cache key
    with np.load(path) as npz:
        xmin, ymin, xmax, ymax = (float(v) for v in npz["bounds_merc"])
        return SiteStack(
            hh=npz["hh"],
            hv=npz["hv"],
            bounds_merc=(xmin, ymin, xmax, ymax),
            dates=tuple(dt.date.fromisoformat(str(d)) for d in npz["dates"]),
        )
