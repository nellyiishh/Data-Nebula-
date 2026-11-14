import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap, Marker, NavigationControl, ScaleControl } from 'maplibre-gl'
import type { Coordinates, ImageSource, MapOptions } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import './SarMap.css'

// Shared map used by the time-slider view and by both halves of the swipe compare.
// It knows nothing about sites or features: it draws one radar image, one optional
// overlay (change map), markers, and reports clicks.

export type Corners = Coordinates

export interface MapMarker {
  id: string
  lon: number
  lat: number
  label: string
}

export interface SarMapProps {
  corners: Corners
  imageUrl: string | null
  imageOpacity?: number
  overlayUrl?: string | null
  /** Shown in the corner of the map: every image must show its date and polarisation. */
  badge?: string
  markers?: MapMarker[]
  onMapClick?: (lon: number, lat: number) => void
  onMarkerClick?: (id: string) => void
  onReady?: (map: MapLibreMap) => void
  showControls?: boolean
}

const BASEMAP: MapOptions['style'] = {
  version: 8,
  sources: {
    base: {
      type: 'raster',
      tiles: ['a', 'b', 'c'].map((s) => `https://${s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png`),
      tileSize: 256,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
    },
  },
  layers: [{ id: 'base', type: 'raster', source: 'base' }],
}

function setImage(map: MapLibreMap, id: string, url: string | null, corners: Corners, opacity: number) {
  const src = map.getSource(id) as ImageSource | undefined
  if (!url) {
    if (map.getLayer(id)) map.removeLayer(id)
    if (src) map.removeSource(id)
    return
  }
  if (src) {
    src.updateImage({ url, coordinates: corners })
  } else {
    map.addSource(id, { type: 'image', url, coordinates: corners })
    map.addLayer({ id, type: 'raster', source: id, paint: { 'raster-fade-duration': 0 } })
  }
  map.setPaintProperty(id, 'raster-opacity', opacity)
}

export function SarMap({
  corners,
  imageUrl,
  imageOpacity = 1,
  overlayUrl = null,
  badge,
  markers = [],
  onMapClick,
  onMarkerClick,
  onReady,
  showControls = true,
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
        fitBoundsOptions: { padding: 40 },
        attributionControl: { compact: true },
      })
    } catch (e) {
      // Usually "WebGL2 is required". Keep the rest of the page usable instead of a blank screen.
      setInitError(e instanceof Error ? e.message : String(e))
      return
    }
    if (showControls) {
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
    if (ready) mapRef.current!.fitBounds([corners[3], corners[1]], { padding: 40, duration: 600 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, cornersKey])

  useEffect(() => {
    if (ready) setImage(mapRef.current!, 'sar', imageUrl, corners, imageOpacity)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, imageUrl, imageOpacity, cornersKey])

  useEffect(() => {
    if (ready) setImage(mapRef.current!, 'overlay', overlayUrl, corners, 0.9)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, overlayUrl, cornersKey])

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
