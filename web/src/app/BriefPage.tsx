import { useState } from 'react'
import { paths } from '../core/api/client'
import { useRain } from '../features/sites/api'
import type { SiteDetail } from '../features/sites/model/types'
import { DATASETS, GLOBAL_LIMITS, PROJECT } from '../features/story/content'
import './BriefPage.css'

// Field brief: one printable page per site (browser "Print → Save as PDF"). Facts only, with
// dates, sources and limits, so it can be handed to a geologist or emergency service.

const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0)

export function BriefPage({ site }: { site: SiteDetail }) {
  const se = site.slope_echo
  const rain = useRain(site)
  const v = se?.validation
  const demo = site.source === 'demo'
  const [generated] = useState(() => new Date().toISOString().slice(0, 10))

  let rain30: string | null = null
  if (rain.status === 'ready' && se) {
    const end = Date.parse(se.event.date)
    const win = rain.data.series.filter((r) => {
      const t = Date.parse(r.date)
      return t <= end && t > end - 30 * 864e5
    })
    rain30 = `${sum(win.map((r) => r.mm)).toFixed(0)} mm in the 30 days before ${se.event.date} (max ${Math.max(0, ...win.map((r) => r.mm)).toFixed(0)} mm/day)`
  }

  return (
    <article className="brief">
      <div className="brief__actions no-print">
        <button type="button" className="btn" onClick={() => window.print()}>
          Print / save as PDF
        </button>
        <a className="btn" href={`?site=${site.id}`}>
          Back to the map
        </a>
      </div>

      {demo && <p className="brief__demo">DEMO DATA — synthetic, not NISAR measurements. Do not use for decisions.</p>}

      <header>
        <p className="brief__kicker">{PROJECT.name} · Field investigation brief</p>
        <h1>{site.name}</h1>
        <p>
          {se ? `${se.region}, ${se.country} · ` : ''}centre {site.center[1].toFixed(4)}° N, {site.center[0].toFixed(4)}° E
          · generated {generated}
        </p>
      </header>

      <section>
        <h2>Event</h2>
        <p>{se ? `${se.event.date} — ${se.event.label} (source: ${se.event.source.name})` : 'Not recorded.'}</p>
      </section>

      <section>
        <h2>What the radar shows</h2>
        <ul>
          {v && (
            <li>
              Backscatter change {v.pair[0]} → {v.pair[1]} (|ΔHH| &gt; {v.threshold_db} dB): {v.changed_inside_pct}% of pixels
              inside the mapped scar vs {v.changed_outside_pct}% outside.
            </li>
          )}
          <li>
            {site.acquisitions.length} NISAR passes, {site.dates[0]} to {site.dates[site.dates.length - 1]}, band{' '}
            {site.acquisitions[0]?.band}, polarisations {site.acquisitions[0]?.polarizations.join('/')}.
          </li>
          {rain30 && <li>Rain (GPM IMERG, regional ~10 km): {rain30}.</li>}
        </ul>
        {v && (
          <figure className="brief__fig">
            <img src={paths.change(site.id, v.pair[0], v.pair[1])} alt={`Radar change ${v.pair[0]} to ${v.pair[1]}`} />
            <figcaption>
              Radar change {v.pair[0]} → {v.pair[1]}. Red = darker, blue = brighter.
            </figcaption>
          </figure>
        )}
      </section>

      {se?.exposure && (
        <section>
          <h2>Nearby</h2>
          <p>
            {se.exposure.buildings} buildings and {se.exposure.roads_km} km of road within {se.exposure.radius_km} km;{' '}
            {se.exposure.nearest_settlement} at {se.exposure.distance_km} km. {se.exposure.method}
          </p>
        </section>
      )}

      <section>
        <h2>Places checked</h2>
        <table>
          <thead>
            <tr>
              <th>Place</th>
              <th>Lat</th>
              <th>Lon</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {site.points_of_interest.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.lat.toFixed(5)}</td>
                <td>{p.lon.toFixed(5)}</td>
                <td>{p.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Limits</h2>
        <ul>
          {[...GLOBAL_LIMITS, ...(se?.limitations ?? [])].map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
        <p>
          <strong>Recommendation:</strong> satellite change is a reason to look, not a conclusion. A specialist should
          inspect the site on the ground.
        </p>
      </section>

      <section>
        <h2>Data</h2>
        <ul>
          {DATASETS.map((d) => (
            <li key={d.name}>
              {d.name} — {d.provider} ({d.url})
            </li>
          ))}
        </ul>
        <p className="brief__small">{site.attribution}</p>
      </section>
    </article>
  )
}
