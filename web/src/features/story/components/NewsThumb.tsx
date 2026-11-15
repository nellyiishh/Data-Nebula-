import type { NewsImage } from '../../sites/model/types'

// Small photo from the cited news report. Files live in public/news/ (BASE_URL-relative so
// the GitHub Pages sub-path works). Renders nothing when a card has no photo.
export function NewsThumb({ image }: { image?: NewsImage }) {
  if (!image) return null
  return (
    <img
      className="news-thumb"
      src={`${import.meta.env.BASE_URL}news/${image.file}`}
      alt={image.alt}
      loading="lazy"
      decoding="async"
    />
  )
}
