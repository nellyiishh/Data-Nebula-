import { useMemo } from 'react'
import { isStatic } from '../core/api/client'
import type { MapMarker } from '../core/map/SarMap'
import { usePreloadImages } from '../core/map/usePreloadImages'
import { usePointExtras, useRain, useTimeSeries } from '../features/sites/api'
import type { PointQuery } from '../features/sites/api'
import { buildLayers, frameIndexFor } from '../features/sites/model/layers'
import type { PointOfInterest, SiteDetail } from '../features/sites/model/types'
import { toMapOverlays } from './mapOverlays'

// Map + timeline state shared by the story's Earth Time Machine and the TRACE workspace.
// Everything lives in the URL so any view can be shared as a link:
// layer, f (frame key), cmp (compare), a/b (Date A/B index), ov (overlays), pt (point),
// op (opacity), t3d (3D terrain), ct (contrast).

type Params = Record<string, string | undefined>

const DEFAULT_OVERLAYS = 'radar_blind,scar'
const ALWAYS_OFF_IN_RADAR = ['exposure', 'aoi']

function nearestPoi(points: PointOfInterest[], lon: number, lat: number) {
  let best: PointOfInterest | undefined
  let bestD = Infinity
  for (const p of points) {
    const d = (p.lon - lon) ** 2 + (p.lat - lat) ** 2
    if (d < bestD) [best, bestD] = [p, d]
  }
  return best
}

export function useExplorerState(site: SiteDetail, params: Params, setParams: (p: Params) => void, opts: { extraOverlays?: string[] } = {}) {
  const se = site.slope_echo
  // Optical has its own comparison (Radar Vision); the explorer animates radar only.
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

  const toggleable = se?.overlays.filter((o) => !ALWAYS_OFF_IN_RADAR.includes(o.id)) ?? []
  const shownIds = (params.ov ?? DEFAULT_OVERLAYS).split(',').filter(Boolean)
  const forced = se?.overlays.filter((o) => opts.extraOverlays?.includes(o.id)) ?? []
  const shown = [...toggleable.filter((o) => shownIds.includes(o.id)), ...forced]
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

  const markers: MapMarker[] = site.points_of_interest.map((p) => ({ id: p.id, lon: p.lon, lat: p.lat, label: p.name }))
  const event = se ? { date: se.event.date, label: 'event' } : undefined
  const badge = (label: string) => `${layer.title} · ${label}${site.source === 'demo' ? ' · DEMO' : ''}`

  const actions = {
    setFrame: (i: number) => setParams({ f: layer.frames[i]?.key }),
    jumpToDate: (d: string) => setParams({ f: layer.frames[frameIndexFor(layer, d)]?.key }),
    setLayer: (id: string) => {
      const next = layers.find((l) => l.id === id)!
      setParams({ layer: id, f: next.frames[frameIndexFor(next, frame?.date)]?.key, a: undefined, b: undefined })
    },
    toggleOverlay: (id: string) =>
      setParams({ ov: (shownIds.includes(id) ? shownIds.filter((x) => x !== id) : [...shownIds, id]).join(',') || ',' }),
    selectPoi: (p: PointOfInterest) => setParams({ pt: p.id }),
    selectPoiId: (id: string) => setParams({ pt: id }),
    clickMap: (lon: number, lat: number) => {
      if (!isStatic) return setParams({ pt: `@${lon.toFixed(5)},${lat.toFixed(5)}` })
      // Static files only hold pre-computed points, so snap to the nearest one.
      const p = nearestPoi(site.points_of_interest, lon, lat)
      if (p) setParams({ pt: p.id })
    },
    setCompare: (on: boolean) => setParams({ cmp: on ? '1' : undefined }),
    setPair: (key: 'a' | 'b', i: number) => setParams({ [key]: String(i) }),
    setOpacity: (v: number) => setParams({ op: String(v) }),
    setTerrain: (on: boolean) => setParams({ t3d: on ? '1' : undefined }),
    setContrast: (v: number) => setParams({ ct: String(v) }),
  }

  return {
    se,
    layers,
    layer,
    frame,
    fIdx,
    compare,
    aIdx,
    bIdx,
    opacity,
    terrain,
    contrast,
    toggleable,
    shownIds,
    shown,
    images,
    vectors,
    poi,
    clicked,
    backscatter,
    extras,
    rain,
    markers,
    event,
    badge,
    pointTitle: poi ? poi.name : clicked ? 'Clicked point' : 'One place over time',
    actions,
  }
}

export type ExplorerState = ReturnType<typeof useExplorerState>
