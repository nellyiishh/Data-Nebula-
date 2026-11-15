import { useEffect, useRef, useState } from 'react'
import './HeroBackdrop.css'

// Backdrop for both first screens ("For everyone" and "For specialists"): the team's TRACE
// promo video on the right, our page colour on the left with a long gradient into the video,
// so the headline sits on calm ground. The video has its own captions on its left half; the
// frame is cropped from the left and the gradient covers what is left of them, so they do not
// compete with the headline. The loop is the caption-free product-demo part of the video
// (12–23 s of the team's 30 s render, H.264, no sound track: public/brand/hero-loop.mp4).
// With "reduce motion" the first frame is shown as a still. Decorative: hidden from readers.

const base = import.meta.env.BASE_URL
const REDUCE = '(prefers-reduced-motion: reduce)'
const reducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.(REDUCE).matches

export function HeroBackdrop() {
  const video = useRef<HTMLVideoElement>(null)
  const [still, setStill] = useState(reducedMotion)

  useEffect(() => {
    const query = window.matchMedia?.(REDUCE)
    if (!query) return
    const update = () => setStill(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    const v = video.current
    if (!v) return
    if (still) {
      v.pause()
      return
    }
    // Autoplay can be refused (power saving, data saver); the poster frame then stays, which is fine.
    v.play().catch(() => {})
  }, [still])

  return (
    <div className="hero-backdrop" aria-hidden="true">
      <div className="hero-backdrop__media">
        <video
          ref={video}
          poster={`${base}brand/hero-loop-poster.jpg`}
          muted
          loop
          playsInline
          autoPlay={!still}
          preload="auto"
          disablePictureInPicture
          tabIndex={-1}
        >
          <source src={`${base}brand/hero-loop.mp4`} type="video/mp4" />
        </video>
      </div>
    </div>
  )
}
