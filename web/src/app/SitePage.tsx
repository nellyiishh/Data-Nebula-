import { SarMap } from '../core/map/SarMap'
import type { Corners } from '../core/map/SarMap'
import { ExposureCard } from '../features/exposure/components/ExposureCard'
import { paths } from '../core/api/client'
import { useRain } from '../features/sites/api'
import type { SiteDetail, SiteSummary } from '../features/sites/model/types'
import { DataLimits } from '../features/story/components/DataLimits'
import { Screen, SourceLink } from '../features/story/components/Screen'
import { PROJECT } from '../features/story/content'
import { RainTimeline } from '../features/timeline/components/RainTimeline'
import { Explorer } from './Explorer'
import { toMapOverlays } from './mapOverlays'
import './SitePage.css'

// Composition root for one site: the 8-screen story. Features never import each other's
// components; they meet here. App mounts it with key={site.id}.

type Params = Record<string, string | undefined>
interface Props {
  site: SiteDetail
  sites: SiteSummary[]
  research: boolean
  params: Params
  setParams: (p: Params) => void
}

function around([lon, lat]: [number, number], d: number): Corners {
  return [
    [lon - d, lat + d * 0.7],
    [lon + d, lat + d * 0.7],
    [lon + d, lat - d * 0.7],
    [lon - d, lat - d * 0.7],
  ]
}

export function SitePage({ site, sites, research, params, setParams }: Props) {
  const se = site.slope_echo
  const rain = useRain(site)
  const exposureOverlays = se ? toMapOverlays(site, se.overlays.filter((o) => ['exposure', 'aoi', 'scar'].includes(o.id))) : null
  const last = site.dates[site.dates.length - 1]

  return (
    <div className="site-page">
      {/* 1 · Hero */}
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero__map">
          <SarMap
            corners={around(site.center, 2.5)}
            interactive={false}
            showControls={false}
            markers={sites.map((s) => ({ id: s.id, lon: s.center[0], lat: s.center[1], label: s.name }))}
            onMarkerClick={(id) => setParams({ site: id })}
            padding={0}
          />
        </div>
        <div className="hero__text">
          <p className="hero__kicker">
            {PROJECT.name} · NISAR radar · {se ? `${se.region}, ${se.country}` : site.name}
          </p>
          <h1 id="hero-title">{PROJECT.tagline}</h1>
          <p className="hero__lede">
            {se
              ? `${se.event.date}: ${se.event.label}. Follow the rain, the radar and the people below the slope.`
              : site.name}
          </p>
          <div className="hero__cta">
            <a className="btn btn--primary" href="#radar">
              See what the radar saw
            </a>
            <a className="btn" href="#data">
              What we know and don't
            </a>
          </div>
        </div>
      </section>

      {/* 2 · Place */}
      <Screen id="place" n={2} title={se ? `${site.name}` : 'The place'} text={se?.story.place} research={research}>
        {se ? (
          <ul className="facts">
            <li className="panel event-card">
              <strong>{se.event.date}</strong>
              <span>{se.event.label}</span>
              <SourceLink source={se.event.source} />
            </li>
            {se.facts.map((f) => (
              <li key={f.text} className="panel">
                <span>{f.text}</span>
                <SourceLink source={f.source} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="state-msg">No story for this site yet.</p>
        )}
      </Screen>

      {/* 3 · Rain */}
      <Screen id="rain" n={3} title="Rain loads it" text={se?.story.rain} research={research}>
        <div className="panel">
          <RainTimeline rain={rain} passes={site.dates} event={se ? { date: se.event.date, label: se.event.label } : undefined} />
          {se?.rain && (
            <p className="muted site-page__note">
              {se.rain.note} <SourceLink source={se.rain.source} />
            </p>
          )}
        </div>
      </Screen>

      {/* 4 + 5 · Radar and tracking */}
      <Explorer site={site} research={research} params={params} setParams={setParams} />

      {/* 6 · Exposure */}
      <Screen id="exposure" n={6} title="People live below it" text={se?.story.exposure} research={research}>
        <div className="exposure-screen">
          <div className="exposure-screen__map">
            <SarMap
              corners={site.corners}
              imageUrl={last ? paths.layer(site.id, 'hh', last) : null}
              imageOpacity={0.45}
              vectors={exposureOverlays?.vectors}
              badge={last ? `HH · ${last}${site.source === 'demo' ? ' · DEMO' : ''}` : undefined}
            />
          </div>
          <div className="panel">
            <ExposureCard exposure={se?.exposure ?? null} research={research} />
          </div>
        </div>
      </Screen>

      {/* 7 · Around the world */}
      <Screen id="world" n={7} title="Same tool, any slope" research={research}>
        <p className="screen__text">
          Every site uses the same template: add its files and one entry in the data, and this page works for it. We
          start with Kyrgyzstan.
        </p>
        <ul className="site-cards">
          {sites.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className="panel site-card"
                aria-pressed={s.id === site.id}
                onClick={() => {
                  setParams({ site: s.id, layer: undefined, f: undefined, pt: undefined, a: undefined, b: undefined })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                <strong>{s.name}</strong>
                <span className="muted">
                  {s.change_type}
                  {s.source === 'demo' ? ' · demo data' : ''}
                </span>
              </button>
            </li>
          ))}
          {sites.length < 2 && (
            <li className="panel site-card site-card--next">
              <strong>Next region</strong>
              <span className="muted">Being checked against NISAR coverage.</span>
            </li>
          )}
        </ul>
      </Screen>

      {/* 8 · Data and limits */}
      <Screen id="data" n={8} title="What we know and what we don't" research={research}>
        <DataLimits site={site} research={research} />
        <p>
          <a className="btn" href={`?site=${site.id}&view=brief`} target="_blank" rel="noreferrer">
            Open field brief (print / PDF)
          </a>
        </p>
      </Screen>
    </div>
  )
}
