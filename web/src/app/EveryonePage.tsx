import { useMemo, useState } from 'react'
import { SarMap } from '../core/map/SarMap'
import { HeroBackdrop } from '../core/ui/HeroBackdrop'
import { LazyMount } from '../core/ui/LazyMount'
import { SwipeCompare } from '../features/compare/components/SwipeCompare'
import { EVERYONE, VIEW_MODES } from '../features/everyone/content'
import type { ViewMode } from '../features/everyone/content'
import { EveryoneSection, FactCard, HowRadarSees, WarningSigns } from '../features/everyone/components/EveryoneBlocks'
import { ListenButton } from '../features/listen/ListenButton'
import { useChangeStats, useRain, useTimeSeries } from '../features/sites/api'
import { buildLayers, frameIndexFor } from '../features/sites/model/layers'
import type { SiteDetail, SiteSummary } from '../features/sites/model/types'
import { SourceLink } from '../features/story/components/Screen'
import { FrameSlider } from '../features/timeline/components/FrameSlider'
import { rainBefore } from '../features/timeline/lib/rain'
import './EveryonePage.css'

// "For everyone": one place, plain words, four ways to look, three numbers, how it works,
// what to watch for. Same data as the specialist section, far fewer controls.

interface Props {
  site: SiteDetail
  sites: SiteSummary[]
  onPickSite: (id: string) => void
  onOpenSpecialists: () => void
}

