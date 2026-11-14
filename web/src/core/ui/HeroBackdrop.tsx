import './HeroBackdrop.css'

// Full-bleed mountain landscape behind a hero: a trail over grassy ridges, layered valleys and
// a cloudy blue-grey sky (public/brand/hero-mountains.jpg, image supplied by the team, with a
// 1280 px variant for small screens). Decorative only, so it is hidden from screen readers.

const base = import.meta.env.BASE_URL

export function HeroBackdrop() {
  return (
    <div className="hero-backdrop" aria-hidden="true">
      <img
        src={`${base}brand/hero-mountains.jpg`}
        srcSet={`${base}brand/hero-mountains-1280.jpg 1280w, ${base}brand/hero-mountains.jpg 1672w`}
        sizes="100vw"
        alt=""
        decoding="async"
      />
    </div>
  )
}
