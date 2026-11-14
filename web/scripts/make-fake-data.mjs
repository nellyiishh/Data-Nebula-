// Generates FAKE data in public/data/ that matches the API contract in
// docs/plans/2026-11-14-nisar-surface-change-hackathon.md §4, so the web app can be built
// before real NISAR layers exist. Replace public/data/ with the backend's static export
// (same layout) once real data is ready. Run: npm run fake-data
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { crc32, deflateSync } from 'node:zlib'

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'data')
const SIZE = 256

const SITE = {
  id: 'demo-site',
  name: 'Demo site (FAKE data)',
  center: [77.0, 43.15],
  change_type: 'mudflow',
}
// top-left, top-right, bottom-right, bottom-left
const CORNERS = [
  [76.85, 43.25],
  [77.15, 43.25],
  [77.15, 43.05],
  [76.85, 43.05],
]
// 12-day repeat, skipping the 27 Jul – 10 Aug 2026 NISAR gap. Event happens before 2026-08-19.
const DATES = ['2026-06-20', '2026-07-02', '2026-07-14', '2026-08-19', '2026-08-31', '2026-09-12']
const EVENT_INDEX = 3
const LAYERS = ['hh', 'hv', 'rgb', 'water']
const POIS = [
  { id: 'p1', name: 'Debris fan', lon: 76.99, lat: 43.12, note: 'Fake: where the flow spreads out.' },
  { id: 'p2', name: 'Upper channel', lon: 77.06, lat: 43.2, note: 'Fake: steep channel, source zone.' },
  { id: 'p3', name: 'Reservoir', lon: 76.92, lat: 43.09, note: 'Fake: water body, stays dark in radar.' },
]

// ---- PNG encoder (RGBA, no deps) -------------------------------------------------------
function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body) >>> 0)
  return Buffer.concat([len, body, crc])
}
function png(rgba, w, h) {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(w, 0)
  ihdr.writeUInt32BE(h, 4)
  ihdr[8] = 8
  ihdr[9] = 6
  const raw = Buffer.alloc((w * 4 + 1) * h)
  for (let y = 0; y < h; y++) {
    raw[y * (w * 4 + 1)] = 0
    rgba.copy(raw, y * (w * 4 + 1) + 1, y * w * 4, (y + 1) * w * 4)
  }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

// ---- Fake radar scene ------------------------------------------------------------------
function rand(seed) {
  let s = seed >>> 0
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32)
}
const noise = rand(42)
const speckle = Array.from({ length: SIZE * SIZE }, () => noise())

function inReservoir(x, y, t) {
  const r = 34 - t * 3 // shrinks slowly over the season
  return (x - 50) ** 2 + ((y - 200) * 1.4) ** 2 < r * r
}
function inFlow(x, y) {
  // A curved channel from the upper right towards a fan in the lower middle.
  const cx = 180 - (y - 40) * 0.55 + Math.sin(y / 18) * 8
  const width = y > 150 ? 6 + (y - 150) * 0.45 : 6
  return y > 40 && y < 210 && Math.abs(x - cx) < width
}

/** Returns backscatter in dB for HH and HV at a pixel and date index. */
function backscatter(x, y, t) {
  const terrain = Math.sin(x / 23) * 2 + Math.cos(y / 31) * 2 + Math.sin((x + y) / 11)
  const s = (speckle[y * SIZE + x] - 0.5) * 3
  if (inReservoir(x, y, t)) return { hh: -24 + s, hv: -30 + s }
  if (t >= EVENT_INDEX && inFlow(x, y)) {
    // Fresh rough debris: brighter HH; vegetation stripped: darker HV.
    const fade = (t - EVENT_INDEX) * 0.6
    return { hh: -4 - fade + s, hv: -22 + fade + s }
  }
  const season = Math.sin((t / DATES.length) * Math.PI) * 1.5 // greener mid-summer
  return { hh: -9 + terrain + s, hv: -16 + terrain + season + s }
}

const toByte = (db, min, max) => Math.max(0, Math.min(255, Math.round(((db - min) / (max - min)) * 255)))

