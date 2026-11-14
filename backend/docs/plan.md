# Dancing with the SARs — 6-hour team plan

NASA Space Apps 2026 · 6 people (1 backend, 5 frontend) · 6 hours · written 2026-11-14

Challenge page: https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/

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

## 2. What we build (proposal — change it in the first 30 minutes if you disagree)

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

## 7. Backend steps in order

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
