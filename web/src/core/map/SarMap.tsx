import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap, Marker, NavigationControl, ScaleControl } from 'maplibre-gl'
import type { Coordinates, GeoJSONSourceSpecification, ImageSource, MapOptions } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import './SarMap.css'

// Shared map used by every screen. It knows nothing about sites or features: it draws one
// main raster, extra raster overlays, GeoJSON overlays and markers, and reports clicks.

export type Corners = Coordinates

export interface MapMarker {
  id: string
  lon: number
  lat: number
  label: string
}
export interface ImageOverlay {
  id: string
  url: string
  opacity?: number
}
export interface VectorOverlay {
  id: string
  url: string
  /** polygon: filled outline · outline: dashed line · exposure: points (buildings) + lines (roads) */
  style: 'polygon' | 'outline' | 'exposure'
  /** Any CSS colour or var(--token). */
  color: string
}

export interface SarMapProps {
  /** Area to fit: top-left, top-right, bottom-right, bottom-left. */
  corners: Corners
  imageUrl?: string | null
  imageOpacity?: number
  images?: ImageOverlay[]
  vectors?: VectorOverlay[]
  /** Shown in the corner of the map: every radar image must show its date and polarisation. */
  badge?: string
  markers?: MapMarker[]
  onMapClick?: (lon: number, lat: number) => void
  onMarkerClick?: (id: string) => void
  onReady?: (map: MapLibreMap) => void
  showControls?: boolean
  interactive?: boolean
  padding?: number
}

const BASEMAP: MapOptions['style'] = {
  version: 8,
  sources: {
    base: {
      type: 'raster',
      tiles: ['a', 'b', 'c'].map((s) => `https://${s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png`),
      tileSize: 256,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
    },
  },
  layers: [{ id: 'base', type: 'raster', source: 'base' }],
}

/** MapLibre cannot read CSS variables, so resolve var(--x) against :root. */
function resolveColor(c: string) {
  const m = /^var\((--[\w-]+)\)$/.exec(c)
  return m ? getComputedStyle(document.documentElement).getPropertyValue(m[1]).trim() || '#ffffff' : c
}

function setImage(map: MapLibreMap, id: string, url: string | null | undefined, corners: Corners, opacity: number) {
  const src = map.getSource(id) as ImageSource | undefined
  if (!url) {
    if (map.getLayer(id)) map.removeLayer(id)
    if (src) map.removeSource(id)
    return
  }
  if (src) src.updateImage({ url, coordinates: corners })
  else {
    map.addSource(id, { type: 'image', url, coordinates: corners })
    // Keep images under vector overlays.
    const firstVector = map.getStyle().layers.find((l) => l.id.startsWith('vec:'))?.id
    map.addLayer({ id, type: 'raster', source: id, paint: { 'raster-fade-duration': 0 } }, firstVector)
  }
  map.setPaintProperty(id, 'raster-opacity', opacity)
}

function addVector(map: MapLibreMap, v: VectorOverlay) {
  const sid = `vec:${v.id}`
  const color = resolveColor(v.color)
  map.addSource(sid, { type: 'geojson', data: v.url } satisfies GeoJSONSourceSpecification)
  if (v.style === 'polygon') {
    map.addLayer({ id: `${sid}:fill`, type: 'fill', source: sid, paint: { 'fill-color': color, 'fill-opacity': 0.12 } })
    map.addLayer({ id: `${sid}:line`, type: 'line', source: sid, paint: { 'line-color': color, 'line-width': 2 } })
  } else if (v.style === 'outline') {
    map.addLayer({
      id: `${sid}:line`,
      type: 'line',
      source: sid,
      paint: { 'line-color': color, 'line-width': 1.5, 'line-dasharray': [3, 3] },
    })
  } else {
    map.addLayer({
      id: `${sid}:line`,
      type: 'line',
      source: sid,
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: { 'line-color': color, 'line-width': 3, 'line-opacity': 0.8 },
    })
    map.addLayer({
      id: `${sid}:pt`,
      type: 'circle',
      source: sid,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: { 'circle-color': color, 'circle-radius': 3.5, 'circle-stroke-color': '#000', 'circle-stroke-width': 1 },
    })
  }
}

