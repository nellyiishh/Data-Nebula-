import type { ImageOverlay, VectorOverlay } from '../core/map/SarMap'
import { overlayColor } from '../features/compare/model/overlays'
import { siteFileUrl } from '../features/sites/api'
import type { ExtOverlay, SiteDetail } from '../features/sites/model/types'

const VECTOR_STYLE: Record<string, VectorOverlay['style']> = { polygon: 'polygon', outline: 'outline', exposure: 'exposure' }

/** Splits slope_echo overlays into raster and GeoJSON layers for SarMap. */
export function toMapOverlays(site: SiteDetail, overlays: ExtOverlay[]) {
  const images: ImageOverlay[] = overlays
    .filter((o) => o.kind === 'image')
    .map((o) => ({ id: o.id, url: siteFileUrl(site.id, o.file) }))
  const vectors: VectorOverlay[] = overlays
    .filter((o) => o.kind !== 'image')
    .map((o) => ({ id: o.id, url: siteFileUrl(site.id, o.file), style: VECTOR_STYLE[o.kind] ?? 'outline', color: overlayColor(o.id) }))
  return { images, vectors }
}
