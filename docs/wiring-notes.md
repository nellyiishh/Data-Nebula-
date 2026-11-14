# Wiring notes

What is real, stubbed or demo-only today. Update this in the same change that alters it.

| Surface | State | Notes |
|---|---|---|
| `GET /api/v1/health` | Wired | |
| `GET /api/v1/sites…` (list, detail, stats, layers, change, timeseries) | Wired | Serves whatever the pipeline wrote to `data/derived/` |
| `demo-reservoir` site | **Demo data** | Synthetic (`pipeline/make_demo_site.py`), `source: "demo"`. The UI must label it as not real |
| Real NISAR site | `TODO(nisar-pipeline)` | `backend/pipeline/prepare_nisar.py` is a stub; `data/manifest.json` has no sites yet |
| Static export → `web/public/data/` | Wired | `pipeline/export_static.py`. Merges `sites.json` (keeps other sites), replaces only the exported sites' folders |
| `slope_echo` block | Wired in the API | Optional field of the site detail, typed as in `web/.../types.ts`. Comes from `data/manifest.json`; its files from `data/ext/<site_id>/` (copied to `ext/`). Missing files fail the pipeline |
| `GET /sites/{id}/files/{ext/…\|layers/…}` | Wired | Serves the `slope_echo` files in API mode. Web `paths.siteFile` still always uses static files (`TODO(slope-echo-api)` on the web side) |
| Display ranges (`display` in site detail) | Wired | dB stretch, change threshold and colours the images were drawn with. Web legend can read them instead of `TODO(legend-api)` |
| Coherence / LOS displacement / radar-blind mask / validation / raw example | Not built | P1–P2 in the plan; GUNW needed for coherence and LOS |

## Web (`web/`)

| Surface | State | Notes |
|---|---|---|
| All data | **Demo — fake static files** | `web/public/data/` from `web/scripts/make-fake-data.mjs` (`togus-bulak`, `source: "demo"`). A banner and `DEMO` map badges say so. Set `VITE_API_URL` to use the API instead. |
| Contract types | Hand-written `TODO(contract-api)` | `web/src/features/sites/model/types.ts` mirrors `backend/app/features/sites/schemas.py`. `contracts/openapi.json` now includes `slope_echo`, `display` and `landslide`, so the whole file can be generated. |
| `slope_echo` block in site.json | **Static only** `TODO(slope-echo-api)` | Event, story text, rain, coherence, displacement, optical, overlays, exposure, validation. Not in the API yet; files are read from `public/data/sites/{id}/ext/`. The backend now accepts and serves both (see Backend table). |
| Click-a-point chart (static mode) | Snaps to nearest point of interest | Live API mode passes the clicked coordinates (HH/HV only; coherence/LOS only for points of interest). |
| Legend stretch | `TODO(legend-api)` | `web/src/features/sites/model/layers.ts` — must match `backend/pipeline/writer.py`. |
| Event facts | `TODO(source)` | Links for 42.8k m³, 348 mudflows, ADB atlas still missing. |
| Site location | `TODO(site)` | Togus-Bulak centre is an approximate placeholder. |
| Team / AI-use text | `TODO(team)` | `web/src/features/story/content.ts`. |
| Registered events (`catalog`) | **Demo** | Two of three entries are invented; replace with NASA COOLR / Global Landslide Catalog rows. |
| 3D terrain | External tiles | AWS Open Data Terrain Tiles (terrarium), no key. Not checked in a WebGL browser yet. |
| Listen to Earth | Wired (client only) | Web Audio; pitch follows the selected point's series, silence = missing value. |
