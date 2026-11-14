import { useMemo } from 'react'
import { isStatic } from '../core/api/client'
import { SarMap } from '../core/map/SarMap'
import type { MapMarker } from '../core/map/SarMap'
import { usePreloadImages } from '../core/map/usePreloadImages'
import { PointPanel } from '../features/chart/components/PointPanel'
import { LayerControls } from '../features/compare/components/LayerControls'
import type { SwipeMode } from '../features/compare/components/LayerControls'
import { Legend } from '../features/compare/components/Legend'
import { SwipeCompare } from '../features/compare/components/SwipeCompare'
import { usePointExtras, useRain, useTimeSeries } from '../features/sites/api'
import type { PointQuery } from '../features/sites/api'
import { buildLayers, frameIndexFor } from '../features/sites/model/layers'
import type { PointOfInterest, SiteDetail } from '../features/sites/model/types'
import { Screen } from '../features/story/components/Screen'
import { FrameSlider } from '../features/timeline/components/FrameSlider'
import { RainTimeline } from '../features/timeline/components/RainTimeline'
import { toMapOverlays } from './mapOverlays'
import './Explorer.css'

// Screens 4 ("Radar hears it") and 5 ("Tracking the slope") share one map state, so they are
// composed here. State lives in the URL (?layer, f, swipe, a, b, ov, pt) so views can be shared.

type Params = Record<string, string | undefined>
interface Props {
  site: SiteDetail
  research: boolean
  params: Params
  setParams: (p: Params) => void
}

const DEFAULT_OVERLAYS = 'radar_blind,scar'

function nearestPoi(points: PointOfInterest[], lon: number, lat: number) {
  let best: PointOfInterest | undefined
  let bestD = Infinity
  for (const p of points) {
    const d = (p.lon - lon) ** 2 + (p.lat - lat) ** 2
    if (d < bestD) [best, bestD] = [p, d]
  }
  return best
}

