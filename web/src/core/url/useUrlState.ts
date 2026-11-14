import { useCallback, useEffect, useState } from 'react'

// Small URL-backed state: ?site=…&layer=…&f=…&pt=…&mode=… so any view can be shared as a link.
// Uses replaceState (no history spam). Only plain, non-personal values belong here.

type Params = Record<string, string | undefined>

const read = (): Params => Object.fromEntries(new URLSearchParams(window.location.search))

export function useUrlState(): [Params, (patch: Params) => void] {
  const [params, setParams] = useState<Params>(read)

  useEffect(() => {
    const onPop = () => setParams(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const update = useCallback((patch: Params) => {
    setParams((prev) => {
      const next = { ...prev, ...patch }
      const qs = new URLSearchParams()
      for (const [k, v] of Object.entries(next)) if (v !== undefined && v !== '') qs.set(k, v)
      const s = qs.toString()
      window.history.replaceState(null, '', `${window.location.pathname}${s ? `?${s}` : ''}${window.location.hash}`)
      return next
    })
  }, [])

  return [params, update]
}
