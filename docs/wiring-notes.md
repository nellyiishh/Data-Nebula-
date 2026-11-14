# Wiring notes

What is real, stubbed or demo-only today. Update this in the same change that alters it.

| Surface | State | Notes |
|---|---|---|
| `GET /api/v1/health` | Wired | |
| `GET /api/v1/sites…` (list, detail, stats, layers, change, timeseries) | Wired | Serves whatever the pipeline wrote to `data/derived/` |
| `demo-reservoir` site | **Demo data** | Synthetic (`pipeline/make_demo_site.py`), `source: "demo"`. The UI must label it as not real |
| Real NISAR site | `TODO(nisar-pipeline)` | `backend/pipeline/prepare_nisar.py` is a stub; `data/manifest.json` has no sites yet |
| Static fallback for the frontend (`public/data/`) | Not built | Planned: export the same files so the demo survives an API outage |

## Web (`web/`)

| Surface | State | Notes |
|---|---|---|
| All data | **Demo — fake static files** | `web/public/data/` from `web/scripts/make-fake-data.mjs` (`togus-bulak`, `source: "demo"`). A banner and `DEMO` map badges say so. Set `VITE_API_URL` to use the API instead. |
| Contract types | Hand-written `TODO(contract-api)` | `web/src/features/sites/model/types.ts` mirrors `backend/app/features/sites/schemas.py`. |
| `slope_echo` block in site.json | **Static only** `TODO(slope-echo-api)` | Event, story text, rain, coherence, displacement, optical, overlays, exposure, validation. Not in the API yet; files are read from `public/data/sites/{id}/ext/`. Backend needs `change_type: "landslide"` and an optional `slope_echo` field to serve it. |
| Click-a-point chart (static mode) | Snaps to nearest point of interest | Live API mode passes the clicked coordinates (HH/HV only; coherence/LOS only for points of interest). |
| Legend stretch | `TODO(legend-api)` | `web/src/features/sites/model/layers.ts` — must match `backend/pipeline/writer.py`. |
| Event facts | `TODO(source)` | Links for 42.8k m³, 348 mudflows, ADB atlas still missing. |
| Site location | `TODO(site)` | Togus-Bulak centre is an approximate placeholder. |
| Team / AI-use text | `TODO(team)` | `web/src/features/story/content.ts`. |
| Registered events (`catalog`) | **Demo** | Two of three entries are invented; replace with NASA COOLR / Global Landslide Catalog rows. |
| 3D terrain | External tiles | AWS Open Data Terrain Tiles (terrarium), no key. Not checked in a WebGL browser yet. |
| Listen to Earth | Wired (client only) | Web Audio; pitch follows the selected point's series, silence = missing value. |
