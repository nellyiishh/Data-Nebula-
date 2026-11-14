import type { Loadable } from '../../../core/api/useJson'
import { TimeChart } from '../../chart/components/TimeChart'
import type { RainSeries } from '../../sites/model/types'

// Owner: Frontend 3 (chart). "Rain loads it": daily rain bars, NISAR passes and the event on
// one axis. With onPassClick it doubles as the explorer's time control.

interface Props {
  rain: Loadable<RainSeries>
  passes: string[]
  event?: { date: string; label: string }
  activePass?: string
  onPassClick?: (date: string) => void
  height?: number
}

export function RainTimeline({ rain, passes, event, activePass, onPassClick, height }: Props) {
  const series = rain.status === 'ready' ? rain.data.series : []
  const dates = [...passes, ...series.map((s) => s.date), ...(event ? [event.date] : [])].sort()
  if (dates.length === 0) return <p className="state-msg">No dates yet.</p>

  return (
    <div>
      <TimeChart
        start={dates[0]}
        end={dates[dates.length - 1]}
        bars={series.map((s) => ({ date: s.date, value: s.mm }))}
        barLabel="mm"
        unit={series.length ? 'mm/day' : undefined}
        event={event}
        ticks={passes}
        activeTick={activePass}
        onTickClick={onPassClick}
        cursor={activePass}
        height={height}
        ariaLabel="Daily rain, radar passes and the event date"
      />
      <div className="chart-key">
        {rain.status === 'ready' && (
          <span>
            <i style={{ background: 'var(--rain)' }} />
            Daily rain
          </span>
        )}
        {rain.status === 'idle' && <span className="state-msg">Rain data not available for this site yet.</span>}
        {rain.status === 'loading' && <span className="state-msg">Loading rain…</span>}
        {rain.status === 'error' && <span className="state-msg error">Rain failed to load: {rain.error}</span>}
        <span>▲ NISAR pass{onPassClick ? ' (click to jump)' : ''}</span>
        {event && (
          <span>
            <i style={{ background: 'var(--danger)' }} />
            Event
          </span>
        )}
      </div>
    </div>
  )
}
