import { useMemo, useState } from 'react'
import { isStatic } from '../core/api/client'
import { SarMap } from '../core/map/SarMap'
import type { MapMarker } from '../core/map/SarMap'
import { usePreloadImages } from '../core/map/usePreloadImages'
import { LazyMount } from '../core/ui/LazyMount'
import { PointPanel } from '../features/chart/components/PointPanel'
import { LayerControls } from '../features/compare/components/LayerControls'
import { Legend } from '../features/compare/components/Legend'
import { SwipeCompare } from '../features/compare/components/SwipeCompare'
import { ListenButton } from '../features/listen/ListenButton'
import { usePointExtras, useRain, useTimeSeries } from '../features/sites/api'
import type { PointQuery } from '../features/sites/api'
import { buildLayers, frameIndexFor } from '../features/sites/model/layers'
import type { PointOfInterest, SiteDetail } from '../features/sites/model/types'
import { Screen } from '../features/story/components/Screen'
import { FrameSlider } from '../features/timeline/components/FrameSlider'
import { RainTimeline } from '../features/timeline/components/RainTimeline'
import { toMapOverlays } from './mapOverlays'
import './TimeMachine.css'

// Screen 03 "Earth Time Machine": every NISAR pass as a frame, with rain and one point's
// history on the same timeline. State lives in the URL (?layer, f, cmp, a, b, ov, pt, op, t3d, ct).

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

export function TimeMachine({ site, research, params, setParams }: Props) {
  const se = site.slope_echo
  // Optical has its own screen (Radar Vision); the time machine is radar only.
  const layers = useMemo(() => buildLayers(site).filter((l) => l.kind !== 'optical'), [site])
  const layer = layers.find((l) => l.id === params.layer) ?? layers[0]
  const n = layer.frames.length
  const fIdx = Math.max(0, layer.frames.findIndex((f) => f.key === params.f))
  const frame = layer.frames[fIdx]
  const compare = params.cmp === '1' && n > 1
  const aIdx = Math.min(n - 1, Number(params.a ?? 0))
  const bIdx = Math.min(n - 1, Number(params.b ?? n - 1))
  const opacity = Number(params.op ?? 0.85)
  const terrain = params.t3d === '1'
  const contrast = Number(params.ct ?? 0)
  const [listenDate, setListenDate] = useState<string | undefined>()

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
  const onMarkerClick = (id: string) => setParams({ pt: id })

  const markers: MapMarker[] = site.points_of_interest.map((p) => ({ id: p.id, lon: p.lon, lat: p.lat, label: p.name }))
  const badge = (label: string) => `${layer.title} · ${label}${site.source === 'demo' ? ' · DEMO' : ''}`
  const event = se ? { date: se.event.date, label: 'event' } : undefined

  const map = compare ? (
    <SwipeCompare
      corners={site.corners}
      left={{ imageUrl: layer.frames[aIdx].url, badge: badge(layer.frames[aIdx].label) }}
      right={{ imageUrl: layer.frames[bIdx].url, badge: badge(layer.frames[bIdx].label) }}
      {...{ markers, images, vectors, onMapClick, onMarkerClick }}
    />
  ) : (
    <SarMap
      corners={site.corners}
      imageUrl={frame?.url}
      imageOpacity={opacity}
      contrast={contrast}
      terrain={terrain}
      badge={frame ? badge(frame.label) : undefined}
      {...{ markers, images, vectors, onMapClick, onMarkerClick }}
    />
  )

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
    <Screen id="time-machine" n={3} title="Earth Time Machine" text={se?.story.tracking} research={research} wide>
      <div className="explorer">
        <LazyMount className="explorer__map">{map}</LazyMount>
        <aside className="explorer__side">
          <section className="panel">
            <h3>What to look at</h3>
            <LayerControls
              layers={layers}
              layerId={layer.id}
              onLayer={setLayer}
              opacity={opacity}
              onOpacity={(v) => setParams({ op: String(v) })}
              overlays={allOverlays}
              shownOverlays={shownIds}
              onToggleOverlay={toggleOverlay}
              research={research}
            />
            <div className="explorer__toggles">
              <button type="button" className="btn" aria-pressed={compare} onClick={() => setParams({ cmp: compare ? undefined : '1' })}>
                Compare two dates
              </button>
              <button
                type="button"
                className="btn"
                aria-pressed={terrain}
                disabled={compare}
                onClick={() => setParams({ t3d: terrain ? undefined : '1' })}
                title="Drape the radar on a 3D elevation model. Elevation comes from a DEM, not from the radar."
              >
                3D terrain
              </button>
            </div>
            {compare && (
              <div className="explorer__pairs">
                {pairSelect('Left', aIdx, 'a')}
                {pairSelect('Right', bIdx, 'b')}
              </div>
            )}
            {research && !compare && (
              <label className="explorer__field" title="Radar images are dark until stretched; this only changes the display, not the data.">
                Contrast stretch
                <input type="range" min={-0.5} max={0.8} step={0.05} value={contrast} onChange={(e) => setParams({ ct: e.target.value })} />
              </label>
            )}
          </section>
          <section className="panel">
            <h3>Legend</h3>
            <Legend layer={layer} overlays={shown} />
          </section>
        </aside>
      </div>

      <div className="tracking">
        <section className="panel tracking__time">
          <h3>Every pass · press Play</h3>
          <FrameSlider labels={layer.frames.map((f) => f.label)} index={fIdx} onChange={setFrame} />
          <RainTimeline
            rain={rain}
            passes={site.dates}
            event={event}
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
            event={event}
            cursor={listenDate ?? frame?.date}
            backscatter={backscatter}
            extras={extras}
            points={site.points_of_interest}
            selectedId={poi?.id}
            pointLabel={poi?.note}
            onSelect={selectPoi}
            renderExtra={(line) => (
              <ListenButton
                key={`${line.id}-${poi?.id}`}
                label={line.label}
                dates={line.points.map((pt) => pt.date)}
                values={line.points.map((pt) => pt.value)}
                onStep={setListenDate}
              />
            )}
          />
        </section>
      </div>
    </Screen>
  )
}
