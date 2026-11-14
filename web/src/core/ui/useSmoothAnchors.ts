import { useEffect } from 'react'

// In-page links (href="#section") scroll smoothly instead of jumping: a quick, even
// ease-in-out glide whose length grows a little with the distance. The target lands just
// below the sticky header. Any wheel, touch or key input by the visitor cancels the glide,
// and people who ask for reduced motion get the instant jump as before.

const MIN_MS = 450
const MAX_MS = 800
const GAP_PX = 8

const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2)

function headerOffset() {
  const header = document.querySelector<HTMLElement>('.app__header')
  return (header?.offsetHeight ?? 0) + GAP_PX
}

export function useSmoothAnchors() {
  useEffect(() => {
    let frame = 0
    const cancel = () => {
      cancelAnimationFrame(frame)
      frame = 0
    }

    const glideTo = (top: number) => {
      cancel()
      const start = window.scrollY
      const distance = top - start
      const duration = Math.min(MAX_MS, Math.max(MIN_MS, 300 + Math.abs(distance) * 0.25))
      const t0 = performance.now()
      const step = (now: number) => {
        const t = Math.min(1, (now - t0) / duration)
        window.scrollTo(0, start + distance * easeInOutCubic(t))
        frame = t < 1 ? requestAnimationFrame(step) : 0
      }
      frame = requestAnimationFrame(step)
    }

    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
      const link = (e.target as Element | null)?.closest<HTMLAnchorElement>('a[href^="#"]')
      const id = link?.getAttribute('href')?.slice(1)
      if (!id) return
      const target = document.getElementById(decodeURIComponent(id))
      if (!target) return
      e.preventDefault()
      const top = target.getBoundingClientRect().top + window.scrollY - headerOffset()
      // Keep the address shareable, like a normal anchor, without adding history steps.
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${id}`)
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) window.scrollTo(0, top)
      else glideTo(top)
    }

    document.addEventListener('click', onClick)
    // The visitor taking over the scroll stops the glide at once.
    const stop = () => frame && cancel()
    window.addEventListener('wheel', stop, { passive: true })
    window.addEventListener('touchstart', stop, { passive: true })
    window.addEventListener('keydown', stop)
    return () => {
      cancel()
      document.removeEventListener('click', onClick)
      window.removeEventListener('wheel', stop)
      window.removeEventListener('touchstart', stop)
      window.removeEventListener('keydown', stop)
    }
  }, [])
}
