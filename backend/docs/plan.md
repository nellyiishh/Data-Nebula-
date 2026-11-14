# Dancing with the SARs — 6-hour team plan

NASA Space Apps 2026 · 6 people (1 backend, 5 frontend) · 6 hours · written 2026-11-14

Challenge page: https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/

## 0. Update (afternoon): the web app became "Slope Echo"

The team moved the story from seasonal water to **a landslide in Kyrgyzstan (Togus-Bulak)**.
The web app (`web/`, 9 screens) is built on its own fake files in `web/public/data/` and
asks for much more than the backend serves. Sections 2 and 7 below describe the old
water story; this section replaces them where they disagree.

### What the web reads vs what the backend gives today

| Web needs | Backend today | Gap |
|---|---|---|
| `sites.json`, `sites/{id}.json` with `change_type: "landslide"` | Sites API, but `change_type` only allows water/crops/forest/ice/deformation | **Blocking:** a landslide site fails validation |
| Optional `slope_echo` block in site detail (event, facts, story, extra layers, overlays, rain, exposure, validation, limitations, catalog, raw example) | Not in the schema | Add as an optional field so the API can serve what the static files carry |
| Files under `sites/{id}/ext/…` (coherence, displacement, optical PNGs, GeoJSON, rain, per-point extras) | No route | Web calls these static-only (`TODO(slope-echo-api)`) |
| HH / HV / colour-mix PNG per date | Served (plus a water mask the landslide story does not use) | Only list the layers that fit the change type |
| Change image per **consecutive pair**, static path `change/{from}_{to}.png` | Rendered on request only | Static export must pre-render the pairs |
| Point chart, static path `points/{poi_id}.json` | Query endpoint only | Static export must pre-compute each point |
| Legend: fixed dB stretch (`TODO(legend-api)`) | Ranges live only in `rendering.py` | Send the ranges in the site detail |
| Coherence and LOS displacement (cm) per pair, per point | **Nothing** | Needs interferogram data: GCOV has no phase (see catch) |
| Radar-blind mask (layover / shadow) | Nothing | Check GCOV mask layers; otherwise from the DEM |
| Validation: % changed inside the scar vs the stable area | Nothing | Compute from the HH stack + `scar.geojson` / `stable.geojson` |
| Raw linear-power example image | Nothing | One extra PNG from the pipeline |
| Rain (IMERG), exposure (OpenStreetMap), optical, event catalog | Nothing | Owned by the rain / exposure / optical people, not backend; export only copies their files |

### Catches

- **The web runs on static files by default** (`VITE_API_URL` empty). Unless someone hosts
  the API, judges see `web/public/data/`. So the most important backend output is an
  **export into that folder**, not more endpoints.
- **Coherence and displacement need a different NISAR product.** GCOV is brightness only.
  Coherence and ground motion come from the interferogram product (GUNW: coherence +
  unwrapped phase; L-band wavelength ≈ 24 cm, so LOS cm = phase × 24 / (4π)). Check on ASF
  Vertex whether GUNW pairs exist over the site *before* building anything for it. If not,
  label those screens "not available for this site" — never show the fake ones as real.
- Real NISAR coverage starts 17 June 2026 (gap 27 Jul – 10 Aug). The event date in the
  fake file and the dates of real passes must match, or the before/after story breaks.
- Togus-Bulak's centre is still a placeholder (`TODO(site)`). The pipeline bbox depends on it.

### Backend work, in order

**P0 — make the web run on real backend output — DONE (all 7 steps, tests green)**
1. Add `"landslide"` to `change_type`.
2. Add the optional `slope_echo` block to the site schema, typed to match
   `web/src/features/sites/model/types.ts`; the writer copies it from the manifest.
3. Put the display ranges (dB min/max per layer, change threshold, colours) in the site
   detail; the web legend reads them (closes `TODO(legend-api)`).
4. Per-site `layers` list depends on the change type (no water mask for a landslide).
5. **Static export** (`python -m pipeline.export_static`): writes `data/web/` (served by the
   web at `/data`) in the web's layout — `sites.json`, `sites/{id}.json`, layers, `change/{from}_{to}.png` for
   every consecutive pair, `points/{poi}.json`, and copies `ext/` files.
