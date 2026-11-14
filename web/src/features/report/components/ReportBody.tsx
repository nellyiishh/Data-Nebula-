import { paths } from '../../../core/api/client'
import type { Loadable } from '../../../core/api/useJson'
import type { RainSeries, SiteDetail } from '../../sites/model/types'
import { DATASETS, GLOBAL_LIMITS, PROJECT } from '../../story/content'
import { rainBefore } from '../../timeline/lib/rain'
import './report.css'

// Owner: captain. The investigation report: facts only, with dates, sources and limits, so it
// can be handed to a geologist or an emergency service. Used inline (screen 08) and as the
// printable page (?view=brief).

interface Props {
  site: SiteDetail
  rain: Loadable<RainSeries>
  generated: string
  /** Short version for the on-page preview. */
  compact?: boolean
}

export function ReportBody({ site, rain, generated, compact }: Props) {
  const se = site.slope_echo
  const v = se?.validation
  const r = rain.status === 'ready' && se ? rainBefore(rain.data, se.event.date) : null

  return (
    <div className={`report${compact ? ' report--compact' : ''}`}>
      {site.source === 'demo' && <p className="report__demo">DEMO DATA — synthetic, not NISAR measurements. Do not use for decisions.</p>}

      <header>
        <p className="report__kicker">{PROJECT.name} · Investigation report</p>
        <h3 className="report__title">{site.name}</h3>
        <p>
          {se ? `${se.region}, ${se.country} · ` : ''}centre {site.center[1].toFixed(4)}° N, {site.center[0].toFixed(4)}° E · generated{' '}
          {generated}
        </p>
      </header>

      <section>
        <h4>Event</h4>
        <p>{se ? `${se.event.date} — ${se.event.label} (source: ${se.event.source.name})` : 'Not recorded.'}</p>
      </section>

      <section>
        <h4>What the radar shows</h4>
        <ul>
          {v && (
            <li>
              Backscatter change {v.pair[0]} → {v.pair[1]} (|ΔHH| &gt; {v.threshold_db} dB): {v.changed_inside_pct}% of pixels inside
              the mapped scar vs {v.changed_outside_pct}% outside.
            </li>
          )}
          <li>
            {site.acquisitions.length} NISAR passes, {site.dates[0]} to {site.dates[site.dates.length - 1]}, band {site.acquisitions[0]?.band},
            polarisations {site.acquisitions[0]?.polarizations.join('/')}.
          </li>
          {r && (
            <li>
              Rain (GPM IMERG, regional ~10 km): {r.total.toFixed(0)} mm in the {r.days} days before the event, peak {r.peak.toFixed(0)}{' '}
              mm/day, {r.wetDays} wet days.
            </li>
          )}
        </ul>
        {v && !compact && (
          <figure className="report__fig">
            <img src={paths.change(site.id, v.pair[0], v.pair[1])} alt={`Radar change ${v.pair[0]} to ${v.pair[1]}`} />
            <figcaption>
              Radar change {v.pair[0]} → {v.pair[1]}. Red = darker, blue = brighter.
            </figcaption>
          </figure>
        )}
      </section>

      {se?.exposure && (
        <section>
          <h4>Nearby</h4>
          <p>
            {se.exposure.buildings} buildings and {se.exposure.roads_km} km of road within {se.exposure.radius_km} km;{' '}
            {se.exposure.nearest_settlement} at {se.exposure.distance_km} km. {compact ? '' : se.exposure.method}
          </p>
        </section>
      )}

      {se?.catalog && se.catalog.length > 0 && (
        <section>
          <h4>Registered events</h4>
          <ul>
            {se.catalog.map((e) => (
              <li key={`${e.date}-${e.name}`}>
                {e.date} · {e.type} · {e.name} ({e.source.name})
              </li>
            ))}
          </ul>
        </section>
      )}

      {!compact && (
        <section>
          <h4>Places checked</h4>
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
      )}

      <section>
        <h4>Limits and recommendation</h4>
        {!compact && (
          <ul>
            {[...GLOBAL_LIMITS, ...(se?.limitations ?? [])].map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        )}
        <p>
          <strong>Recommendation:</strong> satellite change is a reason to look, not a conclusion. A specialist should inspect the site on
          the ground.
        </p>
      </section>

      {!compact && (
        <section>
          <h4>Data</h4>
          <ul>
            {DATASETS.map((d) => (
              <li key={d.name}>
                {d.name} — {d.provider} ({d.url})
              </li>
            ))}
          </ul>
          <p className="report__small">{site.attribution}</p>
        </section>
      )}
    </div>
  )
}
