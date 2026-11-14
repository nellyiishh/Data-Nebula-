import { paths } from '../../../core/api/client'
import { useJson } from '../../../core/api/useJson'
import type { Site, SiteSummary, Stats, TimeSeries } from '../model/types'

export const useSites = () => useJson<SiteSummary[]>(paths.sites())
export const useSite = (id: string | null) => useJson<Site>(id ? paths.site(id) : null)
export const useStats = (id: string | null) => useJson<Stats>(id ? paths.stats(id) : null)

export interface PointQuery {
  lon: number
  lat: number
  /** Nearest point of interest; required when running on static files. */
  poiId?: string
}
export const useTimeSeries = (siteId: string | null, q: PointQuery | null) =>
  useJson<TimeSeries>(siteId && q ? paths.timeseries(siteId, q.lon, q.lat, q.poiId) : null)

export const layerUrl = paths.layer
export const changeUrl = paths.change
