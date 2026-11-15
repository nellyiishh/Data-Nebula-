import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap, Marker, NavigationControl, ScaleControl, setWorkerUrl } from 'maplibre-gl'
import type { Coordinates, GeoJSONSourceSpecification, ImageSource, MapOptions } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'
import './SarMap.css'
import { notify } from '../ui/notify'

// MapLibre looks for its worker file next to its own script. Vite moves that script (dev
// pre-bundle, build chunk) without the worker, so GeoJSON overlays never draw. `?url` makes
// Vite serve and ship the worker, and this points MapLibre at it.
setWorkerUrl(workerUrl)

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
  /** Drape everything on a 3D elevation model (DEM), tilted. */
  terrain?: boolean
  /** Contrast stretch for the main raster, −1…1 (0 = as delivered). */
  contrast?: number
}

// Open elevation tiles (AWS Open Data "Terrain Tiles", terrarium encoding, no key).
// Elevation comes from a DEM (SRTM and others), not from the radar image.
const DEM_SOURCE = {
  type: 'raster-dem' as const,
  tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
  encoding: 'terrarium' as const,
  tileSize: 256,
  maxzoom: 14,
  attribution: 'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/">AWS Terrain Tiles</a> (SRTM and others)',
}

function setTerrain(map: MapLibreMap, on: boolean) {
  if (on) {
    if (!map.getSource('dem')) map.addSource('dem', DEM_SOURCE)
    if (!map.getLayer('hillshade'))
      // Above the basemap, below the radar image.
      map.addLayer(
        { id: 'hillshade', type: 'hillshade', source: 'dem', paint: { 'hillshade-exaggeration': 0.4 } },
        map.getLayer('sar') ? 'sar' : undefined,
      )
    map.setTerrain({ source: 'dem', exaggeration: 1.6 })
    map.easeTo({ pitch: 62, bearing: -20, duration: 900 })
  } else {
    map.setTerrain(null)
    if (map.getLayer('hillshade')) map.removeLayer('hillshade')
    map.easeTo({ pitch: 0, bearing: 0, duration: 600 })
  }
}

const BASEMAP: MapOptions['style'] = {
  version: 8,
  sources: {
    base: {
      type: 'raster',
      // Esri Dark Gray Canvas needs no key (CARTO's free tiles now return an "API KEY REQUIRED" watermark).
      // Esri's URL order is {z}/{y}/{x}.
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      maxzoom: 16,
      attribution:
        'Basemap © <a href="https://www.esri.com/">Esri</a>, HERE, Garmin, © OpenStreetMap contributors',
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
  terrain = false,
  contrast = 0,
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
      const msg = e instanceof Error ? e.message : String(e)
      setInitError(msg)
      notify(`The map could not start: ${msg}`)
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
    // Source/tile failures (offline, blocked host) otherwise only reach the console.
    map.on('error', (e) => {
      const source = (e as { sourceId?: string }).sourceId
      notify(source === 'dem' ? '3D elevation data could not be loaded.' : 'Some map data could not be loaded.')
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

  useEffect(() => {
    const map = mapRef.current
    if (ready && map?.getLayer('sar')) map.setPaintProperty('sar', 'raster-contrast', contrast)
  }, [ready, contrast, imageUrl])

  const firstTerrainRun = useRef(true)
  useEffect(() => {
    if (!ready) return
    // Skip the initial "off" so a flat map does not animate on load.
    if (firstTerrainRun.current && !terrain) return
    firstTerrainRun.current = false
    setTerrain(mapRef.current!, terrain)
  }, [ready, terrain])

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
