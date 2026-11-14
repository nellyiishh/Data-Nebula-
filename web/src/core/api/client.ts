// Single place that knows where data comes from.
// - VITE_API_URL set   → the FastAPI backend (contract: docs/plans/...-hackathon.md §4).
// - VITE_API_URL empty → static files in public/data/ (fake data now, backend export later).
// The static layout mirrors the API paths, except the two query endpoints, which fall back
// to pre-computed files (change/{from}_{to}.png, points/{poi_id}.json).

const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
export const isStatic = API_URL === ''

const STATIC_ROOT = `${import.meta.env.BASE_URL}data`

export const paths = {
  sites: () => (isStatic ? `${STATIC_ROOT}/sites.json` : `${API_URL}/api/v1/sites`),
  site: (id: string) => (isStatic ? `${STATIC_ROOT}/sites/${id}.json` : `${API_URL}/api/v1/sites/${id}`),
  stats: (id: string) =>
    isStatic ? `${STATIC_ROOT}/sites/${id}/stats.json` : `${API_URL}/api/v1/sites/${id}/stats`,
  layer: (id: string, layer: string, date: string) =>
    isStatic
      ? `${STATIC_ROOT}/sites/${id}/layers/${layer}/${date}.png`
      : `${API_URL}/api/v1/sites/${id}/layers/${layer}/${date}.png`,
  change: (id: string, from: string, to: string) =>
    isStatic
      ? `${STATIC_ROOT}/sites/${id}/change/${from}_${to}.png`
      : `${API_URL}/api/v1/sites/${id}/change.png?from=${from}&to=${to}`,
  /** Static mode cannot answer arbitrary points, so it needs the nearest point of interest. */
  timeseries: (id: string, lon: number, lat: number, poiId?: string) =>
    isStatic
      ? poiId
        ? `${STATIC_ROOT}/sites/${id}/points/${poiId}.json`
        : null
      : `${API_URL}/api/v1/sites/${id}/timeseries?lon=${lon}&lat=${lat}`,
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
