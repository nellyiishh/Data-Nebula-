import { LazyMount } from '../core/ui/LazyMount'
import type { SiteDetail } from '../features/sites/model/types'
import { FrameSlider } from '../features/timeline/components/FrameSlider'
import { Screen } from '../features/story/components/Screen'
import { DatePairControls, ExplorerMap, LayersPanel, PointBlock, TimelineBlock } from './ExplorerParts'
import { useExplorerState } from './useExplorerState'
import './TimeMachine.css'

// Story screen 03 "Earth Time Machine": every NISAR pass as a frame, with rain and one point's
// history on the same timeline. Same state and parts as the TRACE workspace.

// What the selected layer cannot tell you on its own. Wording stays within what the data and
// processing support (see the Data & science screen); keyed by layer kind, not by site.
const CAVEATS: Record<string, string> = {
  backscatter:
    'Brightness is how much of the radar pulse comes back, on one fixed dB stretch for every date. Roughness, slope facing the radar, soil moisture, snow and plants all change it, so a bright or dark patch alone does not identify a landslide.',
  change:
    'Coloured where the 3×3-smoothed HH moved past the threshold between the two dates. Wetter soil, snow or calibration can shift a whole scene at once, so compare with other pairs before reading a patch as ground change.',
  coherence:
    'How alike two passes are (0–1). Low coherence means the radar echo decorrelated: moving ground, but also snow, wet soil, growing plants or noise. Treat it as a place to look, not as proof that the slope moved.',
  displacement:
    'Motion along the radar line of sight (LOS), not vertical or downslope motion: + toward the satellite, − away. Each pair is relative to the site median, and fast motion decorrelates instead of showing as centimetres.',
}

type Params = Record<string, string | undefined>
interface Props {
  site: SiteDetail
  research: boolean
  params: Params
  setParams: (p: Params) => void
}

export function TimeMachine({ site, research, params, setParams }: Props) {
  const s = useExplorerState(site, params, setParams)

  return (
    <Screen id="time-machine" n={3} title="Earth Time Machine" text={s.se?.story.tracking} research={research} wide>
      <div className="explorer">
        <LazyMount className="explorer__map">
          <ExplorerMap site={site} s={s} />
          {/* Phones: the map fills the screen, so Play lives on it. Desktop uses the panel below. */}
          <div className="explorer__player">
            <FrameSlider labels={s.layer.frames.map((f) => f.label)} index={s.fIdx} onChange={s.actions.setFrame} playBlockedReason={s.playBlockedReason} />
          </div>
        </LazyMount>
        <aside className="explorer__side">
          <section className="panel">
            <h3>What to look at</h3>
            <LayersPanel s={s} research={research} />
          </section>
          <section className="panel">
            <h3>Compare</h3>
            <DatePairControls s={s} />
          </section>
          {CAVEATS[s.layer.kind] && (
            <section className="panel tm-caveat" aria-live="polite">
              <h3>Read with care · {s.layer.title}</h3>
              <p className="muted">{CAVEATS[s.layer.kind]}</p>
            </section>
          )}
        </aside>
      </div>

      <div className="tracking">
        <section className="panel tracking__time">
          <h3>Every pass · press Play</h3>
          <TimelineBlock site={site} s={s} />
        </section>
        <section className="panel">
          <h3>{s.pointTitle}</h3>
          <PointBlock site={site} s={s} />
        </section>
      </div>
    </Screen>
  )
}
