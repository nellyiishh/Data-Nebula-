import { useEffect } from 'react'
import { notify } from '../ui/notify'

/** Warms the browser cache so the time-slider animation does not flicker on first play. */
export function usePreloadImages(urls: string[]) {
  const key = urls.join('|')
  useEffect(() => {
    urls.forEach((u) => {
      const img = new Image()
      img.onerror = () => notify('A radar image could not be loaded.')
      img.src = u
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
}