export function Explorer({ site, research, params, setParams }: Props) {
  const se = site.slope_echo
  const layers = useMemo(() => buildLayers(site), [site])
  const layer = layers.find((l) => l.id === params.layer) ?? layers[0]
  const optical = layers.find((l) => l.kind === 'optical')
  const n = layer.frames.length
  const fIdx = Math.max(0, layer.frames.findIndex((f) => f.key === params.f))
  const frame = layer.frames[fIdx]
  const swipe = (params.swipe as SwipeMode | undefined) ?? 'off'
  const aIdx = Math.min(n - 1, Number(params.a ?? 0))
  const bIdx = Math.min(n - 1, Number(params.b ?? n - 1))
  const opacity = Number(params.op ?? 0.85)

  const allOverlays = se?.overlays.filter((o) => o.id !== 'exposure' && o.id !== 'aoi') ?? []
  const shownIds = (params.ov ?? DEFAULT_OVERLAYS).split(',').filter(Boolean)
  const shown = allOverlays.filter((o) => shownIds.includes(o.id))
  const { images, vectors } = toMapOverlays(site, shown)

  // Point: a POI id, or "@lon,lat" from a click when the live API can answer any point.
  const poi = site.points_of_interest.find((p) => p.id === params.pt)
  const clicked = params.pt?.startsWith('@') ? params.pt.slice(1).split(',').map(Number) : null
  const query: PointQuery | null = poi
    ? { lon: poi.lon, lat: poi.lat, poiId: poi.id }
    : clicked
      ? { lon: clicked[0], lat: clicked[1] }
      : null
  const backscatter = useTimeSeries(site.id, query)
  const extras = usePointExtras(site, poi?.id)
  const rain = useRain(site)

  usePreloadImages(layer.frames.map((f) => f.url))

  const setFrame = (i: number) => setParams({ f: layer.frames[i]?.key })
  const setLayer = (id: string) => {
    const next = layers.find((l) => l.id === id)!
    setParams({ layer: id, f: next.frames[frameIndexFor(next, frame?.date)]?.key, a: undefined, b: undefined })
  }
  const toggleOverlay = (id: string) =>
    setParams({ ov: (shownIds.includes(id) ? shownIds.filter((x) => x !== id) : [...shownIds, id]).join(',') || ',' })
  const selectPoi = (p: PointOfInterest) => setParams({ pt: p.id })
  const onMapClick = (lon: number, lat: number) => {
    if (!isStatic) return setParams({ pt: `@${lon.toFixed(5)},${lat.toFixed(5)}` })
    // Static files only hold pre-computed points, so snap to the nearest one.
    const p = nearestPoi(site.points_of_interest, lon, lat)
    if (p) selectPoi(p)
  }

  const markers: MapMarker[] = site.points_of_interest.map((p) => ({ id: p.id, lon: p.lon, lat: p.lat, label: p.name }))
  const badge = (label: string, title = layer.title) => `${title} · ${label}${site.source === 'demo' ? ' · DEMO' : ''}`

  let map
  if (swipe === 'dates' && n > 1) {
    map = (
      <SwipeCompare
        corners={site.corners}
        left={{ imageUrl: layer.frames[aIdx].url, badge: badge(layer.frames[aIdx].label) }}
        right={{ imageUrl: layer.frames[bIdx].url, badge: badge(layer.frames[bIdx].label) }}
        {...{ markers, images, vectors, onMapClick }}
        onMarkerClick={(id) => setParams({ pt: id })}
      />
    )
  } else if (swipe === 'optical' && optical && frame) {
    const o = optical.frames[frameIndexFor(optical, frame.date)]
    map = (
      <SwipeCompare
        corners={site.corners}
        left={{ imageUrl: o.url, badge: badge(o.label, optical.title) }}
        right={{ imageUrl: frame.url, badge: badge(frame.label) }}
        {...{ markers, images, vectors, onMapClick }}
        onMarkerClick={(id) => setParams({ pt: id })}
      />
    )
  } else {
    map = (
      <SarMap
        corners={site.corners}
        imageUrl={frame?.url}
        imageOpacity={opacity}
        badge={frame ? badge(frame.label) : undefined}
        {...{ markers, images, vectors, onMapClick }}
        onMarkerClick={(id) => setParams({ pt: id })}
      />
    )
  }

  const pairSelect = (label: string, value: number, key: 'a' | 'b') => (
    <label className="explorer__pair">
      {label}
      <select value={value} onChange={(e) => setParams({ [key]: e.target.value })}>
        {layer.frames.map((f, i) => (
          <option key={f.key} value={i}>
            {f.label}
          </option>
        ))}
      </select>
    </label>
  )

  return (
    <>
      <Screen id="radar" n={4} title="Radar hears it" text={se?.story.radar} research={research} wide>
        <div className="explorer">
          <div className="explorer__map">{map}</div>
          <aside className="explorer__side">
            <section className="panel">
              <h3>Layer</h3>
              <LayerControls
                layers={layers}
                layerId={layer.id}
                onLayer={setLayer}
                opacity={opacity}
                onOpacity={(v) => setParams({ op: String(v) })}
                swipe={swipe}
                onSwipe={(m) => setParams({ swipe: m === 'off' ? undefined : m })}
                hasOptical={!!optical && layer.id !== optical.id}
                overlays={allOverlays}
                shownOverlays={shownIds}
                onToggleOverlay={toggleOverlay}
                research={research}
              />
              {swipe === 'dates' && (
                <div className="explorer__pairs">
                  {pairSelect('Left', aIdx, 'a')}
                  {pairSelect('Right', bIdx, 'b')}
                </div>
              )}
            </section>
            <section className="panel">
              <h3>Legend</h3>
              <Legend layer={layer} overlays={shown} />
            </section>
            {research && (
              <section className="panel">
                <h3>Why radar, not photos?</h3>
                <p className="muted explorer__why">
                  NISAR brings its own microwave light (L-band, ~24 cm). It works at night and sees through clouds and
                  smoke — try “Radar vs photo” on a cloudy date.
                </p>
              </section>
            )}
          </aside>
        </div>
      </Screen>

      <Screen id="tracking" n={5} title="Tracking the slope" text={se?.story.tracking} research={research} wide>
        <div className="tracking">
          <section className="panel tracking__time">
            <h3>Every pass</h3>
            <FrameSlider labels={layer.frames.map((f) => f.label)} index={fIdx} onChange={setFrame} />
            <RainTimeline
              rain={rain}
              passes={site.dates}
              event={se ? { date: se.event.date, label: 'event' } : undefined}
              activePass={frame?.date}
              onPassClick={(d) => setFrame(frameIndexFor(layer, d))}
              height={150}
            />
          </section>
          <section className="panel">
            <h3>{poi ? poi.name : clicked ? 'Clicked point' : 'One place over time'}</h3>
            <PointPanel
              layer={layer}
              dates={site.dates}
              event={se ? { date: se.event.date, label: 'event' } : undefined}
              cursor={frame?.date}
              backscatter={backscatter}
              extras={extras}
              points={site.points_of_interest}
              selectedId={poi?.id}
              pointLabel={poi?.note}
              onSelect={selectPoi}
            />
          </section>
        </div>
      </Screen>
    </>
  )
}
