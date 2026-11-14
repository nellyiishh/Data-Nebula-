import { useState } from 'react'
import type { FormEvent } from 'react'
import { Brand } from '../core/ui/Brand'
import { EventCatalog } from '../features/exposure/components/EventCatalog'
import { ExposureCard } from '../features/exposure/components/ExposureCard'
import { ReportBody } from '../features/report/components/ReportBody'
import type { SiteDetail, SiteSummary } from '../features/sites/model/types'
import { SourceLink } from '../features/story/components/Screen'
import { PROJECT } from '../features/story/content'
import { rainBefore } from '../features/timeline/lib/rain'
import { DatePairControls, ExplorerMap, LayersPanel, PointBlock, TimelineBlock } from './ExplorerParts'
import { useExplorerState } from './useExplorerState'
import type { ExplorerState } from './useExplorerState'
import './TimeMachine.css'
import './Workspace.css'

// TRACE workspace (?view=app): the analysis tool. Four zones — top bar (logo, area search, date),
// left (map layers), centre (map), right (selected area), bottom (observation timeline) — and
// one core scenario in five steps. Shares state and parts with the story's Time Machine.

type Params = Record<string, string | undefined>
interface Props {
  site: SiteDetail
  sites: SiteSummary[]
  research: boolean
  params: Params
  setParams: (p: Params) => void
}

const STEPS = [
  { id: 'explore', title: 'Explore map', hint: 'Choose the area and look around' },
  { id: 'change', title: 'Change analysis', hint: 'Compare Date A with Date B' },
  { id: 'rain', title: 'Rainfall context', hint: 'What the weather did before' },
  { id: 'infra', title: 'Infrastructure', hint: 'What is near the slope' },
  { id: 'report', title: 'Investigation report', hint: 'Facts, sources, limits' },
] as const
type StepId = (typeof STEPS)[number]['id']

