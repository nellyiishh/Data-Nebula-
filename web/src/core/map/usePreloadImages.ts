import { useEffect } from 'react'

/** Warms the browser cache so the time-slider animation does not flicker on first play. */
export function usePreloadImages(urls: string[]) {
  const key = urls.join('|')
  useEffect(() => {
    urls.forEach((u) => {
      const img = new Image()
      img.src = u
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
}
