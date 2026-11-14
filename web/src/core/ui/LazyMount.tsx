import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

/**
 * Mounts children only once they come near the viewport, then keeps them. Keeps the number of
 * live WebGL maps (and phone memory) low on a long scrolling page.
 */
export function LazyMount({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  // Old browsers without IntersectionObserver just render immediately.
  const [shown, setShown] = useState(() => !('IntersectionObserver' in window))

  useEffect(() => {
    const el = ref.current
    if (!el || shown) return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) setShown(true)
      },
      { rootMargin: '400px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [shown])

  return (
    <div ref={ref} className={className}>
      {shown ? children : null}
    </div>
  )
}
