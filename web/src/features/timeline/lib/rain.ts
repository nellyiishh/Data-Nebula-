import type { RainSeries } from '../../sites/model/types'

/** Total and peak daily rain in the `days` before (and including) `date`. */
export function rainBefore(rain: RainSeries, date: string, days = 30) {
  const end = Date.parse(date)
  const win = rain.series.filter((r) => {
    const t = Date.parse(r.date)
    return t <= end && t > end - days * 864e5
  })
  return {
    days,
    total: win.reduce((s, r) => s + r.mm, 0),
    peak: win.reduce((m, r) => Math.max(m, r.mm), 0),
    wetDays: win.filter((r) => r.mm >= 1).length,
  }
}
