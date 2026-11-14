import type { Loadable } from '../../../core/api/useJson'
import type { TimeSeries } from '../../sites/model/types'
import './chart.css'

// Owner: Frontend 3 (chart). Minimal SVG line chart (HH and HV over time) so the slice works
// without a chart library. Swap for a library later if the team agrees (CLAUDE.md §9: ask first).

const W = 320
const H = 160
const PAD = { l: 36, r: 8, t: 8, b: 22 }

interface Props {
  data: Loadable<TimeSeries>
  /** Shown when there is no point selected or static mode has no data for the clicked spot. */
  emptyHint: string
  currentDate?: string
}

export function PointChart({ data, emptyHint, currentDate }: Props) {
  if (data.status === 'idle') return <p className="state-msg">{emptyHint}</p>
  if (data.status === 'loading') return <p className="state-msg">Loading time series…</p>
  if (data.status === 'error') return <p className="state-msg error">Could not load time series: {data.error}</p>

  const s = data.data.series
  if (s.length === 0) return <p className="state-msg">No observations at this point.</p>

  const values = s.flatMap((d) => [d.hh_db, d.hv_db])
  const min = Math.floor(Math.min(...values) - 1)
  const max = Math.ceil(Math.max(...values) + 1)
  const x = (i: number) => PAD.l + (i / Math.max(1, s.length - 1)) * (W - PAD.l - PAD.r)
  const y = (v: number) => PAD.t + ((max - v) / (max - min)) * (H - PAD.t - PAD.b)
  const line = (key: 'hh_db' | 'hv_db') => s.map((d, i) => `${i ? 'L' : 'M'}${x(i)},${y(d[key])}`).join('')
  const cur = s.findIndex((d) => d.date === currentDate)

  return (
    <figure className="point-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Backscatter over time at the selected point">
        {[min, (min + max) / 2, max].map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="grid" />
            <text x={PAD.l - 4} y={y(v) + 3} className="axis" textAnchor="end">
              {Math.round(v)}
            </text>
          </g>
        ))}
        {cur >= 0 && <line x1={x(cur)} x2={x(cur)} y1={PAD.t} y2={H - PAD.b} className="cursor" />}
        <path d={line('hh_db')} className="hh" />
        <path d={line('hv_db')} className="hv" />
        {s.map((d, i) => (
          <g key={d.date}>
            <circle cx={x(i)} cy={y(d.hh_db)} r={2.5} className="hh-dot" />
            <circle cx={x(i)} cy={y(d.hv_db)} r={2.5} className="hv-dot" />
          </g>
        ))}
        <text x={x(0)} y={H - 6} className="axis">
          {s[0].date.slice(5)}
        </text>
        <text x={x(s.length - 1)} y={H - 6} className="axis" textAnchor="end">
          {s[s.length - 1].date.slice(5)}
        </text>
      </svg>
      <figcaption className="muted">
        <span className="key hh">HH</span> <span className="key hv">HV</span> backscatter, dB ·{' '}
        {data.data.lat.toFixed(3)}, {data.data.lon.toFixed(3)}
      </figcaption>
    </figure>
  )
}
