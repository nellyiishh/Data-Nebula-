import type { LayerView } from '../../sites/model/layers'
import type { ExtOverlay } from '../../sites/model/types'
import './LayerControls.css'

// Owner: Frontend 2 (compare). Layer switch, opacity, overlay toggles.

interface Props {
  layers: LayerView[]
  layerId: string
  onLayer: (id: string) => void
  opacity: number
  onOpacity: (v: number) => void
  overlays: ExtOverlay[]
  shownOverlays: string[]
  onToggleOverlay: (id: string) => void
  research: boolean
}

export function LayerControls(p: Props) {
  const layer = p.layers.find((l) => l.id === p.layerId)
  return (
    <div className="layer-controls">
      <div className="layer-controls__row" role="group" aria-label="Map layer">
        {p.layers.map((l) => (
          <button key={l.id} type="button" className="btn" aria-pressed={p.layerId === l.id} onClick={() => p.onLayer(l.id)}>
            {l.title}
          </button>
        ))}
      </div>
      {layer && (
        <p className="muted layer-controls__hint">
          {layer.description}
          {p.research && (
            <>
              {' '}
              <span className="layer-controls__src">
                Source:{' '}
                {layer.source.url ? (
                  <a href={layer.source.url} target="_blank" rel="noreferrer">
                    {layer.source.name}
                  </a>
                ) : (
                  layer.source.name
                )}
                {layer.unit && ` · unit: ${layer.unit}`}
              </span>
            </>
          )}
        </p>
      )}

      <label className="layer-controls__field">
        Opacity
        <input type="range" min={0} max={1} step={0.05} value={p.opacity} onChange={(e) => p.onOpacity(Number(e.target.value))} />
      </label>

      {p.overlays.length > 0 && (
        <fieldset className="layer-controls__overlays">
          <legend className="muted">On top</legend>
          {p.overlays.map((o) => (
            <label key={o.id} title={o.description}>
              <input type="checkbox" checked={p.shownOverlays.includes(o.id)} onChange={() => p.onToggleOverlay(o.id)} />
              {o.title}
            </label>
          ))}
        </fieldset>
      )}
    </div>
  )
}
