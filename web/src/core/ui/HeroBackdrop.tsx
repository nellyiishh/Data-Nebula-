import './HeroBackdrop.css'

// Full-bleed generated mountain scene behind a hero (public/brand/hero-mountains.svg, made by
// scripts/make-hero-mountains.mjs). Decorative only, so it is hidden from screen readers.

export function HeroBackdrop() {
  return (
    <div className="hero-backdrop" aria-hidden="true">
      <img src={`${import.meta.env.BASE_URL}brand/hero-mountains.svg`} alt="" />
    </div>
  )
}
