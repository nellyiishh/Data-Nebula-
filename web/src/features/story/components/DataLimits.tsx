import type { SiteDetail } from '../../sites/model/types'
import { AI_USE, DATASETS, GLOBAL_LIMITS, PROJECT } from '../content'
import './story.css'

// Owner: captain (validity). "What we know and what we don't" — the screen NASA judges read.

// The site JSON carries the display settings the images were drawn with; the shared type
// does not declare them yet, so read the one value we need defensively.
function changeThreshold(site: SiteDetail): number | null {
  const display = (site as SiteDetail & { display?: { change_threshold_db?: unknown } }).display
  return typeof display?.change_threshold_db === 'number' ? display.change_threshold_db : null
}

/** Methods as this site's data was actually processed (backend/pipeline on main). */
function methodsFor(site: SiteDetail): string[] {
  const thr = changeThreshold(site)
  const hasScar = site.slope_echo?.overlays.some((o) => o.id === 'scar') ?? false
  return [
    'All radar dates come from one track and frame, so the viewing geometry is the same on every date.',
    `Backscatter change = dB(after) − dB(before), averaged over 3×3 pixels to suppress speckle; pixels beyond ${
      thr === null ? 'a fixed threshold' : `±${thr} dB`
    } are coloured. The threshold is fixed for all pairs, not tuned on a reference area.`,
    'Displacement = −λ / (4π) × unwrapped phase (λ ≈ 0.238 m, L-band), from 80 m phase minus the ionosphere screen; + means toward the satellite. Each pair is relative to the site median and blank where coherence < 0.3. This is line-of-sight motion, one component of the 3D movement, not vertical motion.',
    hasScar
      ? 'The scar outline is drawn on post-event optical imagery and used only to check the radar result, never to make it.'
      : 'No slide outline exists yet, so radar change has not been checked against a mapped scar.',
    'Every date uses one fixed dB stretch. Stretching each image separately (min-max, std-dev or 2–98 % cut, as desktop GIS does by default) would make unchanged ground look changed.',
  ]
}

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

      {se && !v && (
        <div className="panel validation validation--missing">
          <h3>Does the radar agree with the photo?</h3>
          <p>
            <strong>Not checked yet.</strong> There is no mapped outline of the slide, so we cannot say how much of the
            radar change sits on it. Treat the change, coherence and motion maps as places to look, not as confirmed
            landslide signals.
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
            {methodsFor(site).map((m) => (
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
      </div>

      {research && (
        <div className="panel data-limits__passes">
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
        </div>
      )}

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
