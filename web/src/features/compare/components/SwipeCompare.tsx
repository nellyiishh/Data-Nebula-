import { useCallback, useEffect, useRef, useState } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { SarMap } from '../../../core/map/SarMap'
import type { Corners, MapMarker } from '../../../core/map/SarMap'
import './SwipeCompare.css'

// Owner: Frontend 2 (compare). Two synced maps stacked; the right one is clipped by the divider.

interface Side {
  imageUrl: string
  badge: string
}
interface Props {
  corners: Corners
  left: Side
  right: Side
  markers?: MapMarker[]
  onMapClick?: (lon: number, lat: number) => void
  onMarkerClick?: (id: string) => void
}

export function SwipeCompare({ corners, left, right, markers, onMapClick, onMarkerClick }: Props) {
  const [pos, setPos] = useState(50)
  const wrapRef = useRef<HTMLDivElement>(null)
  const maps = useRef<{ a?: MapLibreMap; b?: MapLibreMap }>({})

  const sync = useCallback(() => {
    const { a, b } = maps.current
    if (!a || !b) return
    let busy = false
    const follow = (from: MapLibreMap, to: MapLibreMap) => () => {
      if (busy) return
      busy = true
      to.jumpTo({ center: from.getCenter(), zoom: from.getZoom(), bearing: from.getBearing(), pitch: from.getPitch() })
      busy = false
    }
    a.on('move', follow(a, b))
    b.on('move', follow(b, a))
  }, [])

  const onDrag = useCallback((clientX: number) => {
    const r = wrapRef.current!.getBoundingClientRect()
    setPos(Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100)))
  }, [])

  const [dragging, setDragging] = useState(false)
  useEffect(() => {
    if (!dragging) return
    const move = (e: PointerEvent) => onDrag(e.clientX)
    const up = () => setDragging(false)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
  }, [dragging, onDrag])

  return (
    <div className="swipe" ref={wrapRef}>
      <SarMap
        corners={corners}
        imageUrl={left.imageUrl}
        badge={left.badge}
        markers={markers}
        onMapClick={onMapClick}
        onMarkerClick={onMarkerClick}
        showControls={false}
        onReady={(m) => {
          maps.current.a = m
          sync()
        }}
      />
      <div className="swipe__right" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
        <SarMap
          corners={corners}
          imageUrl={right.imageUrl}
          markers={markers}
          onMapClick={onMapClick}
          onMarkerClick={onMarkerClick}
          onReady={(m) => {
            maps.current.b = m
            sync()
          }}
        />
        <div className="swipe__badge-right">{right.badge}</div>
      </div>
      <div className="swipe__divider" style={{ left: `${pos}%` }}>
        <button
          type="button"
          className="swipe__handle"
          aria-label="Drag to compare dates"
          onPointerDown={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft') setPos((p) => Math.max(0, p - 5))
            if (e.key === 'ArrowRight') setPos((p) => Math.min(100, p + 5))
          }}
        >
          ⇆
        </button>
      </div>
    </div>
  )
}
