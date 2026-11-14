import { useState } from 'react'
import { paths } from '../core/api/client'
import { SarMap } from '../core/map/SarMap'
import { HeroBackdrop } from '../core/ui/HeroBackdrop'
import { LazyMount } from '../core/ui/LazyMount'
import { EventCatalog } from '../features/exposure/components/EventCatalog'
import { ExposureCard } from '../features/exposure/components/ExposureCard'
import { ReportBody } from '../features/report/components/ReportBody'
import { useRain } from '../features/sites/api'
import type { SiteDetail, SiteSummary } from '../features/sites/model/types'
import { DataLimits } from '../features/story/components/DataLimits'
import { Screen, SourceLink } from '../features/story/components/Screen'
import { PROJECT } from '../features/story/content'
import { RainTimeline } from '../features/timeline/components/RainTimeline'
import { rainBefore } from '../features/timeline/lib/rain'
import { RadarVision } from './RadarVision'
import { TimeMachine } from './TimeMachine'
import { toMapOverlays } from './mapOverlays'
import './SitePage.css'

// Composition root for one site: the 9-screen story agreed by the team
// (Hero, Explore, Earth Time Machine, Radar Vision, Rainfall, Earth Impact, Global Stories,
// Investigation Report, Data & Science). App mounts it with key={site.id}.

// "Rain loads it. Radar hears it. People live below it." → one line per sentence.
const taglineLines = PROJECT.tagline.split(/(?<=\.)\s+/)

type Params = Record<string, string | undefined>
interface Props {
  site: SiteDetail
  sites: SiteSummary[]
  research: boolean
  params: Params
  setParams: (p: Params) => void
}

