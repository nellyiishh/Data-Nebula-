# web — Data Nebula frontend

React + Vite + TypeScript + MapLibre GL. Rules live in [`../CLAUDE.md`](../CLAUDE.md); the team plan and
API contract are in [`../docs/plans/2026-11-14-nisar-surface-change-hackathon.md`](../docs/plans/2026-11-14-nisar-surface-change-hackathon.md) §4.

## Run

```bash
cd web
npm install
npm run dev          # http://localhost:5173
```

Before pushing: `npm run lint && npm run build` (both must pass with zero warnings).

## Where data comes from

`src/core/api/client.ts` is the only file that builds URLs.

- **`VITE_API_URL` empty (default)** → static files in `public/data/`. Right now these are **FAKE**, made by
  `npm run fake-data` (`scripts/make-fake-data.mjs`). The header shows a `static data` badge in this mode.
- **`VITE_API_URL=http://localhost:8000`** in `web/.env.local` → the FastAPI backend.

Static layout (mirrors the API; the backend's static export must use the same paths):

```
public/data/
  sites.json                                   GET /api/v1/sites
  sites/{id}.json                              GET /api/v1/sites/{id}
  sites/{id}/stats.json                        GET /api/v1/sites/{id}/stats
  sites/{id}/layers/{layer}/{date}.png         GET /api/v1/sites/{id}/layers/{layer}/{date}.png
  sites/{id}/change/{from}_{to}.png            GET /api/v1/sites/{id}/change.png?from=&to=
  sites/{id}/points/{poi_id}.json              GET /api/v1/sites/{id}/timeseries?lon=&lat=  (pre-computed per point)
```

All PNGs of a site share the site's `corners` (top-left, top-right, bottom-right, bottom-left, lon/lat).

## Who owns what

| Folder | Owner | What is there |
|---|---|---|
| `src/app/` | Frontend 1 (map lead) | App shell, `SitePage` = wires features together and holds view state |
| `src/core/map/` | Frontend 1 | `SarMap` (MapLibre, image layer, overlay, markers), preloading |
| `src/features/map/` | Frontend 1 | `TimeSlider` with play |
| `src/features/compare/` | Frontend 2 | `SwipeCompare`, `LayerControls`, `Legend`, layer names/hints |
| `src/features/chart/` | Frontend 3 | `PointChart` (SVG), `StatCards`, `PoiList` |
| `src/features/story/` | Frontend 4 | `StoryPanel` — texts marked `TODO(story)` |
| `src/core/theme/tokens.css` | Frontend 4 | Colours, spacing, fonts — use variables, no raw hex in features |
| `src/features/sites/` | shared | Contract types + data hooks (`useSites`, `useSite`, `useStats`, `useTimeSeries`) |

Rules that keep merges painless: features never import each other's components (they meet in `app/`);
components never call `fetch` (use the hooks in `features/sites/api`); each feature keeps its own CSS file.