const human = (d: string) =>
  new Date(`${d}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
const short = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })

export function EveryonePage({ site, sites, onPickSite, onOpenSpecialists }: Props) {
  const se = site.slope_echo
  const layers = useMemo(() => buildLayers(site), [site])
  const hh = layers.find((l) => l.id === 'hh') ?? layers[0]
  const change = layers.find((l) => l.kind === 'change')
  const optical = layers.find((l) => l.kind === 'optical')
  const modes = VIEW_MODES.filter((m) => (m.id === 'photo' ? !!optical : m.id === 'changed' ? !!change : true))
  const [mode, setMode] = useState<ViewMode['id']>('before-after')
  const [frame, setFrame] = useState(0)
  const active = modes.find((m) => m.id === mode) ?? modes[0]

  const rain = useRain(site)
  const r30 = rain.status === 'ready' && se ? rainBefore(rain.data, se.event.date) : null
  const r7 = rain.status === 'ready' && se ? rainBefore(rain.data, se.event.date, 7) : null
  // Most of the month's rain fell before the last week: say so instead of implying rain set it off.
  const dryWeek = r30 && r7 ? r7.total < 0.25 * r30.total : false
  const poi = site.points_of_interest[0]
  const series = useTimeSeries(site.id, poi ? { lon: poi.lon, lat: poi.lat, poiId: poi.id } : null)
  const demo = site.source === 'demo' ? ' · DEMO' : ''

  const first = hh.frames[0]
  const last = hh.frames[hh.frames.length - 1]
  // The change pair that spans the event, else the last pair.
  const eventChange =
    change && se
      ? (change.frames.find((f) => (f.from ?? '') < se.event.date && f.date >= se.event.date) ?? change.frames[change.frames.length - 1])
      : change?.frames[change.frames.length - 1]
  const photo = optical?.frames[frameIndexFor(optical, last.date)]
  // Real numbers behind the change picture, so an empty map is explained, not left to guess.
  const stats = useChangeStats(site.id, eventChange?.from ? { from: eventChange.from, to: eventChange.date } : null)

  let map
  if (active.id === 'before-after') {
    map = (
      <SwipeCompare
        corners={site.corners}
        left={{ imageUrl: first.url, badge: `Before · ${short(first.date)}${demo}` }}
        right={{ imageUrl: last.url, badge: `After · ${short(last.date)}${demo}` }}
      />
    )
  } else if (active.id === 'photo' && photo) {
    map = (
      <SwipeCompare
        corners={site.corners}
        left={{ imageUrl: photo.url, badge: `Photo · ${short(photo.date)}${demo}` }}
        right={{ imageUrl: last.url, badge: `Radar · ${short(last.date)}${demo}` }}
      />
    )
  } else if (active.id === 'changed' && eventChange) {
    map = (
      <SarMap
        corners={site.corners}
        imageUrl={hh.frames[frameIndexFor(hh, eventChange.date)].url}
        imageOpacity={0.55}
        images={[{ id: 'change', url: eventChange.url }]}
        badge={`Changed · ${short(eventChange.from ?? '')} → ${short(eventChange.date)}${demo}`}
      />
    )
  } else {
    const f = hh.frames[Math.min(frame, hh.frames.length - 1)]
    map = <SarMap corners={site.corners} imageUrl={f.url} badge={`Pass ${frame + 1} of ${hh.frames.length} · ${short(f.date)}${demo}`} />
  }

  return (
    <div className="everyone">
      <section className="ev-hero" aria-labelledby="ev-hero-title">
        <HeroBackdrop />
        <div className="ev-hero__text">
          <p className="ev-hero__kicker">{EVERYONE.kicker}</p>
          <h1 id="ev-hero-title">{EVERYONE.title}</h1>
          <p className="ev-hero__lede">{EVERYONE.lede}</p>
          {sites.length > 1 && (
            <div className="ev-places" role="group" aria-label="Choose a place">
              {sites.map((s) => (
                <button key={s.id} type="button" className="btn" aria-pressed={s.id === site.id} onClick={() => onPickSite(s.id)}>
                  {s.name}
                  {s.source === 'demo' ? ' (demo)' : ''}
                </button>
              ))}
            </div>
          )}
          <a className="btn btn--primary ev-hero__cta" href="#ev-what">
            {EVERYONE.start}
          </a>
        </div>
      </section>

      <EveryoneSection id="ev-what" title={se ? `What happened at ${site.name.replace(/ landslide$/i, '')}` : site.name}>
        {se ? (
          <div className="ev-event">
            <p className="ev-event__date">{human(se.event.date)}</p>
            <p className="ev-event__label">{se.event.label}</p>
            <ul>
              {se.facts.slice(0, 2).map((f) => (
                <li key={f.text}>
                  {f.text} <SourceLink source={f.source} />
                </li>
              ))}
            </ul>
            <p className="muted">
              {se.region}, {se.country}
            </p>
          </div>
        ) : (
          <p>No story for this place yet.</p>
        )}
      </EveryoneSection>

      <EveryoneSection id="ev-look" title="Look at it from space">
        <div className="ev-modes" role="tablist" aria-label="How to look">
          {modes.map((m) => (
            <button key={m.id} type="button" role="tab" aria-selected={m.id === active.id} onClick={() => setMode(m.id)}>
              {m.label}
            </button>
          ))}
        </div>
        <LazyMount className="ev-map">{map}</LazyMount>
        {active.id === 'timelapse' && (
          <FrameSlider labels={hh.frames.map((f) => short(f.date))} index={frame} onChange={setFrame} frameMs={1200} />
        )}
        <p className="ev-explain">{active.explain}</p>
        {active.id === 'changed' && stats.status === 'ready' && (
          <p className="ev-explain ev-explain--result">
            <strong>
              {stats.data.changed_pct.toFixed(1)}% of the area ({stats.data.changed_km2.toFixed(3)} km²) changed by more than {stats.data.threshold_db} dB
            </strong>{' '}
            between {short(stats.data.from)} and {short(stats.data.to)}.{' '}
            {stats.data.changed_pct < 1
              ? 'Almost nothing crossed the threshold, so this pair does not show the landslide clearly. A small slide covers only a few dozen 20 m radar pixels, and one pair can miss it.'
              : 'Coloured areas are where to look closer; they still need checking against photos and reports.'}
          </p>
        )}
      </EveryoneSection>

      <EveryoneSection id="ev-numbers" title="Three things worth knowing">
        <div className="ev-facts">
          {r30 ? (
            <FactCard
              big={`${r30.total.toFixed(0)} mm`}
              label={`of rain in the ${r30.days} days before`}
              note={`That is ${r30.total.toFixed(0)} litres of water on every square metre, measured over a 10 km area, not on the slope itself. ${
                dryWeek
                  ? 'Most of it fell earlier: the last week was almost dry, so rain alone does not explain why the slope moved that day.'
                  : 'Wet soil is heavier and weaker, but rain alone does not prove what set the slope moving.'
              }`}
            />
          ) : (
            <FactCard big="—" label="Rain data not available yet" />
          )}
          {se?.exposure ? (
            <FactCard
              big={`${se.exposure.buildings}`}
              label={`buildings within ${se.exposure.radius_km} km`}
              note={`and ${se.exposure.roads_km} km of road. Being near a slope is not the same as being in danger.`}
            />
          ) : (
            <FactCard big="—" label="Nearby buildings not counted yet" />
          )}
          {se?.catalog?.length ? (
            <FactCard
              big={`${se.catalog.length}`}
              label="earlier landslides and mudflows reported in the area"
              note={
                <>
                  Latest: {se.catalog[0].name}, {short(se.catalog[0].date)} {se.catalog[0].date.slice(0, 4)}.{' '}
                  <SourceLink source={se.catalog[0].source} />
                </>
              }
            />
          ) : (
            <FactCard big="—" label="No earlier events listed yet" />
          )}
        </div>
      </EveryoneSection>

      <EveryoneSection id="ev-how" title="How can a satellite see through clouds?">
        <HowRadarSees />
        {series.status === 'ready' && poi && (
          <div className="ev-listen">
            <p>Hear it: each note is one satellite pass over {poi.name}. Higher note, stronger echo.</p>
            <ListenButton
              label="Radar echo"
              dates={series.data.series.map((s) => s.date)}
              values={series.data.series.map((s) => s.hh_db)}
            />
          </div>
        )}
      </EveryoneSection>

      <EveryoneSection id="ev-safe" title="Signs of a moving slope">
        <WarningSigns />
      </EveryoneSection>

      <EveryoneSection id="ev-more" title="Want the full analysis?">
        <p>
          Specialists can compare any two dates, see the radar's motion maps (centimetres along its line of sight), read why the
          data does and does not show this slide, and download a report.
        </p>
        <div>
          <button type="button" className="btn btn--primary ev-more__btn" onClick={onOpenSpecialists}>
            Open the specialist section
          </button>
        </div>
      </EveryoneSection>
    </div>
  )
}