function layerImage(layer, t) {
  const buf = Buffer.alloc(SIZE * SIZE * 4)
  for (let y = 0; y < SIZE; y++)
    for (let x = 0; x < SIZE; x++) {
      const { hh, hv } = backscatter(x, y, t)
      const i = (y * SIZE + x) * 4
      let px
      if (layer === 'hh') px = [toByte(hh, -25, 0), toByte(hh, -25, 0), toByte(hh, -25, 0), 255]
      else if (layer === 'hv') px = [toByte(hv, -32, -8), toByte(hv, -32, -8), toByte(hv, -32, -8), 255]
      else if (layer === 'rgb') px = [toByte(hh, -25, 0), toByte(hv, -32, -8), toByte(hh - hv, 0, 20), 255]
      else px = inReservoir(x, y, t) ? [40, 120, 255, 220] : [0, 0, 0, 0]
      buf.set(px, i)
    }
  return png(buf, SIZE, SIZE)
}

function changeImage(a, b) {
  const buf = Buffer.alloc(SIZE * SIZE * 4)
  for (let y = 0; y < SIZE; y++)
    for (let x = 0; x < SIZE; x++) {
      const d = backscatter(x, y, b).hh - backscatter(x, y, a).hh
      const i = (y * SIZE + x) * 4
      // Contract: red = darker, blue = brighter; only beyond ±3 dB.
      if (d < -3) buf.set([230, 50, 50, Math.min(255, 120 + (-d - 3) * 15)], i)
      else if (d > 3) buf.set([50, 110, 240, Math.min(255, 120 + (d - 3) * 15)], i)
    }
  return png(buf, SIZE, SIZE)
}

// ---- Write files -----------------------------------------------------------------------
function write(rel, data) {
  const p = join(OUT, rel)
  mkdirSync(dirname(p), { recursive: true })
  writeFileSync(p, typeof data === 'string' ? data : data)
}
const json = (v) => JSON.stringify(v, null, 2) + '\n'
const toPixel = (lon, lat) => [
  Math.round(((lon - CORNERS[0][0]) / (CORNERS[1][0] - CORNERS[0][0])) * (SIZE - 1)),
  Math.round(((CORNERS[0][1] - lat) / (CORNERS[0][1] - CORNERS[3][1])) * (SIZE - 1)),
]
const round = (v) => Math.round(v * 100) / 100

write('sites.json', json([SITE]))
write(
  `sites/${SITE.id}.json`,
  json({ id: SITE.id, name: SITE.name, corners: CORNERS, dates: DATES, layers: LAYERS, points_of_interest: POIS }),
)
DATES.forEach((date, t) => LAYERS.forEach((l) => write(`sites/${SITE.id}/layers/${l}/${date}.png`, layerImage(l, t))))
DATES.forEach((from, a) =>
  DATES.forEach((to, b) => b > a && write(`sites/${SITE.id}/change/${from}_${to}.png`, changeImage(a, b))),
)

const pixelKm2 = ((0.3 * 111 * Math.cos((43.15 * Math.PI) / 180)) / SIZE) * ((0.2 * 111) / SIZE)
const series = DATES.map((date, t) => {
  let water = 0
  let hh = 0
  let hv = 0
  for (let y = 0; y < SIZE; y++)
    for (let x = 0; x < SIZE; x++) {
      const v = backscatter(x, y, t)
      hh += v.hh
      hv += v.hv
      if (inReservoir(x, y, t)) water++
    }
  const n = SIZE * SIZE
  return { date, water_km2: round(water * pixelKm2), mean_hh_db: round(hh / n), mean_hv_db: round(hv / n) }
})
write(`sites/${SITE.id}/stats.json`, json({ series }))

// Static fallback for /timeseries: one file per point of interest.
for (const p of POIS) {
  const [x, y] = toPixel(p.lon, p.lat)
  write(
    `sites/${SITE.id}/points/${p.id}.json`,
    json({
      lon: p.lon,
      lat: p.lat,
      series: DATES.map((date, t) => {
        const v = backscatter(x, y, t)
        return { date, hh_db: round(v.hh), hv_db: round(v.hv) }
      }),
    }),
  )
}
console.log(`Fake data written to ${OUT}`)
