import { useId } from 'react'
import './chart.css'

// Owner: Frontend 3 (chart). One SVG time axis for every chart on the page, so rain, radar
// passes and the event line always line up. No chart library (CLAUDE.md §9: ask first).

export interface TimeLine {
  id: string
  label: string
  color: string
  points: { date: string; value: number | null }[]
}

interface Props {
  start: string
  end: string
  bars?: { date: string; value: number }[]
  barLabel?: string
  lines?: TimeLine[]
  unit?: string
  /** Red vertical marker, e.g. the landslide date. */
  event?: { date: string; label: string }
  /** Radar passes along the bottom; clickable when onTickClick is set. */
  ticks?: string[]
  activeTick?: string
  onTickClick?: (date: string) => void
  cursor?: string
  height?: number
  /** Logical width of the drawing; use a wider value for short, full-width strips. */
  width?: number
  ariaLabel: string
}

const DEFAULT_W = 640
const PAD = { l: 40, r: 10, t: 24, b: 34 }
const DAY = 864e5

const t = (d: string) => Date.parse(d)
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function niceRange(values: number[]): [number, number] {
  if (values.length === 0) return [0, 1]
  let min = Math.min(...values)
  let max = Math.max(...values)
  if (min === max) [min, max] = [min - 1, max + 1]
  const pad = (max - min) * 0.1
  return [min - pad, max + pad]
}

export function TimeChart(p: Props) {
  const clipId = useId()
  const H = p.height ?? 200
  const W = p.width ?? DEFAULT_W
  const t0 = t(p.start)
  const t1 = t(p.end)
  const x = (d: string) => PAD.l + ((t(d) - t0) / Math.max(DAY, t1 - t0)) * (W - PAD.l - PAD.r)
  const plotH = H - PAD.t - PAD.b
  const bottom = PAD.t + plotH

  const lineValues = (p.lines ?? []).flatMap((l) => l.points.map((pt) => pt.value).filter((v): v is number => v !== null))
  const [lmin, lmax] = niceRange(lineValues)
  const ly = (v: number) => PAD.t + ((lmax - v) / (lmax - lmin)) * plotH

  const barMax = Math.max(1, ...(p.bars ?? []).map((b) => b.value))
  const by = (v: number) => bottom - (v / barMax) * plotH
  const barW = Math.max(1.5, ((W - PAD.l - PAD.r) / Math.max(1, (t1 - t0) / DAY)) * 0.7)

  const axis = lineValues.length
    ? [lmin, (lmin + lmax) / 2, lmax].map((v) => ({ y: ly(v), label: v.toFixed(Math.abs(lmax - lmin) < 3 ? 1 : 0) }))
    : p.bars
      ? [0, barMax / 2, barMax].map((v) => ({ y: by(v), label: v.toFixed(0) }))
      : []

  const months: { x: number; label: string }[] = []
  for (let d = new Date(t0); d.getTime() <= t1; d.setUTCMonth(d.getUTCMonth() + 1, 1)) {
    const iso = d.toISOString().slice(0, 10)
    if (t(iso) >= t0) months.push({ x: x(iso), label: MONTHS[d.getUTCMonth()] })
  }

  return (
    <svg className="time-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.ariaLabel}>
      <defs>
        <clipPath id={clipId}>
          <rect x={PAD.l} y={PAD.t - 2} width={W - PAD.l - PAD.r} height={plotH + 4} />
        </clipPath>
      </defs>
      {axis.map((a) => (
        <g key={a.y}>
          <line x1={PAD.l} x2={W - PAD.r} y1={a.y} y2={a.y} className="grid" />
          <text x={PAD.l - 6} y={a.y + 3} className="axis" textAnchor="end">
            {a.label}
          </text>
        </g>
      ))}
      {p.unit && (
        <text x={4} y={11} className="axis">
          {p.unit}
        </text>
      )}
      {months.map((m) => (
        <text key={m.x} x={m.x + 2} y={H - 4} className="axis">
          {m.label}
        </text>
      ))}

      <g clipPath={`url(#${clipId})`}>
        {p.bars?.map((b) =>
          b.value > 0 ? (
            <rect key={b.date} x={x(b.date) - barW / 2} y={by(b.value)} width={barW} height={bottom - by(b.value)} className="bar">
              <title>{`${b.date}: ${b.value} ${p.barLabel ?? ''}`}</title>
            </rect>
          ) : null,
        )}
        {p.lines?.map((l) => {
          const pts = l.points.filter((pt) => pt.value !== null) as { date: string; value: number }[]
          const d = pts.map((pt, i) => `${i ? 'L' : 'M'}${x(pt.date)},${ly(pt.value)}`).join('')
          return (
            <g key={l.id} style={{ color: l.color }}>
              <path d={d} className="line" />
              {pts.map((pt) => (
                <circle key={pt.date} cx={x(pt.date)} cy={ly(pt.value)} r={3} className="dot">
                  <title>{`${l.label} ${pt.date}: ${pt.value}`}</title>
                </circle>
              ))}
            </g>
          )
        })}
      </g>

      {p.event && (
        <g className="event">
          <line x1={x(p.event.date)} x2={x(p.event.date)} y1={PAD.t - 4} y2={bottom} />
          {/* Flip the label to the left of the line when it would run off the right edge. */}
          <text
            x={x(p.event.date) + (x(p.event.date) > W * 0.55 ? -4 : 4)}
            y={PAD.t + 8}
            textAnchor={x(p.event.date) > W * 0.55 ? 'end' : 'start'}
          >
            {p.event.label}
          </text>
        </g>
      )}
      {p.cursor && <line x1={x(p.cursor)} x2={x(p.cursor)} y1={PAD.t} y2={bottom} className="cursor" />}

      {p.ticks?.map((d) => {
        const active = d === p.activeTick
        const cls = `tick${active ? ' active' : ''}${p.onTickClick ? ' clickable' : ''}`
        return (
          <g
            key={d}
            className={cls}
            role={p.onTickClick ? 'button' : undefined}
            tabIndex={p.onTickClick ? 0 : undefined}
            aria-label={p.onTickClick ? `Radar pass ${d}` : undefined}
            onClick={() => p.onTickClick?.(d)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') p.onTickClick?.(d)
            }}
          >
            <path d={`M${x(d)},${bottom + 3} l5,8 h-10 z`} />
            <title>{`NISAR pass ${d}`}</title>
          </g>
        )
      })}
    </svg>
  )
}
