import { useEffect, useState } from 'react'
import { getJson } from './client'

export type Loadable<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; error: string }
  | { status: 'ready'; data: T }

/** Fetches JSON when `url` changes. A null url means "nothing to load" (idle). */
export function useJson<T>(url: string | null): Loadable<T> {
  // The result is stored with the url it belongs to; a result for an older url reads as loading.
  const [result, setResult] = useState<{ url: string; value: Loadable<T> } | null>(null)

  useEffect(() => {
    if (!url) return
    const ctrl = new AbortController()
    getJson<T>(url, ctrl.signal)
      .then((data) => setResult({ url, value: { status: 'ready', data } }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        setResult({ url, value: { status: 'error', error: e instanceof Error ? e.message : String(e) } })
      })
    return () => ctrl.abort()
  }, [url])

  if (!url) return { status: 'idle' }
  if (result?.url !== url) return { status: 'loading' }
  return result.value
}
