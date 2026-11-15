// Single place that knows where data comes from.
// - VITE_API_URL set   → the FastAPI backend (contracts/openapi.json).
// - VITE_API_URL empty → static files at /data (the backend export in ../data/web/).
// The static layout mirrors the API paths, except the two query endpoints, which fall back
// to pre-computed files (change/{from}_{to}.png, points/{poi_id}.json).

const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
export const isStatic = API_URL === ''

const STATIC_ROOT = `${import.meta.env.BASE_URL}data`
const api = (p: string) => `${API_URL}/api/v1${p}`

export const paths = {
  sites: () => (isStatic ? `${STATIC_ROOT}/sites.json` : api('/sites')),
  site: (id: string) => (isStatic ? `${STATIC_ROOT}/sites/${id}.json` : api(`/sites/${id}`)),
  layer: (id: string, layer: string, date: string) =>
    isStatic ? `${STATIC_ROOT}/sites/${id}/layers/${layer}/${date}.png` : api(`/sites/${id}/layers/${layer}/${date}.png`),
  change: (id: string, from: string, to: string) =>
    isStatic ? `${STATIC_ROOT}/sites/${id}/change/${from}_${to}.png` : api(`/sites/${id}/change.png?from=${from}&to=${to}`),
  /** Numbers behind change.png (GET …/change-stats); static export writes them beside the PNG. */
  changeStats: (id: string, from: string, to: string) =>
    isStatic
      ? `${STATIC_ROOT}/sites/${id}/change/${from}_${to}.json`
      : api(`/sites/${id}/change-stats?from=${from}&to=${to}`),
  /** Static mode cannot answer arbitrary points, so it needs the nearest point of interest. */
  timeseries: (id: string, lon: number, lat: number, poiId?: string) =>
    isStatic
      ? poiId
        ? `${STATIC_ROOT}/sites/${id}/points/${poiId}.json`
        : null
      : api(`/sites/${id}/timeseries?lon=${lon}&lat=${lat}`),
  /** Files referenced by the `slope_echo` extension (ext/…, layers/…), relative to the site folder. */
  siteFile: (id: string, rel: string) =>
    isStatic ? `${STATIC_ROOT}/sites/${id}/${rel}` : api(`/sites/${id}/files/${rel}`),
}

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = (await res.json()) as { error?: { message?: string } }
      if (body.error?.message) message = body.error.message
    } catch {
      // Body was not JSON (e.g. static 404 page); keep the status text.
    }
    throw new ApiError(res.status, message)
  }
  return (await res.json()) as T
}
