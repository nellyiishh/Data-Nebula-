# Wiring notes

What is real, stubbed or demo-only today. Update this in the same change that alters it.

| Surface | State | Notes |
|---|---|---|
| `GET /api/v1/health` | Wired | |
| `GET /api/v1/sites…` (list, detail, stats, layers, change, timeseries) | Wired | Serves whatever the pipeline wrote to `data/derived/` |
| `demo-reservoir` site | **Demo data** | Synthetic (`pipeline/make_demo_site.py`), `source: "demo"`. The UI must label it as not real |
| IMERG rain (`pipeline/rain.py`) | Wired; real data for toguz-bulak | Writes `data/ext/<site>/rain.json` (one 0.1° cell, 30 days before the first pass → last pass). Every request is 403 until the Earthdata account accepts the GES DISC terms once. After the file exists, set `slope_echo.rain` in the manifest and rerun `prepare_nisar` |
| Real NISAR site `toguz-bulak` | Wired (pipeline), exported to `data/web/` | `data/manifest.json`: track 156 A, frame 022, 6 PROVISIONAL GCOV passes 12 Aug – 11 Oct 2026 (event 10 Oct). Earthdata login read from `backend/.env` (EARTHDATA_* only). |
| Exposure (screen 06) | Wired (OpenStreetMap) | `pipeline/exposure.py --site <id>` → `data/ext/<id>/exposure.{geojson,json}`; `write_site` adds the `exposure` block + overlay. Centred on the `slide` point if the manifest has one, else the first point (today: the village, so `distance_km` is 0). Rerun after adding a slide point |
| Static export → `data/web/` | Wired, **temporary** `TODO(server-backend)` | `pipeline/export_static.py` writes website data only there (bucket layout). `web/vite.config.ts` (`siteData`) serves it at `/data` in dev and copies it into the build; files missing there fall back to the fakes in `web/public/data/`, and `sites.json` lists backend sites first. Replaced by the hosted API + Cloud Storage later |
| `slope_echo` block | Wired in the API | Optional field of the site detail, typed as in `web/.../types.ts`. Comes from `data/manifest.json`; its files from `data/ext/<site_id>/` (copied to `ext/`). Missing files fail the pipeline |
| `GET /sites/{id}/files/{ext/…\|layers/…}` | Wired | Serves the `slope_echo` files in API mode. Web `paths.siteFile` still always uses static files (`TODO(slope-echo-api)` on the web side) |
| Display ranges (`display` in site detail) | Wired | dB stretch, change threshold and colours the images were drawn with. Web legend can read them instead of `TODO(legend-api)` |
| Radar-blind overlay (`radar_blind`) | Wired | `pipeline/radar_blind.py`: local-slope layover/shadow from Copernicus GLO-30 DEM + GCOV look geometry. Ridges hiding distant valleys are not caught |
| Raw linear example | Wired | Last pass before the event, written by `pipeline/derived.py` when the block has none |
| Validation numbers | Wired, **no real input yet** | Computed only when the site has `scar` and `stable` polygon outlines in `data/ext/<id>/`; none are mapped for Toguz-Bulak, so `validation` is null |
| Coherence / LOS displacement (`coherence`, `displacement` layers + `point_extras`) | Wired | `pipeline/interferometry.py` + `derived.py` from NISAR GUNW pairs listed in the manifest (`pairs`). Coherence 20 m; motion from 80 m unwrapped phase − ionosphere, `−φλ/4π` (MintPy convention, + = toward the satellite), referenced to the site median, blank below coherence 0.3, colour ±1.5 cm. Point files hold cumulative motion, which stops (null) after a pair with no value |

## Web (`web/`)

| Surface | State | Notes |
|---|---|---|
| All data | **Demo — fake static files** | `web/public/data/` from `web/scripts/make-fake-data.mjs` (`togus-bulak`, `source: "demo"`). A banner and `DEMO` map badges say so. Set `VITE_API_URL` to use the API instead. |
| Contract types | Hand-written `TODO(contract-api)` | `web/src/features/sites/model/types.ts` mirrors `backend/app/features/sites/schemas.py`. `contracts/openapi.json` now includes `slope_echo`, `display` and `landslide`, so the whole file can be generated. |
| `slope_echo` block in site.json | **Static only** `TODO(slope-echo-api)` | Event, story text, rain, coherence, displacement, optical, overlays, exposure, validation. Not in the API yet; files are read from `public/data/sites/{id}/ext/`. The backend now accepts and serves both (see Backend table). |
| Click-a-point chart (static mode) | Snaps to nearest point of interest | Live API mode passes the clicked coordinates (HH/HV only; coherence/LOS only for points of interest). |
| Legend stretch | `TODO(legend-api)` | `web/src/features/sites/model/layers.ts` — must match `backend/pipeline/writer.py`. |
| Event facts | `TODO(source)` | Links for 42.8k m³, 348 mudflows, ADB atlas still missing. |
| Site location | `TODO(site)` on the web fake only | Real site: Toguz-Bulak village 40.4721 N, 73.6266 E (OpenStreetMap); the web fake `togus-bulak` sits ~10 km away. The slide outline (Donuz-Oi section) is still unmapped. |
| Team / AI-use text | `TODO(team)` | `web/src/features/story/content.ts`. |
| Registered events (`catalog`) | **Demo** | Two of three entries are invented; replace with NASA COOLR / Global Landslide Catalog rows. |
| 3D terrain | External tiles | AWS Open Data Terrain Tiles (terrarium), no key. Not checked in a WebGL browser yet. |
| Listen to Earth | Wired (client only) | Web Audio; pitch follows the selected point's series, silence = missing value. |