function removeVector(map: MapLibreMap, id: string) {
  const sid = `vec:${id}`
  for (const suffix of [':fill', ':line', ':pt']) if (map.getLayer(sid + suffix)) map.removeLayer(sid + suffix)
  if (map.getSource(sid)) map.removeSource(sid)
}

export function SarMap({
  corners,
  imageUrl,
  imageOpacity = 1,
  images = [],
  vectors = [],
  badge,
  markers = [],
  onMapClick,
  onMarkerClick,
  onReady,
  showControls = true,
  interactive = true,
  padding = 40,
}: SarMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [ready, setReady] = useState(false)
  const [initError, setInitError] = useState<string | null>(null)

  // Keep latest callbacks without re-creating the map.
  const handlers = useRef({ onMapClick, onMarkerClick, onReady })
  handlers.current = { onMapClick, onMarkerClick, onReady }

  useEffect(() => {
    let map: MapLibreMap
    try {
      map = new MapLibreMap({
        container: containerRef.current!,
        style: BASEMAP,
        bounds: [corners[3], corners[1]],
        fitBoundsOptions: { padding },
        attributionControl: { compact: true },
        interactive,
        cooperativeGestures: interactive, // page scroll is not hijacked by the map
      })
    } catch (e) {
      // Usually "WebGL2 is required". Keep the rest of the page usable instead of a blank screen.
      setInitError(e instanceof Error ? e.message : String(e))
      return
    }
    if (showControls && interactive) {
      map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
      map.addControl(new ScaleControl(), 'bottom-left')
    }
    map.on('load', () => {
      setReady(true)
      handlers.current.onReady?.(map)
    })
    map.on('click', (e) => handlers.current.onMapClick?.(e.lngLat.lng, e.lngLat.lat))
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
    // Map is created once; corners changes are handled by the fitBounds effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const cornersKey = JSON.stringify(corners)
  useEffect(() => {
    if (ready) mapRef.current!.fitBounds([corners[3], corners[1]], { padding, duration: 600 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, cornersKey])

  useEffect(() => {
    if (ready) setImage(mapRef.current!, 'sar', imageUrl, corners, imageOpacity)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, imageUrl, imageOpacity, cornersKey])

  const imagesKey = JSON.stringify(images)
  const shownImages = useRef<string[]>([])
  useEffect(() => {
    if (!ready) return
    const map = mapRef.current!
    for (const id of shownImages.current) if (!images.some((i) => `img:${i.id}` === id)) setImage(map, id, null, corners, 1)
    for (const i of images) setImage(map, `img:${i.id}`, i.url, corners, i.opacity ?? 1)
    shownImages.current = images.map((i) => `img:${i.id}`)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, imagesKey, cornersKey])

  const vectorsKey = JSON.stringify(vectors)
  const shownVectors = useRef<string[]>([])
  useEffect(() => {
    if (!ready) return
    const map = mapRef.current!
    for (const id of shownVectors.current) removeVector(map, id)
    for (const v of vectors) addVector(map, v)
    shownVectors.current = vectors.map((v) => v.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, vectorsKey])

  const markersKey = JSON.stringify(markers)
  useEffect(() => {
    if (!ready) return
    const created = markers.map((m) => {
      const el = document.createElement('button')
      el.className = 'sar-marker'
      el.type = 'button'
      el.title = m.label
      el.setAttribute('aria-label', m.label)
      el.addEventListener('click', (ev) => {
        ev.stopPropagation()
        handlers.current.onMarkerClick?.(m.id)
      })
      return new Marker({ element: el }).setLngLat([m.lon, m.lat]).addTo(mapRef.current!)
    })
    return () => created.forEach((mk) => mk.remove())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, markersKey])

  return (
    <div className="sar-map">
      <div ref={containerRef} className="sar-map__canvas" />
      {badge && <div className="sar-map__badge">{badge}</div>}
      {initError && (
        <p className="state-msg error sar-map__error" role="alert">
          The map could not start in this browser: {initError}
        </p>
      )}
    </div>
  )
}
