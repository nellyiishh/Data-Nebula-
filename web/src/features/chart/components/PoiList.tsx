import type { PointOfInterest } from '../../sites/model/types'
import './chart.css'

// Owner: Frontend 3 (chart). Named places; clicking one loads its time series.

interface Props {
  points: PointOfInterest[]
  selectedId?: string
  onSelect: (p: PointOfInterest) => void
}

export function PoiList({ points, selectedId, onSelect }: Props) {
  if (points.length === 0) return <p className="state-msg">No points of interest for this site.</p>
  return (
    <ul className="poi-list">
      {points.map((p) => (
        <li key={p.id}>
          <button type="button" className="btn" aria-pressed={p.id === selectedId} onClick={() => onSelect(p)}>
            {p.name}
          </button>
          <span className="muted">{p.note}</span>
        </li>
      ))}
    </ul>
  )
}
