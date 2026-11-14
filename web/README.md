# web — TRACE / Slope Echo frontend

*Rain loads it. Radar hears it. People live below it.* React + Vite + TypeScript + MapLibre GL.
Rules live in [`../CLAUDE.md`](../CLAUDE.md); what is real vs demo is in [`../docs/wiring-notes.md`](../docs/wiring-notes.md).

## Run

```bash
cd web
npm install
npm run dev          # http://localhost:5173 (needs a browser with WebGL2 for the maps)
```

Before pushing: `npm run lint && npm run build` (both must pass with zero warnings).

## Two sections (tabs in the top-right corner)

| Section | URL | For |
|---|---|---|
| **For everyone** | `/?section=everyone` | Curious people: one place, four ways to look (before/after, time-lapse, what changed, photo vs radar), three numbers, how radar works, warning signs. `src/app/EveryonePage.tsx`, texts in `src/features/everyone/content.ts` |
| **For specialists** | `/` (default) | Everything below: the story, the workspace and the report, always at full detail. "Open workspace" sits in the bar under the header |

Logo: `public/brand/trace-mark.png` (cut from the team logo). Hero background: `public/brand/hero-mountains.jpg`
(1672 px, + `hero-mountains-1280.jpg` for small screens), a mountain landscape supplied by the team: a trail over
grassy ridges, layered valleys and a cloudy blue-grey sky.

## Two ways in

| Mode | URL | For |
|---|---|---|
| **Story** | `/` | Presentation and the public: 9 screens, one scroll |
| **TRACE workspace** | `/?view=app` | Analysis: one screen, five investigation steps |
| Report | `/?view=brief` | Printable PDF |

Both use the same state (`src/app/useExplorerState.ts`) and the same parts (`src/app/ExplorerParts.tsx`), so a
link opens the same layer, date, point and overlays in either mode.

### TRACE workspace (`src/app/Workspace.tsx`)

```
┌ top: TRACE · search (area, place, "lat, lon") · current date · DEMO · Story ──────────────────┐
├ steps: 1 Explore map → 2 Change analysis → 3 Rainfall context → 4 Infrastructure → 5 Report ──┤
├ left: map layers ──────┬ centre: map ─────────────────────┬ right: selected area (per step) ──┤
├ bottom: observation timeline — Play, rain bars, NISAR passes (click to jump), event line ──────┘
```

On screens under 1000 px the side panels become drawers (Layers / Details buttons).
Design system: "Dark Earth Intelligence" palette in `src/core/theme/tokens.css`, Inter + IBM Plex Mono
(mono for dates, coordinates, IDs). Red is only for "radar got darker" and errors, never a generic danger colour.

## The page (9 screens, one scroll)

| # | Screen | Where |
|---|---|---|
| 01 | Hero: Earth map + mission | `src/app/SitePage.tsx` |
| 02 | Explore: pick a place, event and facts with sources | `src/app/SitePage.tsx` |
| 03 | Earth Time Machine: Play through every NISAR pass (HH/HV, change, coherence, LOS), rain + passes timeline, point chart, **Listen to Earth**, 3D terrain, compare two dates, contrast stretch (Research) | `src/app/TimeMachine.tsx` |
| 04 | Radar Vision: camera ↔ radar slider, what radar is/isn't, band guide (X/C/S/L), raw vs stretched | `src/app/RadarVision.tsx` |
| 05 | Rainfall connection: IMERG bars + 30-day totals | `src/features/timeline/` |
| 06 | Earth impact: buildings/roads, registered events, report button | `src/features/exposure/` |
| 07 | Global stories: same template for every region | `src/app/SitePage.tsx` |
| 08 | Investigation report: preview + printable PDF | `src/features/report/` |
| 09 | Data & science: validation, limits, methods, datasets, AI use | `src/features/story/DataLimits.tsx` |

- **One level of detail** for specialists: the former Explore and Research modes were merged; every screen shows the detailed text. Plain-language versions live in the "For everyone" section.
- **The URL keeps the view** (`?site, section, layer, f, cmp, a, b, ov, pt, op, t3d, ct`), so a link opens the same frame.
- **Field brief**: `?site=<id>&view=brief` → printable page (browser Print → Save as PDF).

## Where data comes from

