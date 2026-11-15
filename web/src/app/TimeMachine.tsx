import { LazyMount } from '../core/ui/LazyMount'
import type { SiteDetail } from '../features/sites/model/types'
import { FrameSlider } from '../features/timeline/components/FrameSlider'
import { Screen } from '../features/story/components/Screen'
import { DatePairControls, ExplorerMap, LayersPanel, PointBlock, TimelineBlock } from './ExplorerParts'
import { useExplorerState } from './useExplorerState'
import './TimeMachine.css'

// Story screen 03 "Earth Time Machine": every NISAR pass as a frame, with rain and one point's
// history on the same timeline. Same state and parts as the TRACE workspace.

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
