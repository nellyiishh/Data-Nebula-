import { paths } from '../../../core/api/client'
import { useJson } from '../../../core/api/useJson'
import type { PointExtras, PointTimeseries, RainSeries, SiteDetail, SiteSummary } from '../model/types'

export const useSites = () => useJson<SiteSummary[]>(paths.sites())
export const useSite = (id: string | null) => useJson<SiteDetail>(id ? paths.site(id) : null)

export interface PointQuery {
  lon: number
  lat: number
  /** Nearest point of interest; required when running on static files. */
  poiId?: string
}
export const useTimeSeries = (siteId: string, q: PointQuery | null) =>
  useJson<PointTimeseries>(q ? paths.timeseries(siteId, q.lon, q.lat, q.poiId) : null)

export const useRain = (site: SiteDetail) => {
  const file = site.slope_echo?.rain?.file
  return useJson<RainSeries>(file ? paths.siteFile(site.id, file) : null)
}

export const usePointExtras = (site: SiteDetail, poiId: string | undefined) => {
  const file = poiId ? site.slope_echo?.point_extras[poiId] : undefined
  return useJson<PointExtras>(file ? paths.siteFile(site.id, file) : null)
}

export const siteFileUrl = paths.siteFile