export function SitePage({ site, sites, research, params, setParams }: Props) {
  const se = site.slope_echo
  const rain = useRain(site)
  const [generated] = useState(() => new Date().toISOString().slice(0, 10))
  const impactOverlays = se ? toMapOverlays(site, se.overlays.filter((o) => ['exposure', 'aoi', 'scar'].includes(o.id))) : null
  const last = site.dates[site.dates.length - 1]
  const r30 = rain.status === 'ready' && se ? rainBefore(rain.data, se.event.date) : null
  const pickSite = (id: string) => {
    setParams({ site: id, layer: undefined, f: undefined, pt: undefined, a: undefined, b: undefined })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="site-page">
      {/* 01 · Hero */}
      <section className="hero" aria-labelledby="hero-title">
        <HeroBackdrop />
        <div className="hero__text">
          <p className="hero__kicker">
            <span className="hero__kicker-rule" aria-hidden="true" />
            <span className="hero__kicker-id">{PROJECT.name}</span>
            <span className="hero__kicker-sep" aria-hidden="true">
              ·
            </span>
            <span>NASA-ISRO NISAR radar</span>
          </p>
          {/* One sentence per line: two light lines build up to the bold third. */}
          <h1 id="hero-title" className="hero__title">
            {taglineLines.map((line, i) => (
              <span key={line} className={`hero__line hero__line--${i + 1}`}>
                {line}{' '}
              </span>
            ))}
          </h1>
          <p className="hero__lede">{PROJECT.mission}</p>
          <div className="hero__cta">
            <a className="btn btn--primary" href={`?view=app&site=${site.id}`}>
              Open the TRACE workspace
            </a>
            <a className="btn" href="#time-machine">
              Start the Time Machine
            </a>
            <a className="btn" href="#explore">
              Choose a place
            </a>
          </div>
        </div>
      </section>

      {/* 02 · Explore */}
      <Screen id="explore" n={2} title="Explore a place" text={se?.story.place} research={research}>
        <ul className="site-cards">
          {sites.map((s) => (
            <li key={s.id}>
              <button type="button" className="panel site-card" aria-pressed={s.id === site.id} onClick={() => pickSite(s.id)}>
                <strong>{s.name}</strong>
                <span className="muted">
                  {s.change_type}
                  {s.source === 'demo' ? ' · demo data' : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {se && (
          <ul className="facts">
            <li className="panel event-card">
              <strong>{se.event.date}</strong>
              <span>{se.event.label}</span>
              <span className="muted">
                {se.region}, {se.country}
              </span>
              <SourceLink source={se.event.source} />
            </li>
            {se.facts.map((f) => (
              <li key={f.text} className="panel">
                <span>{f.text}</span>
                <SourceLink source={f.source} />
              </li>
            ))}
          </ul>
        )}
      </Screen>

      {/* 03 · Earth Time Machine */}
      <TimeMachine site={site} research={research} params={params} setParams={setParams} />

      {/* 04 · Radar Vision */}
      <RadarVision site={site} research={research} />

      {/* 05 · Rainfall */}
      <Screen id="rain" n={5} title="Rainfall connection" text={se?.story.rain} research={research}>
        <div className="panel">
          <RainTimeline rain={rain} passes={site.dates} event={se ? { date: se.event.date, label: se.event.label } : undefined} />
          {se?.rain && (
            <p className="muted site-page__note">
              {se.rain.note} <SourceLink source={se.rain.source} />
            </p>
          )}
        </div>
        {r30 && (
          <div className="rain-stats">
            <div className="panel">
              <strong>{r30.total.toFixed(0)} mm</strong>
              <span className="muted">in the {r30.days} days before the event</span>
            </div>
            <div className="panel">
              <strong>{r30.peak.toFixed(0)} mm</strong>
              <span className="muted">wettest single day</span>
            </div>
            <div className="panel">
              <strong>{r30.wetDays}</strong>
              <span className="muted">days with rain</span>
            </div>
          </div>
        )}
        <p className="muted site-page__note">
          Rain coming before a slide does not prove it caused it; it is one of the drivers we compare with the radar.
        </p>
      </Screen>

      {/* 06 · Earth Impact */}
      <Screen id="impact" n={6} title="Earth impact" text={se?.story.exposure} research={research}>
        <div className="impact">
          <LazyMount className="impact__map">
            <SarMap
              corners={site.corners}
              imageUrl={last ? paths.layer(site.id, 'hh', last) : null}
              imageOpacity={0.45}
              vectors={impactOverlays?.vectors}
              badge={last ? `HH · ${last}${site.source === 'demo' ? ' · DEMO' : ''}` : undefined}
            />
          </LazyMount>
          <div className="impact__side">
            <section className="panel">
              <h3>Near the slope</h3>
              <ExposureCard exposure={se?.exposure ?? null} research={research} />
            </section>
            <section className="panel">
              <h3>Registered events</h3>
              <EventCatalog catalog={se?.catalog} />
            </section>
            <a className="btn btn--primary" href="#report">
              Generate investigation report
            </a>
          </div>
        </div>
      </Screen>

      {/* 07 · Global Stories */}
      <Screen id="stories" n={7} title="Global stories" research={research}>
        <p className="screen__text">
          One method, many slopes. Each place uses the same template, so a new region is new data, not new code. We start
          with Kyrgyzstan.
        </p>
        <ul className="site-cards">
          {sites.map((s) => (
            <li key={s.id}>
              <button type="button" className="panel site-card" aria-pressed={s.id === site.id} onClick={() => pickSite(s.id)}>
                <strong>{s.name}</strong>
                <span className="muted">
                  {s.change_type} · {s.center[1].toFixed(2)}°, {s.center[0].toFixed(2)}°{s.source === 'demo' ? ' · demo data' : ''}
                </span>
              </button>
            </li>
          ))}
          {sites.length < 2 && (
            <li className="panel site-card site-card--next">
              <strong>Second region</strong>
              <span className="muted">Being checked against NISAR coverage. Same screens, different slope.</span>
            </li>
          )}
        </ul>
      </Screen>

      {/* 08 · Investigation Report */}
      <Screen id="report" n={8} title="Investigation report" research={research}>
        <p className="screen__text">
          Everything above on one page, with dates, sources and limits. Hand it to a geologist or save it as PDF.
        </p>
        <div className="panel">
          <ReportBody site={site} rain={rain} generated={generated} compact />
        </div>
        <p>
          <a className="btn btn--primary" href={`?site=${site.id}&view=brief`} target="_blank" rel="noreferrer">
            Generate full report (print / PDF)
          </a>
        </p>
      </Screen>

      {/* 09 · Data & Science */}
      <Screen id="data" n={9} title="Data & science" research={research}>
        <DataLimits site={site} research={research} />
      </Screen>
    </div>
  )
}
