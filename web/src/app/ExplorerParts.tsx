import { useState } from 'react'
import { SarMap } from '../core/map/SarMap'
import { PointPanel } from '../features/chart/components/PointPanel'
import { LayerControls } from '../features/compare/components/LayerControls'
import { Legend } from '../features/compare/components/Legend'
import { SwipeCompare } from '../features/compare/components/SwipeCompare'
import { ListenButton } from '../features/listen/ListenButton'
import type { SiteDetail } from '../features/sites/model/types'
import { FrameSlider } from '../features/timeline/components/FrameSlider'
import { RainTimeline } from '../features/timeline/components/RainTimeline'
import type { ExplorerState } from './useExplorerState'

// Building blocks shared by the story's Time Machine and the TRACE workspace. They read one
// ExplorerState, so both views always show the same map, frame, point and overlays.

interface Common {
  site: SiteDetail
  s: ExplorerState
}

export function ExplorerMap({ site, s }: Common) {
  const { layer, frame, aIdx, bIdx, markers, images, vectors, actions } = s
  const shared = { markers, images, vectors, onMapClick: actions.clickMap, onMarkerClick: actions.selectPoiId }
  return s.compare ? (
    <SwipeCompare
      corners={site.corners}
      left={{ imageUrl: layer.frames[aIdx].url, badge: s.badge(`A · ${layer.frames[aIdx].label}`) }}
      right={{ imageUrl: layer.frames[bIdx].url, badge: s.badge(`B · ${layer.frames[bIdx].label}`) }}
      {...shared}
    />
  ) : (
    <SarMap
      corners={site.corners}
      imageUrl={frame?.url}
      imageOpacity={s.opacity}
      contrast={s.contrast}
      terrain={s.terrain}
      badge={frame ? s.badge(frame.label) : undefined}
      {...shared}
    />
  )
}

export function LayersPanel({ s, research }: { s: ExplorerState; research: boolean }) {
  const { actions } = s
  return (
    <>
      <LayerControls
        layers={s.layers}
        layerId={s.layer.id}
        onLayer={actions.setLayer}
        opacity={s.opacity}
        onOpacity={actions.setOpacity}
        overlays={s.toggleable}
        shownOverlays={s.shownIds}
        onToggleOverlay={actions.toggleOverlay}
        research={research}
      />
      <div className="explorer__toggles">
        <button
          type="button"
          className="btn"
          aria-pressed={s.terrain}
          disabled={s.compare}
          onClick={() => actions.setTerrain(!s.terrain)}
          title="Drape the radar on a 3D elevation model. Elevation comes from a DEM, not from the radar."
        >
          3D terrain
        </button>
      </div>
      {research && !s.compare && (
        <label className="explorer__field" title="Radar images are dark until stretched; this changes the display only, not the data.">
          Contrast stretch
          <input type="range" min={-0.5} max={0.8} step={0.05} value={s.contrast} onChange={(e) => actions.setContrast(Number(e.target.value))} />
        </label>
      )}
      <div className="explorer__legend">
        <Legend layer={s.layer} overlays={s.shown} />
      </div>
    </>
  )
}

/** Date A / Date B selectors for comparing two observations. */
export function DatePairControls({ s }: { s: ExplorerState }) {
  const sel = (label: string, value: number, key: 'a' | 'b') => (
    <label className={`explorer__pair explorer__pair--${key}`}>
      <span className="mono">{label}</span>
      <select value={value} onChange={(e) => s.actions.setPair(key, Number(e.target.value))}>
        {s.layer.frames.map((f, i) => (
          <option key={f.key} value={i}>
            {f.label}
          </option>
        ))}
      </select>
    </label>
  )
  return (
    <div className="explorer__pairs">
      <button type="button" className="btn" aria-pressed={s.compare} onClick={() => s.actions.setCompare(!s.compare)}>
        Compare Date A ↔ Date B
      </button>
      {s.compare && (
        <>
          {sel('Date A', s.aIdx, 'a')}
          {sel('Date B', s.bIdx, 'b')}
        </>
      )}
    </div>
  )
}

export function TimelineBlock({ site, s, height = 150, width }: Common & { height?: number; width?: number }) {
  return (
    <>
      <FrameSlider labels={s.layer.frames.map((f) => f.label)} index={s.fIdx} onChange={s.actions.setFrame} playBlockedReason={s.playBlockedReason} />
      <RainTimeline rain={s.rain} passes={site.dates} event={s.event} activePass={s.frame?.date} onPassClick={s.actions.jumpToDate} height={height} width={width} />
    </>
  )
}

export function PointBlock({ site, s }: Common) {
  const [listenDate, setListenDate] = useState<string | undefined>()
  return (
    <PointPanel
      layer={s.layer}
      dates={site.dates}
      event={s.event}
      cursor={listenDate ?? s.frame?.date}
      backscatter={s.backscatter}
      extras={s.extras}
      points={site.points_of_interest}
      selectedId={s.poi?.id}
      pointLabel={s.poi?.note}
      onSelect={s.actions.selectPoi}
      renderExtra={(line) => (
        <ListenButton
          key={`${line.id}-${s.poi?.id}`}
          label={line.label}
          dates={line.points.map((pt) => pt.date)}
          values={line.points.map((pt) => pt.value)}
          onStep={setListenDate}
        />
      )}
    />
  )
}

