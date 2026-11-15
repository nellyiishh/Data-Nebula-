// TODO(contract-api): the first block mirrors backend/app/features/sites/schemas.py
// (contracts/openapi.json) by hand. Replace it with a generated client when we add one.
// The `slope_echo` block is a frontend-proposed extension the API does not serve yet;
// static files in public/data/ carry it. Keep both in sync with web/README.md.

export type LonLat = [number, number]
export type DataSource = 'demo' | 'nisar'

export interface SiteSummary {
  id: string
  name: string
  center: LonLat
  change_type: string
  /** 'demo' = synthetic; the UI must say so. */
  source: DataSource
}

export interface PointOfInterest {
  id: string
  name: string
  lon: number
  lat: number
  note: string
}

export interface Acquisition {
  date: string
  granule_id: string | null
  band: 'L' | 'S' | 'C'
  polarizations: string[]
}

export type ContractLayer = 'hh' | 'hv' | 'rgb' | 'water'

export interface SiteDetail extends SiteSummary {
  /** top-left, top-right, bottom-right, bottom-left */
  corners: [LonLat, LonLat, LonLat, LonLat]
  layers: ContractLayer[]
  acquisitions: Acquisition[]
  points_of_interest: PointOfInterest[]
  attribution: string
  dates: string[]
  slope_echo?: SlopeEcho
}

export interface PointTimeseries {
  site_id: string
  lon: number
  lat: number
  series: { date: string; hh_db: number | null; hv_db: number | null }[]
}

// ---- Slope Echo extension (static only for now) -------------------------------------

export interface SourceRef {
  name: string
  url?: string
}

/** Text in two registers: plain language and research detail. */
export interface DualText {
  explore: string
  research: string
}

export type StoryKey = 'place' | 'rain' | 'radar' | 'tracking' | 'exposure'

export interface ExtFrame {
  date?: string
  from?: string
  to?: string
  /** Path relative to the site's data folder. */
  file: string
}

export interface ExtLayer {
  id: string
  kind: 'coherence' | 'displacement' | 'optical' | (string & {})
  title: string
  unit: string
  description: string
  source: SourceRef
  frames: ExtFrame[]
  legend: { colors: string[]; labels: string[] } | null
}

export interface ExtOverlay {
  id: string
  kind: 'image' | 'polygon' | 'exposure' | 'outline'
  title: string
  file: string
  description: string
  source: SourceRef
}

/** Small photo from a news report; `file` sits in public/news/. Mirrors backend NewsImage. */
export interface NewsImage {
  file: string
  alt: string
}

export interface SlopeEcho {
  region: string
  country: string
  event: { date: string; label: string; source: SourceRef; image?: NewsImage }
  facts: { text: string; source?: SourceRef; image?: NewsImage }[]
  story: Record<StoryKey, DualText>
  layers: ExtLayer[]
  overlays: ExtOverlay[]
  rain: { file: string; source: SourceRef; note: string } | null
  /** Registered natural events near the site (e.g. NASA Global Landslide Catalog). */
  catalog?: { date: string; type: string; name: string; source: SourceRef }[]
  /** One date as raw linear power and as stretched dB, for the "why stretch" explainer. */
  raw_example?: { linear: string; db: string; date: string }
  /** poi id → file with per-pair coherence and cumulative LOS displacement */
  point_extras: Record<string, string>
  exposure: {
    radius_km: number
    buildings: number
    roads_km: number
    nearest_settlement: string
    distance_km: number
    method: string
    source: SourceRef
  } | null
  validation: {
    threshold_db: number
    pair: [string, string]
    changed_inside_pct: number
    changed_outside_pct: number
    method: string
  } | null
  limitations: string[]
}

export interface RainSeries {
  series: { date: string; mm: number }[]
}

export interface PointExtras {
  series: { from: string; to: string; coherence: number | null; los_cm: number | null }[]
}

/** GET /sites/{id}/change-stats (ChangeStats in contracts/openapi.json). Percentages are of
 *  pixels with data on both dates; areas are true ground area. */
export interface ChangeStats {
  site_id: string
  from: string
  to: string
  polarization: 'hh' | 'hv'
  threshold_db: number
  valid_pct: number
  darker_pct: number
  brighter_pct: number
  changed_pct: number
  darker_km2: number
  brighter_km2: number
  changed_km2: number
  mean_delta_db: number | null
}
