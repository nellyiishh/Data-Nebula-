import type { ReactNode } from 'react'
import type { Loadable } from '../../../core/api/useJson'
import type { LayerView } from '../../sites/model/layers'
import type { PointExtras, PointOfInterest, PointTimeseries } from '../../sites/model/types'
import { TimeChart } from './TimeChart'
import type { TimeLine } from './TimeChart'
import './chart.css'

// Owner: Frontend 3 (chart). "Tracking the slope": what one point did over every radar pass.
// The metric follows the active layer: backscatter → HH/HV dB, coherence → 0–1,
// displacement → cumulative LOS cm.

interface Props {
  layer: LayerView | undefined
  dates: string[]
  event?: { date: string; label: string }
  cursor?: string
  backscatter: Loadable<PointTimeseries>
  extras: Loadable<PointExtras>
  points: PointOfInterest[]
  selectedId?: string
  pointLabel?: string
  onSelect: (p: PointOfInterest) => void
  /** Extra UI under the chart for the main line (e.g. sonification), composed by the app. */
  renderExtra?: (line: TimeLine) => ReactNode
}

function linesFor(p: Props): { lines: TimeLine[]; unit: string } | { message: string; error?: boolean } {
  const kind = p.layer?.kind
  if (kind === 'coherence' || kind === 'displacement') {
    const ex = p.extras
    if (ex.status === 'idle') return { message: 'No coherence/displacement series for this point yet.' }
    if (ex.status === 'loading') return { message: 'Loading…' }
    if (ex.status === 'error') return { message: `Could not load: ${ex.error}`, error: true }
    return kind === 'coherence'
      ? {
          unit: '0–1',
          lines: [{ id: 'coh', label: 'Coherence', color: 'var(--accent)', points: ex.data.series.map((s) => ({ date: s.to, value: s.coherence })) }],
        }
      : {
          unit: 'cm',
          lines: [{ id: 'los', label: 'LOS displacement', color: 'var(--accent-2)', points: ex.data.series.map((s) => ({ date: s.to, value: s.los_cm })) }],
        }
  }
  const bs = p.backscatter
  if (bs.status === 'idle') return { message: 'Pick a place below or click the map.' }
  if (bs.status === 'loading') return { message: 'Loading…' }
  if (bs.status === 'error') return { message: `Could not load: ${bs.error}`, error: true }
  const hh: TimeLine = { id: 'hh', label: 'HH', color: 'var(--hh)', points: bs.data.series.map((s) => ({ date: s.date, value: s.hh_db })) }
  const hv: TimeLine = { id: 'hv', label: 'HV', color: 'var(--hv)', points: bs.data.series.map((s) => ({ date: s.date, value: s.hv_db })) }
  return { unit: 'dB', lines: kind === 'change' ? [hh] : [hh, hv] }
}

export function PointPanel(p: Props) {
  const res = p.selectedId || p.backscatter.status !== 'idle' ? linesFor(p) : { message: 'Pick a place below or click the map.' }

  return (
    <div className="point-panel">
      {'lines' in res ? (
        <>
          <TimeChart
            start={p.dates[0]}
            end={p.dates[p.dates.length - 1]}
            lines={res.lines}
            unit={res.unit}
            event={p.event}
            cursor={p.cursor}
            ticks={p.dates}
            height={180}
            ariaLabel={`${p.pointLabel ?? 'Point'} over time`}
          />
          <div className="chart-key">
            {res.lines.map((l) => (
              <span key={l.id}>
                <i style={{ background: l.color }} />
                {l.label}
              </span>
            ))}
            {p.pointLabel && <span>· {p.pointLabel}</span>}
          </div>
          {p.renderExtra?.(res.lines[0])}
        </>
      ) : (
        <p className={`state-msg${res.error ? ' error' : ''}`}>{res.message}</p>
      )}

      {p.points.length > 0 && (
        <ul className="poi-list" aria-label="Places">
          {p.points.map((pt) => (
            <li key={pt.id}>
              <button type="button" className="btn" aria-pressed={pt.id === p.selectedId} title={pt.note} onClick={() => p.onSelect(pt)}>
                {pt.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
