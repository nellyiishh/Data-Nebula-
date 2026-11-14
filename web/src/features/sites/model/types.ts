// TODO(contract-api): hand-written mirror of the contract in
// docs/plans/2026-11-14-nisar-surface-change-hackathon.md §4. Replace with the generated
// client from contracts/openapi.json once the backend publishes it (CLAUDE.md §2.3).

export type LonLat = [number, number]

export type ChangeType = 'water' | 'mudflow' | 'flood' | 'earthquake' | (string & {})

export interface SiteSummary {
  id: string
  name: string
  center: LonLat
  change_type: ChangeType
}

export interface PointOfInterest {
  id: string
  name: string
  lon: number
  lat: number
  note: string
}

/** Known layer ids; the backend may add more, so any string is accepted. */
export type LayerId = 'hh' | 'hv' | 'rgb' | 'water' | (string & {})

export interface Site {
  id: string
  name: string
  /** top-left, top-right, bottom-right, bottom-left — the order MapLibre image sources expect */
  corners: [LonLat, LonLat, LonLat, LonLat]
  dates: string[]
  layers: LayerId[]
  points_of_interest: PointOfInterest[]
}

export interface StatsEntry {
  date: string
  water_km2: number
  mean_hh_db: number
  mean_hv_db: number
}
export interface Stats {
  series: StatsEntry[]
}

export interface TimeSeries {
  lon: number
  lat: number
  series: { date: string; hh_db: number; hv_db: number }[]
}