`src/core/api/client.ts` is the only file that builds URLs.

- **`VITE_API_URL` empty (default)** → static files at `/data`: the real backend output in
  `../data/web/` (written by `python -m pipeline.export_static`). The `siteData` plugin in
  `vite.config.ts` serves it in dev and copies it into `npm run build`. There is no demo/fake site any more.
- **`VITE_API_URL=http://localhost:8000`** in `web/.env.local` → the FastAPI backend.

Static layout = the backend contract (`contracts/openapi.json`) + an optional extension:

```
public/data/
  sites.json                              GET /api/v1/sites
  sites/{id}.json                         GET /api/v1/sites/{id}   (+ optional "slope_echo" block)
  sites/{id}/layers/{hh|hv|rgb}/{date}.png
  sites/{id}/change/{from}_{to}.png       GET …/change.png?from=&to=   (consecutive passes)
  sites/{id}/points/{poi_id}.json         GET …/timeseries?lon=&lat=   (pre-computed per point)
  sites/{id}/ext/…                        files referenced by slope_echo (static only for now)
```

### The `slope_echo` block (what the data team fills in)

All paths are relative to `sites/{id}/`. Every raster shares the site's `corners`.

| Field | What | Who makes it |
|---|---|---|
| `event` `{date, label, source}` | The landslide, with a link | captain |
| `facts[]` `{text, source}` | 2–4 numbers with links | captain |
| `story.{place,rain,radar,tracking,exposure}` `{explore, research}` | Two texts per screen | story |
| `layers[]` `{id, kind, title, unit, description, source, frames[], legend}` | Extra rasters. `kind`: `coherence`, `displacement`, `optical`. A frame is `{date, file}` or `{from, to, file}` | NISAR / optical |
| `overlays[]` `{id, kind, title, file, …}` | `radar_blind` (image), `scar`/`stable` (polygon GeoJSON), `exposure` (points + lines), `aoi` (outline) | NISAR / exposure |
| `rain` `{file, source, note}` → `{series:[{date, mm}]}` | Daily IMERG over the window | rain |
| `point_extras` `{poi_id: file}` → `{series:[{from, to, coherence, los_cm}]}` | Per-point coherence and cumulative LOS | NISAR |
| `exposure` `{radius_km, buildings, roads_km, nearest_settlement, distance_km, method, source}` | Counts for screen 6 | exposure |
| `validation` `{threshold_db, pair, changed_inside_pct, changed_outside_pct, method}` | Radar vs optical scar check | captain |
| `limitations[]` | Site-specific limits | captain |
| `catalog[]` `{date, type, name, source}` | Registered events near the site (NASA Global Landslide Catalog / COOLR) | rain/exposure |
| `raw_example` `{linear, db, date}` | One date as raw power and as stretched dB (Radar Vision) | NISAR |

Open `../data/web/sites/toguz-bulak.json` for a complete example.

## Who owns what

| Folder | Owner | What is there |
|---|---|---|
| `src/app/` | map lead | Story composition, TRACE workspace, shared explorer state and parts, print page |
| `src/core/map/` | map lead | `SarMap` (MapLibre: raster, overlays, GeoJSON, markers), preloading |
| `src/features/timeline/` | map lead | `FrameSlider` (Play), `RainTimeline` |
| `src/features/compare/` | compare | `SwipeCompare`, `LayerControls`, `Legend`, overlay colours |
| `src/features/chart/` | chart | `TimeChart` (one SVG time axis for all charts), `PointPanel` |
| `src/features/exposure/` | story/design | `ExposureCard`, `EventCatalog` |
| `src/features/report/` | captain | `ReportBody` (on-page preview and print) |
| `src/features/listen/` | chart | Sonification: `useSonification`, `ListenButton` |
| `src/features/story/` | story + captain | `Screen`, `DataLimits`, `content.ts` (datasets, methods, AI use) |
| `src/core/theme/tokens.css` | story/design | Colours, spacing, fonts — variables only, no raw hex in features |
| `src/features/sites/` | shared | Contract types, `slope_echo` types, data hooks, `layers.ts` (one model for all rasters) |

Rules that keep merges painless: features never import each other's components (they meet in `app/`);
components never call `fetch` (use the hooks in `features/sites/api`); each feature keeps its own CSS file.
