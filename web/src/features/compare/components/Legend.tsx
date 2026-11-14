import type { LayerView } from '../../sites/model/layers'
import type { ExtOverlay } from '../../sites/model/types'
import { overlayColor } from '../model/overlays'

// Owner: Frontend 2 (compare). Legend for the active layer plus any overlays that are on.

export function Legend({ layer, overlays }: { layer: LayerView | undefined; overlays: ExtOverlay[] }) {
  const lg = layer?.legend
  return (
    <div className="legend">
      {lg && layer?.kind !== 'change' && lg.colors.length > 1 && (
        <>
          <div className="legend__bar" style={{ background: `linear-gradient(90deg, ${lg.colors.join(', ')})` }} />
          <div className="legend__labels muted">
            {lg.labels.map((l) => (
              <span key={l}>{l}</span>
            ))}
          </div>
        </>
      )}
      {lg && lg.colors.length === 1 && (
        <span>
          <i className="legend__swatch" style={{ background: lg.colors[0] }} />
          {lg.labels[0]}
        </span>
      )}
      {layer?.kind === 'change' && lg && (
        <div className="legend__labels">
          <span>
            <i className="legend__swatch" style={{ background: lg.colors[0] }} />
            {lg.labels[0]}
          </span>
          <span>
            <i className="legend__swatch" style={{ background: lg.colors[1] }} />
            {lg.labels[1]}
          </span>
        </div>
      )}
      {!lg && layer && <span className="muted">No colour scale: {layer.title.toLowerCase()} is shown as is.</span>}
      {overlays.map((o) => (
        <span key={o.id}>
          <i className="legend__swatch" style={{ background: overlayColor(o.id) }} />
          {o.title}
        </span>
      ))}
    </div>
  )
}

