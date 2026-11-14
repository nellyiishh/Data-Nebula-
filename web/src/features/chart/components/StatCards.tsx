import type { Loadable } from '../../../core/api/useJson'
import type { Stats } from '../../sites/model/types'
import './chart.css'

// Owner: Frontend 3 (chart). Headline numbers: change between the selected before/after dates.

interface Props {
  stats: Loadable<Stats>
  from: string
  to: string
}

const fmt = (v: number, unit: string) => `${v > 0 ? '+' : ''}${v.toFixed(1)} ${unit}`

export function StatCards({ stats, from, to }: Props) {
  if (stats.status === 'loading' || stats.status === 'idle') return <p className="state-msg">Loading numbers…</p>
  if (stats.status === 'error') return <p className="state-msg error">Could not load numbers: {stats.error}</p>

  const a = stats.data.series.find((d) => d.date === from)
  const b = stats.data.series.find((d) => d.date === to)
  if (!a || !b) return <p className="state-msg">No numbers for these dates yet.</p>

  return (
    <div className="stat-cards">
      <Card label="Water area" value={`${b.water_km2.toFixed(1)} km²`} delta={fmt(b.water_km2 - a.water_km2, 'km²')} />
      <Card label="Mean HH" value={`${b.mean_hh_db.toFixed(1)} dB`} delta={fmt(b.mean_hh_db - a.mean_hh_db, 'dB')} />
      <Card label="Mean HV" value={`${b.mean_hv_db.toFixed(1)} dB`} delta={fmt(b.mean_hv_db - a.mean_hv_db, 'dB')} />
      <p className="muted stat-cards__range">
        {from} → {to}
      </p>
    </div>
  )
}

function Card({ label, value, delta }: { label: string; value: string; delta: string }) {
  return (
    <div className="stat-card">
      <div className="muted">{label}</div>
      <div className="stat-card__value">{value}</div>
      <div className="stat-card__delta">{delta}</div>
    </div>
  )
}
