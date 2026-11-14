import type { LayerId } from '../../sites/model/types'
import { LAYER_HINTS, LAYER_LABELS } from '../model/layers'
import './LayerControls.css'

// Owner: Frontend 2 (compare). Layer switch, opacity, change-map toggle, compare mode + dates.

interface Props {
  layers: LayerId[]
  layer: LayerId
  onLayer: (l: LayerId) => void
  opacity: number
  onOpacity: (v: number) => void
  showChange: boolean
  onShowChange: (v: boolean) => void
  compare: boolean
  onCompare: (v: boolean) => void
  dates: string[]
  fromIndex: number
  toIndex: number
  onFrom: (i: number) => void
  onTo: (i: number) => void
}

export function LayerControls(p: Props) {
  return (
    <div className="layer-controls">
      <div className="layer-controls__row" role="group" aria-label="Radar layer">
        {p.layers.map((l) => (
          <button key={l} type="button" className="btn" aria-pressed={p.layer === l} onClick={() => p.onLayer(l)}>
            {LAYER_LABELS[l] ?? l}
          </button>
        ))}
      </div>
      <p className="muted layer-controls__hint">{LAYER_HINTS[p.layer] ?? ''}</p>

      <label className="layer-controls__field">
        Opacity
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={p.opacity}
          onChange={(e) => p.onOpacity(Number(e.target.value))}
        />
      </label>

      <div className="layer-controls__row">
        <button type="button" className="btn" aria-pressed={p.compare} onClick={() => p.onCompare(!p.compare)}>
          Before / after swipe
        </button>
        <button type="button" className="btn" aria-pressed={p.showChange} onClick={() => p.onShowChange(!p.showChange)}>
          Change map
        </button>
      </div>

      {(p.compare || p.showChange) && (
        <div className="layer-controls__dates">
          <DateSelect label="Before" dates={p.dates} value={p.fromIndex} onChange={p.onFrom} max={p.toIndex - 1} />
          <DateSelect label="After" dates={p.dates} value={p.toIndex} onChange={p.onTo} min={p.fromIndex + 1} />
        </div>
      )}
    </div>
  )
}

function DateSelect(props: {
  label: string
  dates: string[]
  value: number
  onChange: (i: number) => void
  min?: number
  max?: number
}) {
  const { label, dates, value, onChange, min = 0, max = dates.length - 1 } = props
  return (
    <label className="layer-controls__field">
      {label}
      <select value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {dates.map((d, i) => (
          <option key={d} value={i} disabled={i < min || i > max}>
            {d}
          </option>
        ))}
      </select>
    </label>
  )
}