export function Workspace({ site, sites, research, params, setParams }: Props) {
  const step = (STEPS.find((st) => st.id === params.step)?.id ?? 'explore') as StepId
  const s = useExplorerState(site, params, setParams, { extraOverlays: step === 'infra' ? ['exposure', 'aoi'] : [] })
  // Panels start open on wide screens, closed (as drawers) on phones and tablets.
  const [leftOpen, setLeftOpen] = useState(() => window.matchMedia('(min-width: 1001px)').matches)
  const [rightOpen, setRightOpen] = useState(() => window.matchMedia('(min-width: 1001px)').matches)
  const [generated] = useState(() => new Date().toISOString().slice(0, 10))
  const dateLabel = s.compare ? `${s.layer.frames[s.aIdx].label} ↔ ${s.layer.frames[s.bIdx].label}` : s.frame?.label

  const goStep = (id: StepId) => setParams({ step: id === 'explore' ? undefined : id, cmp: id === 'change' ? '1' : params.cmp })

  return (
    <div className={`ws${leftOpen ? ' ws--left' : ''}${rightOpen ? ' ws--right' : ''}`}>
      <header className="ws__top">
        <Brand name={PROJECT.name} subtitle={PROJECT.fullName} href={`?site=${site.id}`} />
        <AreaSearch site={site} sites={sites} s={s} setParams={setParams} />
        <span className="ws__date mono" title="Observation shown on the map">
          {dateLabel}
        </span>
        {site.source === 'demo' && <span className="ws__demo">DEMO DATA</span>}
        <div className="ws__actions">
          <button type="button" className="btn ws__drawer-btn" aria-pressed={leftOpen} onClick={() => setLeftOpen((v) => !v)}>
            Layers
          </button>
          <button type="button" className="btn ws__drawer-btn" aria-pressed={rightOpen} onClick={() => setRightOpen((v) => !v)}>
            Details
          </button>
          <a className="btn" href={`?site=${site.id}`}>
            Story
          </a>
        </div>
      </header>

      <nav className="ws__steps" aria-label="Investigation steps">
        <ol>
          {STEPS.map((st, i) => (
            <li key={st.id}>
              <button type="button" aria-current={st.id === step ? 'step' : undefined} onClick={() => goStep(st.id)}>
                <span className="ws__step-n mono">{i + 1}</span>
                <span>
                  <strong>{st.title}</strong>
                  <span className="muted">{st.hint}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <aside className="ws__left" aria-label="Map layers">
        <PanelHead title="Map layers" onClose={() => setLeftOpen(false)} />
        <LayersPanel s={s} research={research} />
      </aside>

      <main className="ws__map">
        <ExplorerMap site={site} s={s} />
      </main>

      <aside className="ws__right" aria-label="Selected area">
        <PanelHead title={STEPS.find((st) => st.id === step)!.title} onClose={() => setRightOpen(false)} />
        <RightPanel step={step} site={site} s={s} research={research} generated={generated} />
        <StepNav step={step} goStep={goStep} />
      </aside>

      <footer className="ws__bottom" aria-label="Observation timeline">
        <span className="ws__bottom-title">Observation timeline</span>
        <TimelineBlock site={site} s={s} height={120} width={1500} />
      </footer>
    </div>
  )
}

function PanelHead({ title, onClose }: { title: string; onClose: () => void }) {
  return (
    <div className="ws__panel-head">
      <h2>{title}</h2>
      <button type="button" className="btn ws__close" aria-label={`Hide ${title}`} onClick={onClose}>
        ×
      </button>
    </div>
  )
}

function StepNav({ step, goStep }: { step: StepId; goStep: (id: StepId) => void }) {
  const i = STEPS.findIndex((st) => st.id === step)
  const next = STEPS[i + 1]
  return next ? (
    <button type="button" className="btn btn--primary ws__next" onClick={() => goStep(next.id)}>
      Next: {next.title} →
    </button>
  ) : null
}

/** Area search: a site name, a place name, or "lat, lon". */
function AreaSearch({ site, sites, s, setParams }: { site: SiteDetail; sites: SiteSummary[]; s: ExplorerState; setParams: (p: Params) => void }) {
  const [q, setQ] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const text = q.trim().toLowerCase()
    if (!text) return
    const coords = /^(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)$/.exec(text)
    const hitSite = sites.find((x) => x.name.toLowerCase().includes(text))
    const hitPoi = site.points_of_interest.find((p) => p.name.toLowerCase().includes(text))
    if (coords) s.actions.clickMap(Number(coords[2]), Number(coords[1]))
    else if (hitPoi) s.actions.selectPoi(hitPoi)
    else if (hitSite) setParams({ site: hitSite.id, layer: undefined, f: undefined, pt: undefined, a: undefined, b: undefined })
    else return setMsg('Not found in prepared areas')
    setMsg(null)
    setQ('')
  }
  return (
    <form className="ws__search" role="search" onSubmit={onSubmit}>
      <input
        list="ws-areas"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search area, place or lat, lon"
        aria-label="Search study area, place or coordinates"
      />
      <datalist id="ws-areas">
        {sites.map((x) => (
          <option key={x.id} value={x.name} />
        ))}
        {site.points_of_interest.map((p) => (
          <option key={p.id} value={p.name} />
        ))}
      </datalist>
      {msg && (
        <span className="ws__search-msg" role="status">
          {msg}
        </span>
      )}
    </form>
  )
}

interface RightProps {
  step: StepId
  site: SiteDetail
  s: ExplorerState
  research: boolean
  generated: string
}

function RightPanel({ step, site, s, research, generated }: RightProps) {
  const se = site.slope_echo
  if (step === 'change')
    return (
      <>
        <section className="ws__card">
          <h3>Date A ↔ Date B</h3>
          <DatePairControls s={s} />
          {se?.validation && (
            <p className="muted ws__small">
              Reference pair {se.validation.pair[0]} → {se.validation.pair[1]}: {se.validation.changed_inside_pct}% of pixels inside the
              mapped scar changed by more than {se.validation.threshold_db} dB, {se.validation.changed_outside_pct}% outside.
            </p>
          )}
        </section>
        <section className="ws__card">
          <h3>{s.pointTitle}</h3>
          <PointBlock site={site} s={s} />
        </section>
      </>
    )
  if (step === 'rain') {
    const r = s.rain.status === 'ready' && se ? rainBefore(s.rain.data, se.event.date) : null
    return (
      <section className="ws__card">
        <h3>Before the event</h3>
        {r ? (
          <dl className="ws__facts">
            <dt>Rain, {r.days} days before</dt>
            <dd className="mono">{r.total.toFixed(0)} mm</dd>
            <dt>Wettest day</dt>
            <dd className="mono">{r.peak.toFixed(0)} mm</dd>
            <dt>Days with rain</dt>
            <dd className="mono">{r.wetDays}</dd>
          </dl>
        ) : (
          <p className="state-msg">Rain data not available yet.</p>
        )}
        {se?.rain && (
          <p className="muted ws__small">
            {se.rain.note} <SourceLink source={se.rain.source} />
          </p>
        )}
        <p className="muted ws__small">Rain before a slide does not prove it caused it. Use the timeline below to compare it with radar passes.</p>
      </section>
    )
  }
  if (step === 'infra')
    return (
      <>
        <section className="ws__card">
          <h3>Near the slope</h3>
          <ExposureCard exposure={se?.exposure ?? null} research={research} />
        </section>
        <section className="ws__card">
          <h3>Registered events</h3>
          <EventCatalog catalog={se?.catalog} />
        </section>
      </>
    )
  if (step === 'report')
    return (
      <section className="ws__card">
        <ReportBody site={site} rain={s.rain} generated={generated} compact />
        <a className="btn btn--primary ws__next" href={`?site=${site.id}&view=brief`} target="_blank" rel="noreferrer">
          Generate full report (PDF)
        </a>
      </section>
    )
  return <ObservationDetails site={site} s={s} />
}

/** "Selected area — observation details": each row answers one question, from loaded data only. */
function ObservationDetails({ site, s }: { site: SiteDetail; s: ExplorerState }) {
  const se = site.slope_echo
  const acq = site.acquisitions[0]
  const r = s.rain.status === 'ready' && se ? rainBefore(s.rain.data, se.event.date) : null
  const v = se?.validation
  return (
    <>
      <section className="ws__card">
        <h3>Study area</h3>
        <p className="ws__area">{site.name}</p>
        <p className="muted mono ws__small">
          {se ? `${se.region}, ${se.country} · ` : ''}
          {site.center[1].toFixed(4)}° N {site.center[0].toFixed(4)}° E
        </p>
        <dl className="ws__facts">
          <dt>Observation date</dt>
          <dd className="mono">{s.compare ? `${s.layer.frames[s.aIdx].label} / ${s.layer.frames[s.bIdx].label}` : s.frame?.label}</dd>
          <dt>Data source</dt>
          <dd>
            NISAR {s.layer.title}
            <span className="muted mono">
              {' '}
              · {acq?.band}-band {acq?.polarizations.join('/')} · {site.acquisitions.length} passes
            </span>
          </dd>
          <dt>Rainfall context</dt>
          <dd>{r ? `${r.total.toFixed(0)} mm in ${r.days} days before ${se!.event.date} (IMERG)` : 'not loaded'}</dd>
          <dt>Nearby infrastructure</dt>
          <dd>{se?.exposure ? `${se.exposure.buildings} buildings, ${se.exposure.roads_km} km road within ${se.exposure.radius_km} km (OSM)` : 'not available'}</dd>
        </dl>
      </section>
      <section className="ws__card ws__summary">
        <h3>Investigation summary</h3>
        <p>
          {v
            ? `Observable change in the available radar data between ${v.pair[0]} and ${v.pair[1]}: ${v.changed_inside_pct}% of pixels inside the mapped scar vs ${v.changed_outside_pct}% outside. Further examination is recommended before drawing conclusions.`
            : 'No change analysis for this area yet.'}
        </p>
      </section>
      <section className="ws__card">
        <h3>Places</h3>
        <ul className="poi-list">
          {site.points_of_interest.map((p) => (
            <li key={p.id}>
              <button type="button" className="btn" aria-pressed={p.id === s.poi?.id} title={p.note} onClick={() => s.actions.selectPoi(p)}>
                {p.name}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
