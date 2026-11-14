// Generates FAKE data in public/data/ so the web app can be built before real NISAR layers
// exist. Run: npm run fake-data
//
// Layout = the backend contract (contracts/openapi.json, backend/app/features/sites/schemas.py)
// plus an optional `slope_echo` block in site.json for things the API does not serve yet
// (event, rain, coherence, displacement, optical, exposure, validation). See web/README.md.
// Every number and shape here is INVENTED; sites carry source: "demo" and the UI labels it.
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { crc32, deflateSync } from 'node:zlib'

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'data')
const S = 256

// ---- PNG encoder (RGBA, no deps) -------------------------------------------------------
function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body) >>> 0)
  return Buffer.concat([len, body, crc])
}
function png(pixel) {
  const raw = Buffer.alloc((S * 4 + 1) * S)
  for (let y = 0; y < S; y++)
    for (let x = 0; x < S; x++) {
      const px = pixel(x, y)
      if (px) raw.set(px.map((v) => clampByte(v)), y * (S * 4 + 1) + 1 + x * 4)
    }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(S, 0)
  ihdr.writeUInt32BE(S, 4)
  ihdr[8] = 8
  ihdr[9] = 6
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

// ---- Helpers ---------------------------------------------------------------------------
const rand = (seed) => {
  let s = seed >>> 0
  return () => (s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32
}
const clamp = (v, a, b) => Math.max(a, Math.min(b, v))
const clampByte = (v) => Math.round(clamp(v, 0, 255))
const byte = (v, min, max) => Math.round(clamp((v - min) / (max - min), 0, 1) * 255)
const round = (v, d = 2) => Math.round(v * 10 ** d) / 10 ** d
const lerp = (a, b, t) => a + (b - a) * t
const addDays = (d, n) => new Date(Date.parse(d) + n * 864e5).toISOString().slice(0, 10)
const pairs = (dates) => dates.slice(1).map((to, i) => [dates[i], to])

function write(rel, data) {
  const p = join(OUT, rel)
  mkdirSync(dirname(p), { recursive: true })
  writeFileSync(p, data)
}
const json = (v) => JSON.stringify(v, null, 2) + '\n'

// ---- Site definition (FAKE) ------------------------------------------------------------
const SITE = {
  id: 'togus-bulak',
  name: 'Togus-Bulak landslide',
  // TODO(site): approximate placeholder; replace with the surveyed location.
  center: [73.55, 40.55],
  half: [0.03, 0.023], // ~5 × 5 km window
  event: '2026-10-10',
  // 12-day repeat; the post-event acquisition is the first date after 10 Oct.
  dates: ['2026-08-23', '2026-09-04', '2026-09-16', '2026-09-28', '2026-10-22', '2026-11-03'],
  snowFrom: '2026-10-22',
}
const [cx, cy] = SITE.center
const W = cx - SITE.half[0]
const E = cx + SITE.half[0]
const N = cy + SITE.half[1]
const So = cy - SITE.half[1]
const CORNERS = [
  [W, N],
  [E, N],
  [E, So],
  [W, So],
]
const toLonLat = (x, y) => [round(lerp(W, E, x / (S - 1)), 5), round(lerp(N, So, y / (S - 1)), 5)]
const pixelKm = ((E - W) * 111 * Math.cos((cy * Math.PI) / 180)) / S

// Scene geometry in pixel space.
const elev = (x, y) => 1 - y / S + 0.15 * Math.sin(x / 30) // high at the top (north)
const scarCentre = (y) => 140 - ((y - 70) / 105) * 25 + Math.sin(y / 14) * 4
const scarHalfWidth = (y) => 6 + ((y - 70) / 105) * 14
const inScar = (x, y) => y >= 70 && y <= 175 && Math.abs(x - scarCentre(y)) < scarHalfWidth(y)
const inBlind = (x, y) => x < 40 && y < 120 // steep west-facing wall: layover/shadow
const inVillage = (x, y) => (x - 112) ** 2 + ((y - 215) * 1.6) ** 2 < 26 ** 2
const highSnow = (x, y) => elev(x, y) > 0.72

const speckle = Array.from({ length: S * S }, rand(7))
const afterEvent = (d) => d > SITE.event
const snowy = (d) => d >= SITE.snowFrom

function backscatter(x, y, d) {
  const terrain = Math.sin(x / 19) * 1.6 + Math.cos(y / 27) * 1.8 + Math.sin((x + y) / 9) * 0.8
  // Speckle differs per pass, so some unchanged pixels cross the threshold by chance (realistic).
  const k = SITE.dates.indexOf(d) * 7919
  const s = (speckle[(y * S + x + k) % (S * S)] + speckle[(y * S + x + k * 3) % (S * S)] - 1) * 2.2
  let hh = -10 + terrain + s
  let hv = -17 + terrain * 0.8 + s
  if (inVillage(x, y)) {
    hh += 7
    hv += 2
  }
  if (afterEvent(d) && inScar(x, y)) {
    hh += 5.5 // fresh rough debris
    hv -= 5 // vegetation stripped
  }
  if (snowy(d) && highSnow(x, y)) {
    hh -= 2.5 // wet snow absorbs
    hv -= 2
  }
  return { hh, hv }
}

function coherence(x, y, from, to) {
  if (inBlind(x, y)) return 0.05
  let c = 0.62 + (speckle[(y * S + x + 911) % (S * S)] - 0.5) * 0.25
  if (inVillage(x, y)) c += 0.2
  else c -= 0.12 // vegetation
  const spansEvent = from < SITE.event && to > SITE.event
  if (spansEvent && inScar(x, y)) c = 0.08 + speckle[y * S + x] * 0.08
  if (snowy(to) && highSnow(x, y)) c = Math.min(c, 0.2)
  return clamp(c, 0, 1)
}

/** LOS displacement in cm for one pair; null where it cannot be trusted (coherence < 0.3). */
function displacement(x, y, from, to) {
  if (coherence(x, y, from, to) < 0.3) return null
  const i = SITE.dates.indexOf(to)
  let v = (speckle[(y * S + x + 3333) % (S * S)] - 0.5) * 0.4
  if (inScar(x, y) && !afterEvent(to)) v -= [0, 0.3, 0.6, 1.1][i] ?? 0 // accelerating creep
  return v
}

// ---- Points of interest ----------------------------------------------------------------
const POIS = [
  { id: 'p1', name: 'Landslide body', px: [128, 130], note: 'Inside the mapped scar.' },
  { id: 'p2', name: 'Head scarp', px: [139, 78], note: 'Upper edge where the slope broke away.' },
  { id: 'p3', name: 'Village edge', px: [112, 205], note: 'Houses below the toe of the slide.' },
  { id: 'p4', name: 'Stable reference', px: [220, 210], note: 'Used to tune the 3 dB threshold.' },
].map(({ px, ...p }) => {
  const [lon, lat] = toLonLat(...px)
  return { ...p, lon, lat, px }
})

// ---- Rasters ---------------------------------------------------------------------------
rmSync(OUT, { recursive: true, force: true })
const base = `sites/${SITE.id}`

for (const d of SITE.dates) {
  write(`${base}/layers/hh/${d}.png`, png((x, y) => {
    const v = byte(backscatter(x, y, d).hh, -22, 2)
    return [v, v, v, 255]
  }))
  write(`${base}/layers/hv/${d}.png`, png((x, y) => {
    const v = byte(backscatter(x, y, d).hv, -30, -6)
    return [v, v, v, 255]
  }))
  write(`${base}/layers/rgb/${d}.png`, png((x, y) => {
    const { hh, hv } = backscatter(x, y, d)
    return [byte(hh, -22, 2), byte(hv, -30, -6), byte(hh - hv, 2, 14), 255]
  }))
  // Fake optical: green slopes, brown scar after the event, clouds on two dates.
  const cloudy = d === '2026-09-28' || d === '2026-11-03'
  write(`${base}/ext/optical/${d}.png`, png((x, y) => {
    const n = speckle[y * S + x] * 18
    if (cloudy && Math.sin(x / 23) + Math.cos(y / 17) + Math.sin((x - y) / 31) > 0.3) return [235, 238, 242, 255]
    if (snowy(d) && highSnow(x, y)) return [240, 244, 248, 255]
    if (afterEvent(d) && inScar(x, y)) return [150 + n, 120 + n, 95 + n, 255]
    if (inVillage(x, y)) return [170 + n, 160 + n, 150 + n, 255]
    return [70 + n, 110 + n * 1.5 - elev(x, y) * 20, 55 + n, 255]
  }))
}

for (const [from, to] of pairs(SITE.dates)) {
  write(`${base}/change/${from}_${to}.png`, png((x, y) => {
    const dd = backscatter(x, y, to).hh - backscatter(x, y, from).hh
    if (dd < -3) return [230, 50, 50, 130 + (-dd - 3) * 20]
    if (dd > 3) return [50, 110, 240, 130 + (dd - 3) * 20]
    return null
  }))
  write(`${base}/ext/coherence/${from}_${to}.png`, png((x, y) => {
    const v = byte(coherence(x, y, from, to), 0, 1)
    return [v, v * 0.85, 255 - v * 0.6, 255]
  }))
  write(`${base}/ext/displacement/${from}_${to}.png`, png((x, y) => {
    const v = displacement(x, y, from, to)
    if (v === null || Math.abs(v) < 0.2) return null
    const t = clamp(v / 1.5, -1, 1) // ±1.5 cm full scale; negative = away from the satellite
    return t < 0 ? [230, 60, 50, -t * 230] : [50, 110, 240, t * 230]
  }))
}
// "Raw" linear power for one date: what a SAR image looks like before dB + stretching (mostly black).
const lastDate = SITE.dates[SITE.dates.length - 1]
write(`${base}/ext/raw/${lastDate}_linear.png`, png((x, y) => {
  const v = byte(10 ** (backscatter(x, y, lastDate).hh / 10), 0, 1.6)
  return [v, v, v, 255]
}))
write(`${base}/ext/radar_blind.png`, png((x, y) => (inBlind(x, y) ? [120, 120, 130, 200] : null)))

// ---- Point series ----------------------------------------------------------------------
for (const p of POIS) {
  // Contract shape (static stand-in for GET /sites/{id}/timeseries).
  write(`${base}/points/${p.id}.json`, json({
    site_id: SITE.id,
    lon: p.lon,
    lat: p.lat,
    series: SITE.dates.map((d) => {
      const v = backscatter(...p.px, d)
      return { date: d, hh_db: round(v.hh), hv_db: round(v.hv) }
    }),
  }))
  let cum = 0
  write(`${base}/ext/points/${p.id}.json`, json({
    series: pairs(SITE.dates).map(([from, to]) => {
      const v = displacement(...p.px, from, to)
      if (v !== null) cum += v
      return { from, to, coherence: round(coherence(...p.px, from, to)), los_cm: v === null ? null : round(cum) }
    }),
  }))
}

// ---- Rain (fake IMERG-like daily totals, mm). Storm in the week before the event. ------
const r = rand(99)
const rain = []
for (let d = '2026-08-15'; d <= '2026-11-10'; d = addDays(d, 1)) {
  const storm = d >= '2026-10-03' && d <= '2026-10-09'
  const wet = r() < 0.25
  rain.push({ date: d, mm: round(storm ? 12 + r() * 26 : wet ? r() * 9 : 0, 1) })
}
write(`${base}/ext/rain.json`, json({ series: rain }))

// ---- Vectors (GeoJSON, lon/lat) --------------------------------------------------------
const feature = (geometry, properties = {}) => ({ type: 'Feature', geometry, properties })
const fc = (features) => ({ type: 'FeatureCollection', features })
const close = (pts) => [...pts, pts[0]]

const scarRing = []
for (let y = 70; y <= 175; y += 5) scarRing.push(toLonLat(scarCentre(y) + scarHalfWidth(y), y))
for (let y = 175; y >= 70; y -= 5) scarRing.push(toLonLat(scarCentre(y) - scarHalfWidth(y), y))
write(`${base}/ext/scar.geojson`, json(fc([feature({ type: 'Polygon', coordinates: [close(scarRing)] }, { name: 'Mapped scar' })])))
write(`${base}/ext/stable.geojson`, json(fc([feature({
  type: 'Polygon',
  coordinates: [close([toLonLat(200, 190), toLonLat(240, 190), toLonLat(240, 230), toLonLat(200, 230)])],
}, { name: 'Stable reference area' })])))

const rb = rand(5)
const buildings = []
while (buildings.length < 46) {
  const x = 80 + rb() * 64
  const y = 195 + rb() * 40
  if (inVillage(x, y)) buildings.push(feature({ type: 'Point', coordinates: toLonLat(x, y) }, { kind: 'building' }))
}
const roadCoords = [toLonLat(0, 236), toLonLat(70, 228), toLonLat(112, 222), toLonLat(170, 226), toLonLat(255, 240)]
write(`${base}/ext/exposure.geojson`, json(fc([...buildings, feature({ type: 'LineString', coordinates: roadCoords }, { kind: 'road' })])))

const kmPerDegLon = 111 * Math.cos((cy * Math.PI) / 180)
const radiusPx = 2 / pixelKm
const circle = []
for (let a = 0; a < Math.PI * 2; a += Math.PI / 32) circle.push(toLonLat(128 + Math.cos(a) * radiusPx, 125 + Math.sin(a) * radiusPx))
write(`${base}/ext/aoi.geojson`, json(fc([feature({ type: 'Polygon', coordinates: [close(circle)] }, { name: '2 km radius' })])))

// ---- Validation: |ΔHH| > 3 dB pre → post event, inside vs outside the scar -------------
const [pre, post] = [SITE.dates[3], SITE.dates[4]]
let inC = 0
let inN = 0
let outC = 0
let outN = 0
for (let y = 0; y < S; y++)
  for (let x = 0; x < S; x++) {
    if (inBlind(x, y)) continue
    const changed = Math.abs(backscatter(x, y, post).hh - backscatter(x, y, pre).hh) > 3
    if (inScar(x, y)) {
      inN++
      if (changed) inC++
    } else {
      outN++
      if (changed) outC++
    }
  }
const roadKm = roadCoords.slice(1).reduce((sum, b, i) => {
  const a = roadCoords[i]
  return sum + Math.hypot((b[0] - a[0]) * kmPerDegLon, (b[1] - a[1]) * 111)
}, 0)

// ---- Site JSON -------------------------------------------------------------------------
const src = {
  gcov: { name: 'NISAR L2 GCOV (provisional), ASF DAAC', url: 'https://search.asf.alaska.edu/' },
  gunw: { name: 'NISAR L2 GUNW (provisional), ASF DAAC', url: 'https://search.asf.alaska.edu/' },
  imerg: { name: 'GPM IMERG Late daily, NASA GES DISC', url: 'https://gpm.nasa.gov/data/imerg' },
  optical: { name: 'Sentinel-2 / HLS optical', url: 'https://hls.gsfc.nasa.gov/' },
  osm: { name: '© OpenStreetMap contributors', url: 'https://www.openstreetmap.org/copyright' },
  coolr: { name: 'NASA COOLR / Global Landslide Catalog', url: 'https://landslides.nasa.gov/' },
  todo: { name: 'TODO(source): add the news or agency link' },
}
const pairFrames = (dir) => pairs(SITE.dates).map(([from, to]) => ({ from, to, file: `ext/${dir}/${from}_${to}.png` }))

const siteDetail = {
  id: SITE.id,
  name: SITE.name,
  center: SITE.center,
  change_type: 'landslide',
  source: 'demo',
  corners: CORNERS,
  layers: ['hh', 'hv', 'rgb'],
  acquisitions: SITE.dates.map((d) => ({ date: d, granule_id: null, band: 'L', polarizations: ['HH', 'HV'] })),
  points_of_interest: POIS.map(({ px: _px, ...p }) => p),
  attribution: 'FAKE demo data generated by web/scripts/make-fake-data.mjs',
  dates: SITE.dates,
  slope_echo: {
    region: 'Kara-Kulja district, Osh region',
    country: 'Kyrgyzstan',
    event: { date: SITE.event, label: 'Landslide, ~42.8 thousand m³ of ground moved', source: src.todo },
    facts: [
      { text: 'About 42.8 thousand m³ of ground moved on 10 October 2026.', source: src.todo },
      { text: 'Kyrgyzstan recorded 348 mudflows in the first half of 2026, the most in 30–40 years.', source: src.todo },
      { text: 'More than 30,000 people in Kyrgyzstan are directly exposed to landslides (ADB landslide atlas).', source: src.todo },
    ],
    story: {
      place: {
        explore: 'A mountain village in southern Kyrgyzstan. On 10 October 2026 the slope above it gave way.',
        research: 'Study window ~5 × 5 km around the slide. Event date from local reports; scar outline mapped on post-event optical imagery.',
      },
      rain: {
        explore: 'It rained hard for a week before the slope failed. Water makes soil heavy and weak.',
        research: 'GPM IMERG Late daily totals over the window. One IMERG pixel is ~10 km, larger than the slope, so this is regional rain, not rain on the slide itself.',
      },
      radar: {
        explore: 'The satellite sends its own radio waves, so it sees the ground through clouds and at night. After the slide, the broken ground echoes back differently.',
        research: 'L-band HH brightens where fresh debris adds roughness; HV darkens where vegetation volume was removed. InSAR coherence collapses across the scar in the pair spanning the event.',
      },
      tracking: {
        explore: 'Each NISAR pass is one frame. Press Play to watch the slope change pass by pass.',
        research: 'Line-of-sight displacement from GUNW pairs, referenced to a stable area and masked where coherence < 0.3. LOS is not downslope motion.',
      },
      exposure: {
        explore: 'These are the houses and roads closest to the slide.',
        research: 'Buildings and roads from OpenStreetMap within 2 km of the scar centre. Proximity is not a hazard assessment.',
      },
    },
    layers: [
      {
        id: 'coherence', kind: 'coherence', title: 'Coherence', unit: '0–1', source: src.gunw,
        description: 'How alike two passes are. Low = the surface was disturbed (or snow, or vegetation).',
        frames: pairFrames('coherence'),
        legend: { colors: ['#0000ff', '#ffd9a3'], labels: ['0 changed', '1 unchanged'] },
      },
      {
        id: 'displacement', kind: 'displacement', title: 'Displacement (LOS)', unit: 'cm', source: src.gunw,
        description: 'Movement towards or away from the satellite between two passes. Blank where coherence is too low to trust.',
        frames: pairFrames('displacement'),
        legend: { colors: ['#e63c32', '#00000000', '#326ef0'], labels: ['−1.5 cm away', '0', '+1.5 cm towards'] },
      },
      {
        id: 'optical', kind: 'optical', title: 'Optical', unit: '', source: src.optical,
        description: 'Ordinary colour picture for reference. Clouds hide the ground on some dates; radar sees through them.',
        frames: SITE.dates.map((d) => ({ date: d, file: `ext/optical/${d}.png` })),
        legend: null,
      },
    ],
    overlays: [
      { id: 'radar_blind', kind: 'image', title: 'Radar blind spots', file: 'ext/radar_blind.png', description: 'Layover/shadow on steep slopes: radar cannot see here.', source: src.gcov },
      { id: 'scar', kind: 'polygon', title: 'Mapped scar', file: 'ext/scar.geojson', description: 'Outline drawn on post-event optical imagery.', source: src.optical },
      { id: 'stable', kind: 'polygon', title: 'Stable reference area', file: 'ext/stable.geojson', description: 'Used to tune the change threshold and as the InSAR reference.', source: src.gcov },
      { id: 'exposure', kind: 'exposure', title: 'Buildings and roads', file: 'ext/exposure.geojson', description: 'From OpenStreetMap.', source: src.osm },
      { id: 'aoi', kind: 'outline', title: '2 km radius', file: 'ext/aoi.geojson', description: 'Radius used for the exposure counts.', source: src.osm },
    ],
    // Registered events near the site (NASA Global Landslide Catalog / COOLR style). FAKE examples.
    catalog: [
      { date: '2026-10-10', type: 'landslide', name: 'Togus-Bulak slope failure', source: src.todo },
      { date: '2024-04-18', type: 'mudflow', name: 'Mudflow in the same valley (demo)', source: src.coolr },
      { date: '2021-05-02', type: 'landslide', name: 'Road cut collapse 3 km downstream (demo)', source: src.coolr },
    ],
    raw_example: { linear: `ext/raw/${lastDate}_linear.png`, db: `layers/hh/${lastDate}.png`, date: lastDate },
    rain: { file: 'ext/rain.json', source: src.imerg, note: 'IMERG pixel ~10 km: regional rain, not rain on the slope.' },
    point_extras: Object.fromEntries(POIS.map((p) => [p.id, `ext/points/${p.id}.json`])),
    exposure: {
      radius_km: 2,
      buildings: buildings.length,
      roads_km: round(roadKm, 1),
      nearest_settlement: 'Togus-Bulak village (placeholder)',
      distance_km: round((215 - 175) * pixelKm, 2),
      method: 'OpenStreetMap buildings and road length within 2 km of the scar centre. Not a hazard or population estimate.',
      source: src.osm,
    },
    validation: {
      threshold_db: 3,
      pair: [pre, post],
      changed_inside_pct: round((inC / inN) * 100, 1),
      changed_outside_pct: round((outC / outN) * 100, 1),
      method: '|ΔHH| > 3 dB between the last pass before and the first pass after the event; radar blind spots excluded. Threshold tuned on the stable reference area.',
    },
    limitations: [
      'Radar cannot see layover/shadow areas on steep slopes (grey on the map).',
      'Snow from late October lowers coherence and changes backscatter on high ground; do not read it as slope movement.',
      'Fast landslide motion decorrelates InSAR, so displacement is meaningful before and after the event, not during it.',
      'Line-of-sight displacement is not the same as downslope displacement.',
      'IMERG rain is regional (~10 km pixels).',
    ],
  },
}

write('sites.json', json([{ id: SITE.id, name: SITE.name, center: SITE.center, change_type: 'landslide', source: 'demo' }]))
write(`${base}.json`, json(siteDetail))
const v = siteDetail.slope_echo.validation
console.log(`FAKE data written to ${OUT} (changed pixels: ${v.changed_inside_pct}% inside scar vs ${v.changed_outside_pct}% outside)`)
