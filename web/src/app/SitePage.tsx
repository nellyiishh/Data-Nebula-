import { useCallback, useMemo, useState } from 'react'
import { isStatic } from '../core/api/client'
import { SarMap } from '../core/map/SarMap'
import type { MapMarker } from '../core/map/SarMap'
import { usePreloadImages } from '../core/map/usePreloadImages'
import { PoiList } from '../features/chart/components/PoiList'
import { PointChart } from '../features/chart/components/PointChart'
import { StatCards } from '../features/chart/components/StatCards'
import { LayerControls } from '../features/compare/components/LayerControls'
import { Legend } from '../features/compare/components/Legend'
import { SwipeCompare } from '../features/compare/components/SwipeCompare'
import { LAYER_LABELS } from '../features/compare/model/layers'
import { TimeSlider } from '../features/map/components/TimeSlider'
import { changeUrl, layerUrl, useStats, useTimeSeries } from '../features/sites/api'
import type { PointQuery } from '../features/sites/api'
import type { LayerId, PointOfInterest, Site } from '../features/sites/model/types'
import { StoryPanel } from '../features/story/components/StoryPanel'

// Composition root for one site: owns view state and wires features together.
// Features never import each other's components; they meet here.
// App mounts it with key={site.id}, so all view state resets when the site changes.

function nearestPoi(points: PointOfInterest[], lon: number, lat: number) {
  let best: PointOfInterest | undefined
  let bestD = Infinity
  for (const p of points) {
    const d = (p.lon - lon) ** 2 + (p.lat - lat) ** 2
    if (d < bestD) [best, bestD] = [p, d]
  }
  return best
}

export function SitePage({ site }: { site: Site }) {
  const n = site.dates.length
  const [layer, setLayer] = useState<LayerId>(site.layers[0] ?? 'hh')
  const [dateIndex, setDateIndex] = useState(0)
  const [opacity, setOpacity] = useState(0.85)
  const [compare, setCompare] = useState(false)
  const [showChange, setShowChange] = useState(false)
  const [fromIndex, setFromIndex] = useState(0)
  const [toIndex, setToIndex] = useState(Math.max(0, n - 1))
  const [point, setPoint] = useState<(PointQuery & { label: string }) | null>(null)

  const stats = useStats(site.id)
  const series = useTimeSeries(site.id, point)

  const date = site.dates[dateIndex]
  const from = site.dates[fromIndex]
  const to = site.dates[toIndex]
  const label = LAYER_LABELS[layer] ?? layer

  usePreloadImages(useMemo(() => site.dates.map((d) => layerUrl(site.id, layer, d)), [site.id, site.dates, layer]))

  const markers: MapMarker[] = useMemo(
    () => site.points_of_interest.map((p) => ({ id: p.id, lon: p.lon, lat: p.lat, label: p.name })),
    [site.points_of_interest],
  )

  const selectPoi = useCallback((p: PointOfInterest) => {
    setPoint({ lon: p.lon, lat: p.lat, poiId: p.id, label: p.name })
  }, [])

  const onMapClick = useCallback(
    (lon: number, lat: number) => {
      if (!isStatic) return setPoint({ lon, lat, label: `${lat.toFixed(3)}, ${lon.toFixed(3)}` })
      // Static files only hold pre-computed points, so snap to the nearest one.
      const p = nearestPoi(site.points_of_interest, lon, lat)
      if (p) setPoint({ lon: p.lon, lat: p.lat, poiId: p.id, label: `${p.name} (nearest pre-computed point)` })
    },
    [site.points_of_interest],
  )
  const onMarkerClick = useCallback(
    (id: string) => {
      const p = site.points_of_interest.find((x) => x.id === id)
      if (p) selectPoi(p)
    },
    [site.points_of_interest, selectPoi],
  )

  if (n === 0) return <p className="state-msg">This site has no acquisitions yet.</p>

  return (
    <div className="site-page">
      <aside className="site-page__sidebar">
        <section className="panel">
          <h3>Radar layer</h3>
          <LayerControls
            layers={site.layers}
            layer={layer}
            onLayer={setLayer}
            opacity={opacity}
            onOpacity={setOpacity}
            showChange={showChange}
            onShowChange={setShowChange}
            compare={compare}
            onCompare={setCompare}
            dates={site.dates}
            fromIndex={fromIndex}
            toIndex={toIndex}
            onFrom={setFromIndex}
            onTo={setToIndex}
          />
        </section>
        <section className="panel">
          <h3>Legend</h3>
          <Legend layer={layer} showChange={showChange} />
        </section>
        <section className="panel">
          <h3>Story</h3>
          <StoryPanel siteName={site.name} />
        </section>
      </aside>

      <main className="site-page__map">
        {compare ? (
          <SwipeCompare
            corners={site.corners}
            left={{ imageUrl: layerUrl(site.id, layer, from), badge: `${label} · ${from}` }}
            right={{ imageUrl: layerUrl(site.id, layer, to), badge: `${label} · ${to}` }}
            markers={markers}
            onMapClick={onMapClick}
            onMarkerClick={onMarkerClick}
          />
        ) : (
          <SarMap
            corners={site.corners}
            imageUrl={layerUrl(site.id, layer, date)}
            imageOpacity={opacity}
            overlayUrl={showChange ? changeUrl(site.id, from, to) : null}
            badge={showChange ? `${label} · ${date}  |  change ${from} → ${to}` : `${label} · ${date}`}
            markers={markers}
            onMapClick={onMapClick}
            onMarkerClick={onMarkerClick}
          />
        )}
      </main>

      <footer className="site-page__bottom">
        {!compare && (
          <section className="panel site-page__time">
            <h3>Time</h3>
            <TimeSlider dates={site.dates} index={dateIndex} onChange={setDateIndex} />
          </section>
        )}
        <section className="panel">
          <h3>Change {from} → {to}</h3>
          <StatCards stats={stats} from={from} to={to} />
        </section>
        <section className="panel">
          <h3>{point ? point.label : 'Point over time'}</h3>
          <PointChart
            data={series}
            currentDate={compare ? undefined : date}
            emptyHint="Click the map or a place below to see how it changed."
          />
        </section>
        <section className="panel">
          <h3>Places</h3>
          <PoiList points={site.points_of_interest} selectedId={point?.poiId} onSelect={selectPoi} />
        </section>
      </footer>
    </div>
  )
}
