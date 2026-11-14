import type { LayerId } from '../../sites/model/types'

// Owner: Frontend 2 (compare). Ranges must match the backend's fixed stretch per layer.
// TODO(legend-api): confirm dB ranges with the backend prepare script.
const RANGES: Record<string, [string, string]> = {
  hh: ['−25 dB (smooth / water)', '0 dB (rough)'],
  hv: ['−32 dB (bare)', '−8 dB (vegetation)'],
}

export function Legend({ layer, showChange }: { layer: LayerId; showChange: boolean }) {
  const range = RANGES[layer]
  return (
    <div className="legend">
      {range && (
        <>
          <div className="legend__bar" style={{ background: 'linear-gradient(90deg, black, white)' }} />
          <div className="legend__labels muted">
            <span>{range[0]}</span>
            <span>{range[1]}</span>
          </div>
        </>
      )}
      {layer === 'rgb' && <span className="muted">R = HH · G = HV · B = HH/HV</span>}
      {layer === 'water' && (
        <span>
          <i className="legend__swatch" style={{ background: 'var(--accent)' }} />
          Open water
        </span>
      )}
      {showChange && (
        <div>
          <span>
            <i className="legend__swatch" style={{ background: 'var(--darker)' }} />
            Got darker (&gt; 3 dB)
          </span>{' '}
          <span>
            <i className="legend__swatch" style={{ background: 'var(--brighter)' }} />
            Got brighter (&gt; 3 dB)
          </span>
        </div>
      )}
    </div>
  )
}
