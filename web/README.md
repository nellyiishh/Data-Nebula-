# web — Slope Echo frontend

*Rain loads it. Radar hears it. People live below it.* React + Vite + TypeScript + MapLibre GL.
Rules live in [`../CLAUDE.md`](../CLAUDE.md); what is real vs demo is in [`../docs/wiring-notes.md`](../docs/wiring-notes.md).

## Run

```bash
cd web
npm install
npm run dev          # http://localhost:5173 (needs a browser with WebGL2 for the maps)
```

Before pushing: `npm run lint && npm run build` (both must pass with zero warnings).

## The page (8 screens, one scroll)

| # | Screen | Where |
|---|---|---|
| 1 | Hero: map + tagline | `src/app/SitePage.tsx` |
| 2 | Place and facts with sources | `src/app/SitePage.tsx` |
| 3 | Rain: IMERG bars + NISAR passes + event line | `src/features/timeline/RainTimeline.tsx` |
| 4 | Radar hears it: layers, before/after, radar vs photo, overlays | `src/app/Explorer.tsx` |
| 5 | Tracking: Play through every pass, point chart (HH/HV, coherence, LOS) | `src/app/Explorer.tsx` |
| 6 | Who lives below: buildings/roads + counts | `src/features/exposure/` |
| 7 | Same tool, any slope: site switcher | `src/app/SitePage.tsx` |
| 8 | What we know and don't: validation, limits, methods, datasets, AI use | `src/features/story/DataLimits.tsx` |

- **Explore / Research** toggle in the header: every screen has a plain and a detailed text.
- **The URL keeps the view** (`?site, layer, f, swipe, a, b, ov, pt, mode`), so a link opens the same frame.
- **Field brief**: `?site=<id>&view=brief` → printable page (browser Print → Save as PDF).

## Where data comes from

`src/core/api/client.ts` is the only file that builds URLs.

- **`VITE_API_URL` empty (default)** → static files in `public/data/`. Right now **FAKE**, made by
  `npm run fake-data` (`scripts/make-fake-data.mjs`).
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

Open `public/data/sites/togus-bulak.json` for a complete example.

## Who owns what

| Folder | Owner | What is there |
|---|---|---|
| `src/app/` | map lead | Page composition, explorer state, field brief |
| `src/core/map/` | map lead | `SarMap` (MapLibre: raster, overlays, GeoJSON, markers), preloading |
| `src/features/timeline/` | map lead | `FrameSlider` (Play), `RainTimeline` |
| `src/features/compare/` | compare | `SwipeCompare`, `LayerControls`, `Legend`, overlay colours |
| `src/features/chart/` | chart | `TimeChart` (one SVG time axis for all charts), `PointPanel` |
| `src/features/exposure/` | story/design | `ExposureCard` |
| `src/features/story/` | story + captain | `Screen`, `DataLimits`, `content.ts` (datasets, methods, AI use) |
| `src/core/theme/tokens.css` | story/design | Colours, spacing, fonts — variables only, no raw hex in features |
| `src/features/sites/` | shared | Contract types, `slope_echo` types, data hooks, `layers.ts` (one model for all rasters) |

Rules that keep merges painless: features never import each other's components (they meet in `app/`);
components never call `fetch` (use the hooks in `features/sites/api`); each feature keeps its own CSS file.
