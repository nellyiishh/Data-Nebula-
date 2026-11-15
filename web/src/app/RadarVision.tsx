import { useMemo, useState } from 'react'
import { LazyMount } from '../core/ui/LazyMount'
import { SwipeCompare } from '../features/compare/components/SwipeCompare'
import { siteFileUrl } from '../features/sites/api'
import { buildLayers, frameIndexFor } from '../features/sites/model/layers'
import type { SiteDetail } from '../features/sites/model/types'
import { BandGuide } from '../features/story/components/BandGuide'
import { Screen } from '../features/story/components/Screen'
import { CAMERA_VS_RADAR, RADAR_IS_NOT } from '../features/story/content'
import { toMapOverlays } from './mapOverlays'
import './RadarVision.css'

// Screen 04 "Radar Vision": the same place and date through a camera and through radar.

interface Props {
  site: SiteDetail
  research: boolean
}

export function RadarVision({ site, research }: Props) {
  const se = site.slope_echo
  const layers = useMemo(() => buildLayers(site), [site])
  const optical = layers.find((l) => l.kind === 'optical')
  const radarChoices = layers.filter((l) => l.kind === 'backscatter' || l.kind === 'coherence')
  const [radarId, setRadarId] = useState(radarChoices[0]?.id)
  const radar = radarChoices.find((l) => l.id === radarId) ?? radarChoices[0]
  const [dateIdx, setDateIdx] = useState(Math.max(0, site.dates.length - 1))
  const date = site.dates[dateIdx]

  const scar = se?.overlays.filter((o) => o.id === 'scar') ?? []
  const { vectors } = toMapOverlays(site, scar)
  const demo = site.source === 'demo' ? ' · DEMO' : ''

  const o = optical?.frames[frameIndexFor(optical, date)]
  const r = radar?.frames[frameIndexFor(radar, date)]
  const raw = se?.raw_example
  // The camera frame is the nearest optical scene on or before the radar date (the first one
  // if none is earlier), so say how far apart the two pictures really are.
  const gapDays = o && r ? Math.round((Date.parse(r.date) - Date.parse(o.date)) / 86_400_000) : null
  const gapText =
    gapDays === null
      ? null
      : gapDays === 0
        ? 'Same day.'
        : `Camera is ${Math.abs(gapDays)} day${Math.abs(gapDays) === 1 ? '' : 's'} ${gapDays > 0 ? 'before' : 'after'} the radar.`

  return (
    <Screen id="radar-vision" n={4} title="Radar Vision" text={se?.story.radar} research={research} wide>
      <div className="radar-vision">
        <div className="radar-vision__map">
          {o && r ? (
            <LazyMount className="radar-vision__map-inner">
              <SwipeCompare
                corners={site.corners}
                left={{ imageUrl: o.url, badge: `Camera · ${o.label}${demo}` }}
                right={{ imageUrl: r.url, badge: `Radar ${radar.title} · ${r.label}${demo}` }}
                vectors={vectors}
              />
            </LazyMount>
          ) : (
            <p className="state-msg">Optical imagery not available for this site yet.</p>
          )}
        </div>
        <aside className="panel radar-vision__side">
          <h3>Same place, nearest dates</h3>
          <label className="explorer__pair">
            Radar date
            <select value={dateIdx} onChange={(e) => setDateIdx(Number(e.target.value))}>
              {site.dates.map((d, i) => (
                <option key={d} value={i}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <div className="layer-controls__row" role="group" aria-label="Radar layer">
            {radarChoices.map((l) => (
              <button key={l.id} type="button" className="btn" aria-pressed={l.id === radar?.id} onClick={() => setRadarId(l.id)}>
                {l.title}
              </button>
            ))}
          </div>
          {o && r && (
            <p className="radar-vision__dates" aria-live="polite">
              <span>
                Camera <span className="radar-vision__val">{o.label}</span>
              </span>
              <span>
                Radar <span className="radar-vision__val">{r.label}</span>
              </span>
              <span className="muted">{gapText}</span>
            </p>
          )}
          <p className="muted radar-vision__hint">
            Drag the divider. The camera picture is the nearest NASA HLS optical scene on or before the radar date, so the
            two can be days apart; differences between them are not all change on the ground.
          </p>
          <h3>What radar is not</h3>
          <ul className="not-list">
            {RADAR_IS_NOT.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </aside>
      </div>

      <div className="radar-vision__cards">
        <div className="panel">
          <h3>Camera vs radar</h3>
          <table className="vs-table">
            <thead>
              <tr>
                <th />
                <th>Camera (optical)</th>
                <th>Radar (NISAR)</th>
              </tr>
            </thead>
            <tbody>
              {CAMERA_VS_RADAR.map((row) => (
                <tr key={row.title}>
                  <th scope="row">{row.title}</th>
                  <td>{row.camera}</td>
                  <td>{row.radar}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h3>Why L-band</h3>
          <BandGuide />
        </div>
        {raw && (
          <div className="panel">
            <h3>Why raw radar looks black</h3>
            <div className="stretch-demo">
              <figure>
                <img src={siteFileUrl(site.id, raw.linear)} alt={`Raw linear radar power, ${raw.date}`} loading="lazy" />
                <figcaption>Raw power, as stored in the file</figcaption>
              </figure>
              <figure>
                <img src={siteFileUrl(site.id, raw.db)} alt={`Radar in decibels, stretched, ${raw.date}`} loading="lazy" />
                <figcaption>In decibels, fixed stretch</figcaption>
              </figure>
            </div>
            <p className="muted radar-vision__hint">
              {research
                ? 'Echo strength spans orders of magnitude, so a few bright pixels squash the rest to black. Converting to dB (10·log₁₀) and applying one fixed stretch to every date keeps the frames comparable; a per-image stretch would invent change.'
                : 'Radar echoes range from very weak to very strong. We convert them to a log scale (decibels) so the whole slope becomes visible.'}
            </p>
          </div>
        )}
      </div>
    </Screen>
  )
}
