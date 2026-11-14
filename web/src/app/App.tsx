import { Brand } from '../core/ui/Brand'
import { useSmoothAnchors } from '../core/ui/useSmoothAnchors'
import { useSite, useSites } from '../features/sites/api'
import { useUrlState } from '../core/url/useUrlState'
import { PROJECT } from '../features/story/content'
import { BriefPage } from './BriefPage'
import { EveryonePage } from './EveryonePage'
import { SitePage } from './SitePage'
import { Workspace } from './Workspace'
import './App.css'

// Two sections share one header: "For everyone" (plain, for curious people) and
// "For specialists" (the story, workspace and report). ?section=everyone picks the first;
// no parameter keeps the specialist story, so existing links still open what they did.

type Section = 'everyone' | 'specialists'

export function App() {
  const [params, setParams] = useUrlState()
  useSmoothAnchors()
  const sites = useSites()
  // An unknown ?site= (e.g. an old link to the removed demo site) falls back to the first real site.
  const known = sites.status === 'ready' ? sites.data : []
  const siteId =
    sites.status !== 'ready' ? null : known.some((s) => s.id === params.site) ? params.site! : (known[0]?.id ?? null)
  const site = useSite(siteId)
  // The specialist section always shows full detail (Explore and Research were merged).
  const research = true
  const section: Section = params.section === 'everyone' ? 'everyone' : 'specialists'

  if (params.view === 'app') {
    if (site.status === 'ready' && sites.status === 'ready')
      return <Workspace key={site.data.id} site={site.data} sites={sites.data} research={research} params={params} setParams={setParams} />
    if (site.status === 'error') return <p className="state-msg error app__msg">Could not load site: {site.error}</p>
    if (sites.status === 'error') return <p className="state-msg error app__msg">Could not load sites: {sites.error}</p>
    return <p className="state-msg app__msg">Loading…</p>
  }

  if (params.view === 'brief') {
    if (site.status === 'ready') return <BriefPage site={site.data} />
    if (site.status === 'error') return <p className="state-msg error app__msg">Could not load site: {site.error}</p>
    return <p className="state-msg app__msg">Loading…</p>
  }

  const goSection = (s: Section) => {
    setParams({ section: s === 'everyone' ? 'everyone' : undefined })
    window.scrollTo({ top: 0 })
  }

  return (
    <div className="app">
      <header className="app__header">
        <Brand name={PROJECT.name} subtitle={PROJECT.fullName} />
        <nav className="section-switch" aria-label="Section">
          <button type="button" aria-current={section === 'everyone' ? 'page' : undefined} onClick={() => goSection('everyone')}>
            For everyone
          </button>
          <button type="button" aria-current={section === 'specialists' ? 'page' : undefined} onClick={() => goSection('specialists')}>
            For specialists
          </button>
        </nav>
      </header>

      {section === 'specialists' && (
        <div className="app__toolbar">
          <a className="btn btn--primary app__open" href={`?view=app${siteId ? `&site=${siteId}` : ''}`}>
            Open workspace
          </a>
        </div>
      )}

      {site.status === 'ready' && site.data.source === 'demo' && (
        <p className="demo-banner" role="note">
          Demo data: these images and numbers are synthetic, made to build the app. They are not NISAR measurements.
        </p>
      )}

      <main id="top" className="app__body">
        {sites.status === 'loading' && <p className="state-msg app__msg">Loading sites…</p>}
        {sites.status === 'error' && <p className="state-msg error app__msg">Could not load sites: {sites.error}</p>}
        {sites.status === 'ready' && sites.data.length === 0 && <p className="state-msg app__msg">No sites prepared yet.</p>}
        {site.status === 'error' && <p className="state-msg error app__msg">Could not load site: {site.error}</p>}
        {site.status === 'ready' && sites.status === 'ready' && section === 'specialists' && (
          <SitePage key={site.data.id} site={site.data} sites={sites.data} research={research} params={params} setParams={setParams} />
        )}
        {site.status === 'ready' && sites.status === 'ready' && section === 'everyone' && (
          <EveryonePage
            key={site.data.id}
            site={site.data}
            sites={sites.data}
            onPickSite={(id) => setParams({ site: id })}
            onOpenSpecialists={() => goSection('specialists')}
          />
        )}
      </main>
    </div>
  )
}