6. Serve `ext/` files from the API (`GET /sites/{id}/files/ext/…`, safe paths only), so
   API mode matches static mode.
7. Regenerate `contracts/openapi.json` after every step.

**P1 — real landslide data — code DONE; validation waits for a mapped scar outline**
8. Choose the bbox and the passes before/after the event (one track and frame) and run
   `prepare_nisar` on GCOV.
9. Validation numbers from the stack + scar/stable polygons.
10. Raw linear-power example image.
11. Radar-blind mask.

**P2 — GUNW exists over the site (5 pairs on track 156) — code DONE**
12. Coherence and LOS displacement PNGs per pair + per-point `coherence` / `los_cm`.

**Not backend:** rain, exposure, optical, catalog, story text. The export copies them.

### What is left (checked 2026-11-14, evening)

Done: P0, P1 code, P2. Real site `toguz-bulak`: 6 NISAR passes (12 Aug – 11 Oct), HH/HV/colour
mix, 5 coherence + 5 ground-motion pairs, radar-blind mask, raw example, one point
(village). 111 backend tests pass.

**A. Backend can do now (no outside input)**
1. ~~**Exposure**~~ **DONE:** `pipeline/exposure.py` → 14 buildings, 11.97 km of road within
   2 km. Measured around the village point until a `slide` point exists (item 8); rerun then.
2. ~~**Optical before/after**~~ **DONE:** `pipeline/optical.py` (NASA HLS v2.0, 30 m). Clouds are
   measured over the site from each scene's Fmask; one clear scene per radar pass on the
   same side of the event, plus the first clear one after it. Web note: Radar Vision shows
   the latest camera frame on or before the radar date, so an after-image later than the
   last radar pass only appears in the Time Machine.
3. ~~**Registered events**~~ **DONE:** `pipeline/catalog.py` (NASA COOLR reports, now at
   `gis.earthdata.nasa.gov/portal/...`; the old hosts are gone). 26 reports within 100 km,
   nearest 25 km, all from spring 2017; nothing newer nearby. Say so on screen 06.
4. **Re-run `prepare_nisar` + `export_static`** after each of the above.
5. ~~**Remove the synthetic `demo-reservoir` from `data/web/`.**~~ **DONE.** It comes back if
   `export_static` runs without `--site` while `data/derived/demo-reservoir/` exists; export
   with `--site toguz-bulak`.

**B. Needs a person first**
6. **Rain:** `pipeline/rain.py` is written but not run. Someone with the Earthdata account
   must accept the GES DISC terms once (otherwise every request is refused). Then run it and
   add the `rain` block to the manifest.
7. **Scar outline (+ stable area):** draw the slide polygon from the after-image
   (step 2) or from the Ministry's description. The validation numbers then compute
   automatically (code is done). Without it, keep "no validation" in the limitations.
8. **Slide location:** the only point is the village centre. Add a point on the slide
   itself (Donuz-Oi section) so the chart shows the slope, not the houses.

**C. Web team**
9. Read the legend from `display` (`TODO(legend-api)`); generate the TS types from
   `contracts/openapi.json` (`TODO(contract-api)`).
10. Story and team text (`TODO(story)` ×3, `TODO(team)` ×3); rain screen text once step 6 lands.
11. Check the 3D terrain in a real WebGL browser; remove or hide the fake `togus-bulak` site
    (note the spelling: the real one is `toguz-bulak`).

**D. Submission (everyone, start now)**
12. **Licence file** (MIT) — none yet, and the challenge requires open source.
13. **README** at the repo root is empty: what it is, how to run, data sources and credits.
14. Demo video or slides, Space Apps project page text, AI-use statement, dataset credits
    (NISAR/ASF, GPM IMERG, OpenStreetMap, HLS).
15. Final check: every link opens in a private window.

**E. Later (after the hackathon or if time is left)**
16. Move to the hosted backend (`TODO(server-backend)`, section below).
17. Swap the test client package (`httpx` → `httpx2`) to clear the one test warning.

### Later: move from "local files" to "server backend"

For now everything runs locally: the pipeline writes to `data/derived/`, and
`export_static` writes the website data to `data/web/` (the future bucket layout), which the
web dev server and build pick up at `/data`.
**This is temporary.** The backend will be hosted on Google Cloud / Firebase. Then:

