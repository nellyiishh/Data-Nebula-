"""Exports prepared sites as website data into data/web/ (repo root).

data/web/ holds only backend output, in the exact layout the future Cloud Storage bucket
gets. The web app serves it at /data (web/vite.config.ts, plugin `siteData`), falling back
file by file to the web team's fake data in web/public/data/, which this never touches.

TODO(server-backend): temporary. Once the API runs on Cloud Run with data in Cloud Storage,
the web reads from the API and this export is retired (see the plan, section 0).

    uv run python -m pipeline.export_static                    # every prepared site
    uv run python -m pipeline.export_static --site togus-bulak  # only some

The web reads these files when VITE_API_URL is empty (the default deploy), so this is what
judges see unless the API is hosted. Layout (web/src/core/api/client.ts), under data/web/:

    sites.json                          GET /sites   (merged: earlier exported sites kept)
    sites/{id}.json                     GET /sites/{id}
    sites/{id}/layers/{layer}/{date}.png
    sites/{id}/change/{from}_{to}.png   GET …/change.png, every consecutive pair (HH)
    sites/{id}/points/{poi_id}.json     GET …/timeseries at each point of interest
    sites/{id}/stats.json               GET …/stats
    sites/{id}/ext/…                    the slope_echo files, copied
"""

import argparse
import json
import shutil
from itertools import pairwise
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, Settings
from app.core.logging import configure_logging, get_logger
from app.features.sites.repository import EXT_DIR, LAYERS_DIR, SiteRepository
from app.features.sites.schemas import SiteSummary
from app.features.sites.service import SiteService

SITE_DATA_DIR = REPO_ROOT / "data" / "web"
log = get_logger("export")


def export_static(data_dir: Path, out_dir: Path, site_ids: list[str] | None = None) -> list[str]:
    """Writes the chosen sites (default: all) and returns their ids."""
    service = SiteService(SiteRepository(data_dir))
    available = {site.id: site for site in service.list_sites()}
    chosen = site_ids if site_ids is not None else list(available)
    unknown = [site_id for site_id in chosen if site_id not in available]
    if unknown:
        raise ValueError(f"No prepared site(s) {unknown} in {data_dir}")

    for site_id in chosen:
        _export_site(service, data_dir / site_id, out_dir, site_id)
    _merge_index(out_dir / "sites.json", [available[site_id] for site_id in chosen])
    return chosen


def _export_site(service: SiteService, source_dir: Path, out_dir: Path, site_id: str) -> None:
    site = service.get_site(site_id)
    target = out_dir / "sites" / site_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    (out_dir / "sites" / f"{site_id}.json").write_text(site.model_dump_json(indent=2))
    (target / "stats.json").write_text(service.get_stats(site_id).model_dump_json(indent=2))
    shutil.copytree(source_dir / LAYERS_DIR, target / LAYERS_DIR)
    if (source_dir / EXT_DIR).is_dir():
        shutil.copytree(source_dir / EXT_DIR, target / EXT_DIR)

    change_dir = target / "change"
    change_dir.mkdir()
    for before, after in pairwise(site.dates):
        png = service.change_png(site_id, before, after, "hh")
        (change_dir / f"{before.isoformat()}_{after.isoformat()}.png").write_bytes(png)

    points_dir = target / "points"
    points_dir.mkdir()
    for point in site.points_of_interest:
        series = service.point_timeseries(site_id, point.lon, point.lat)
        (points_dir / f"{point.id}.json").write_text(series.model_dump_json(indent=2))
    log.info("Exported %s → %s", site_id, target)


def _merge_index(path: Path, exported: list[SiteSummary]) -> None:
    """Replaces exported sites in sites.json and keeps sites exported earlier."""
    entries: list[dict[str, Any]] = json.loads(path.read_text()) if path.is_file() else []
    fresh = {site.id: site.model_dump(mode="json") for site in exported}
    merged = [fresh.pop(entry["id"], entry) for entry in entries]
    merged += fresh.values()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export prepared sites into data/web/.")
    parser.add_argument("--site", action="append", dest="sites", help="site id (repeatable)")
    parser.add_argument("--out", type=Path, default=SITE_DATA_DIR, help="website data folder")
    args = parser.parse_args()
    configure_logging()
    exported = export_static(Settings().data_dir, args.out, args.sites)
    log.info("Exported %d site(s) to %s", len(exported), args.out)


if __name__ == "__main__":
    main()
