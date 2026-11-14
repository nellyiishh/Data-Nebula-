import type { SiteDetail } from '../../sites/model/types'
import { AI_USE, DATASETS, GLOBAL_LIMITS, METHODS, PROJECT } from '../content'
import './story.css'

// Owner: captain (validity). "What we know and what we don't" — the screen NASA judges read.

export function DataLimits({ site, research }: { site: SiteDetail; research: boolean }) {
  const se = site.slope_echo
  const v = se?.validation
  return (
    <div className="data-limits">
      {v && (
        <div className="panel validation">
          <h3>Does the radar agree with the photo?</h3>
          <div className="validation__nums">
            <div>
              <strong>{v.changed_inside_pct}%</strong>
              <span className="muted">of pixels inside the mapped scar changed</span>
            </div>
            <div>
              <strong>{v.changed_outside_pct}%</strong>
              <span className="muted">of pixels outside it changed</span>
            </div>
          </div>
          <p className="muted">
            A big gap between the two numbers means the radar change really sits on the landslide, not everywhere.
          </p>
          <p className="muted">
            {`${v.method} Pair: ${v.pair[0]} → ${v.pair[1]}, threshold ${v.threshold_db} dB.`}
          </p>
        </div>
      )}

      <div className="panel">
        <h3>What we don't know / limits</h3>
        <ul>
          {[...GLOBAL_LIMITS, ...(se?.limitations ?? [])].map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </div>

      {research && (
        <div className="panel">
          <h3>Methods</h3>
          <ul>
            {METHODS.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="panel">
        <h3>Data we used</h3>
        <ul className="datasets">
          {DATASETS.map((d) => (
            <li key={d.name}>
              <a href={d.url} target="_blank" rel="noreferrer">
                {d.name}
              </a>{' '}
              <span className="muted">
                · {d.provider} · {d.usedFor}
              </span>
            </li>
          ))}
        </ul>
        {research && (
          <>
            <h3>Radar passes in this view</h3>
            <table className="passes">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Band</th>
                  <th>Pol.</th>
                  <th>Granule</th>
                </tr>
              </thead>
              <tbody>
                {site.acquisitions.map((a) => (
                  <tr key={a.date}>
                    <td>{a.date}</td>
                    <td>{a.band}</td>
                    <td>{a.polarizations.join(', ')}</td>
                    <td className="passes__granule">{a.granule_id ?? <span className="muted">demo — none</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <div className="panel">
        <h3>Use of AI</h3>
        <p className="muted">{AI_USE}</p>
        <h3>Open source</h3>
        <p>
          <a href={PROJECT.repo} target="_blank" rel="noreferrer">
            {PROJECT.repo}
          </a>
        </p>
      </div>
    </div>
  )
}