- **Hosting:** run the FastAPI app on **Cloud Run** (Firebase Hosting cannot run Python;
  it can forward `/api/**` to Cloud Run with a rewrite). Firebase Hosting serves the web build.
- **Data:** prepared sites live in a **Cloud Storage bucket**, not on a laptop and not in the
  web repo. The API reads from the bucket (or images are served straight from it with
  public/signed URLs); `NEBULA_DATA_DIR` changes to point there.
- **Pipeline:** stays offline (raw NISAR crops are large), but uploads its output to the
  bucket instead of only writing `data/derived/`. It can later run as a Cloud Run job.
- **Web:** set `VITE_API_URL` to the Cloud Run URL. Change `paths.siteFile` in
  `web/src/core/api/client.ts` to use `GET /sites/{id}/files/…` (`TODO(slope-echo-api)`),
  so story files come from the API too.
- **Retire** `export_static`, `data/web/` and the `siteData` plugin in `web/vite.config.ts`
  (upload `data/web/` to the bucket instead; keep the web team's fakes for offline work).
- **Before switching:** CORS allowlist gets the Firebase domain; secrets (Earthdata) go in
  Secret Manager, never in the image.

Marked in code/docs as `TODO(server-backend)`.

### Agree with the web team before step 2

- The `slope_echo` field names stay exactly as in `types.ts` / `web/README.md`.
- Static layout and paths stay as in `web/src/core/api/client.ts`.
- Who replaces the hand-written TS types with ones generated from `contracts/openapi.json`
  (`TODO(contract-api)`).

## 1. What the challenge asks for

Build an **interactive application** that uses **NISAR radar data** to track and show one or
more kinds of surface change somewhere on Earth, in a way a non-expert can understand.

The challenge text asks for three steps and three answers:

1. Pick a study area.
2. Download free NISAR data (plus optional extra layers for context).
3. Present it interactively (sliders, web maps, time-series animation, dashboard).

And it asks you to answer, in the project itself:

- What physically causes the change you see?
- Which polarizations (HH, HV) show the change best?
- What could NISAR be used for in the future?

It must be **open source** and **user-friendly**. Space Apps judges on Impact, Creativity,
Validity, Relevance and Presentation.

## 2. (Superseded by section 0) What we build (proposal — change it in the first 30 minutes if you disagree)

**One web page that tells one clear story about one place.** Working title: *Earth's Rhythm*.

A map of the study area with:

- **Time slider with a play button** — radar images from June to November 2026 animate like frames.
- **Before / after swipe** — drag a divider between two dates.
- **Change map** — one coloured layer: where the surface got brighter or darker to radar.
- **Click any point → chart** of how that spot changed over time (HH and HV lines).
- **Headline number** — for example "water surface shrank by X km² since June".
- **Story panel** — plain-language text: what radar sees, why it changed, which polarization
  shows it, what NISAR could do next. This answers the three challenge questions directly.

### Which change, which place

Recommended: **seasonal water and farmland change near home** (a reservoir, lake shore,
wetland or irrigated valley you know personally).

- Water is the easiest thing to see in radar: it is dark, with a sharp edge. Low risk.
- June → November covers a full summer-to-autumn cycle, so a visible change is guaranteed
  (water level drops, crops are harvested). A flood or wildfire story depends on finding the
  right dates and may show nothing.
- The challenge explicitly rewards personal context for a hometown area.

Alternatives, only if the team already knows a specific 2026 event with dates: a flood, a
wildfire scar, glacier movement. Not recommended in 6 hours: ground deformation
(earthquake/subsidence). It needs a different, harder data product.

### Out of scope (do not start these)

- Login, user accounts, a database.
- Processing any area the visitor picks, live. We prepare one site (two if time allows).
- Machine learning. A threshold and a difference are enough and easier to defend.
- More than one type of change.

## 3. The biggest risk: getting the data

Facts checked today on the NISAR Data User Guide (ASF):

- Calibrated NISAR L-band data exists for acquisitions from **17 June 2026** onward
  (validated products from 21 October 2026).
- There is a permanent gap: **27 July – 10 August 2026**. No images in that window.
- The satellite revisits the same spot about every 12 days, so one site has roughly 10 usable
  dates. We need 4–6.
- The product to use is **GCOV** (terrain-corrected brightness, ready for maps). It is an HDF5
  file in a UTM projection, 10 or 20 m pixels. Layers we need:
  `/science/LSAR/GCOV/grids/frequencyA/HHHH` and `.../HVHV`.
- Download needs a free **NASA Earthdata Login**. Files are large.

Rules that prevent wasted hours:

- **Start the first download in the first 15 minutes.** Everything else waits on it.
- **All dates must come from the same track and frame.** Mixing viewing angles creates fake
  "change".
- **Crop to a small area early** (about 50 × 50 km). Never carry full scenes through the pipeline.
- **Data gate at 1h15m:** one NISAR image must be visible as a picture. If not, fall back:
  1. Use only two dates (one before, one after) instead of a series.
  2. Add Sentinel-1 radar (OPERA RTC-S1 from the same ASF archive, small files) to fill the
     time series, keeping at least one NISAR pair as the centrepiece. The challenge itself
     suggests comparing with other sensors, so this is a feature, not a cheat.

## 4. How it fits together

```
NISAR GCOV files ──► prepare script (run once, on the backend laptop)
                         │  crop → convert to decibels → smooth → reproject for web
                         ▼
                 data/<site>/  PNG images + JSON numbers + one small array file
                         │
                         ▼
                 FastAPI (read-only, no database) ──► React + map in the browser
```

- **Prepare once, serve fast.** Nothing heavy runs when a visitor clicks.
- **Safety net:** every response except the click-a-point chart is a plain file. If hosting
  the API fails, the frontend reads the same files from its own `public/data/` folder and the
  chart uses 5–8 pre-computed named points. The demo cannot die because of a server.

### Suggested stack

| Part | Choice | Why |
|---|---|---|
| Backend | Python, FastAPI, numpy, h5py, rasterio, Pillow, managed with uv | Matches this repo's guide; standard radar tooling |
| Data search | ASF Vertex website first, `asf_search` script only if time | Clicking is faster than debugging a search script |
| Frontend | React + Vite + TypeScript, MapLibre GL, one chart library | Free map, no API key needed |
| Hosting | Frontend on Vercel or Netlify; API on Render/Railway, or static fallback | Free and quick |

Note: this repo's `CLAUDE.md` lists PostgreSQL, migrations, auth, a generated API client,
test-first and a CI gate. **None of that fits in 6 hours.** This plan skips them on purpose.

### API contract (agree in the kickoff, then freeze it)

Frontend builds against fake files with exactly these shapes from minute 30.

```
GET /api/v1/sites
[{ "id": "site-1", "name": "…", "center": [lon, lat], "change_type": "water" }]

GET /api/v1/sites/{id}
{ "id": "site-1", "name": "…",
  "corners": [[lon,lat],[lon,lat],[lon,lat],[lon,lat]],   // top-left, top-right, bottom-right, bottom-left
  "dates": ["2026-06-20", "2026-07-14", "…"],
  "layers": ["hh", "hv", "rgb", "water"],
  "points_of_interest": [{ "id": "p1", "name": "…", "lon": 0, "lat": 0, "note": "…" }] }

GET /api/v1/sites/{id}/layers/{layer}/{date}.png      → transparent image, same corners
GET /api/v1/sites/{id}/change.png?from=DATE&to=DATE   → red = darker, blue = brighter
GET /api/v1/sites/{id}/stats
{ "series": [{ "date": "2026-06-20", "water_km2": 0, "mean_hh_db": 0, "mean_hv_db": 0 }] }

GET /api/v1/sites/{id}/timeseries?lon=…&lat=…
{ "lon": 0, "lat": 0, "series": [{ "date": "2026-06-20", "hh_db": 0, "hv_db": 0 }] }
```

All images are reprojected to Web Mercator and share one set of corner coordinates, so the
map places every date identically.

## 5. Who does what

| Person | Owns | Done when |
|---|---|---|
| **Backend (you)** | Data download, prepare script, API, hosting the API | Real images and numbers come back from every endpoint |
| **Frontend 1 — map lead** | App skeleton, map, image layers, time slider + play; merges everyone's work | Images animate over the map |
| **Frontend 2 — compare** | Before/after swipe, change-map layer, colour legend, layer switch (HH / HV / colour mix) | Two dates can be compared by dragging |
| **Frontend 3 — chart** | Click-a-point chart, headline number cards, points-of-interest list | Clicking the map draws a chart |
| **Frontend 4 — story and design** | Researches the place; writes the story panel and the three challenge answers; visual style, colours, mobile check | A stranger understands the page in 30 seconds |
| **Frontend 5 — submission and release** | Space Apps project page text, demo slides or video, README, licence, screenshots, deployment, final testing | Submitted, links open in a private window |

Frontend 5 starts the submission text in hour 1, not hour 5. It is a full job.

## 6. Timeline

| Time | Backend | Frontend | Everyone |
|---|---|---|---|
| **0:00–0:30** | Earthdata account; find scenes on Vertex; **start downloads** | Create the app, shared layout, fake data files matching the contract | Kickoff: pick site, agree contract, join the team on the Space Apps site |
| **0:30–1:15** | Open one file, crop, make the first picture | Each person builds their piece against fake data | — |
| **1:15** | | | **Gate 1: is a NISAR picture on screen?** If not, switch to the fallback now |
| **1:15–3:00** | All dates processed; change map; water area numbers; API running locally, then hosted | Pieces merged into one page; story text drafted | Submission text drafted |
| **3:00** | | | **Gate 2: real data shows in the real page.** No new features after this |
| **3:00–4:30** | Fix data problems; points of interest; static fallback files exported | Polish, legend, loading and error states, phone layout; deploy | Start slides or video |
| **4:30** | | | **Gate 3: public link works.** Bug fixes only from here |
| **4:30–5:30** | README: data sources, how to rerun | Screenshots, final polish | Finish demo and project page |
| **5:30–6:00** | | | **Submit.** Test every link in a private window. Keep 30 minutes spare |

## 7. (Superseded by section 0) Backend steps in order

1. Create a NASA Earthdata Login; save credentials in a local, gitignored file.
2. On ASF Vertex: dataset NISAR, product GCOV, draw the area, choose **one track/frame**,
   pick 4–6 dates between June and November (skip 27 Jul – 10 Aug). Start downloading.
3. Open one file, read HH and HV plus the x/y coordinate arrays and projection code.
4. Crop to the area. Convert brightness to decibels (10 × log10). Treat zeros and empty
   pixels as "no data".
5. Smooth the speckle (a small median filter) — raw radar is grainy and will look broken.
6. Reproject to Web Mercator. Save one PNG per date and layer, with one fixed brightness
   range for all dates so the animation does not flicker.
7. Water map: pixels darker than a threshold (find it from the histogram). Area per date in km².
8. Change map: decibels(after) minus decibels(before); colour only differences beyond about ±3 dB.
9. Save the cropped stack as one small array file; the click-a-point endpoint reads from it.
10. Wire the endpoints, allow the frontend's address (CORS), host it, export the static fallback.

## 8. Submission checklist

Check the exact fields on your team's project page early — these are the usual ones:

- [ ] All six members joined the team on the Space Apps site; this challenge selected.
- [ ] Project name and short summary.
- [ ] Demo link: slide deck or short video (Space Apps limits length — check the current limit).
- [ ] Project link: **public** code repository with an open-source licence (MIT) and README.
- [ ] Detailed description: what it does, how it works, why it matters, tools used.
- [ ] NASA data used: NISAR GCOV via ASF, with links and dates of the scenes.
- [ ] Partner agency data, if any (for example Sentinel-1, RADARSAT, SAOCOM).
- [ ] **Use of AI** statement — say where AI tools helped.
- [ ] References and credits for the base map and every dataset.
- [ ] Live link and repository open in a private browser window.

## 9. If there is time left

- Optical satellite layer under the radar (NASA GIBS tiles, free, no key) to show what radar
  sees through cloud.
- L-band (NISAR) versus C-band (Sentinel-1) side by side — the challenge mentions this.
- A second site with a different kind of change.
- A share link that remembers the chosen dates.

## Sources

- Challenge details and resources: https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/
- NISAR data availability: https://nisar-docs.asf.alaska.edu/availability-overview
- GCOV product description: https://nisar-docs.asf.alaska.edu/gcov
- Data search: https://search.asf.alaska.edu/
