import { useSite, useSites } from '../features/sites/api'
import { useUrlState } from '../core/url/useUrlState'
import { PROJECT } from '../features/story/content'
import { BriefPage } from './BriefPage'
import { SitePage } from './SitePage'
import { Workspace } from './Workspace'
import './App.css'

export function App() {
  const [params, setParams] = useUrlState()
  const sites = useSites()
  const siteId = params.site ?? (sites.status === 'ready' ? (sites.data[0]?.id ?? null) : null)
  const site = useSite(siteId)
  const research = params.mode === 'research'

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

  return (
    <div className="app">
      <header className="app__header">
        <a className="app__brand" href="#top">
          <strong>{PROJECT.name}</strong>
          <span className="muted">{PROJECT.fullName} · Dancing with the SARs</span>
        </a>
        <a className="btn btn--primary app__open" href={`?view=app${siteId ? `&site=${siteId}` : ''}`}>
          Open workspace
        </a>
        <div className="mode-toggle" role="group" aria-label="Detail level">
          <button type="button" className="btn" aria-pressed={!research} onClick={() => setParams({ mode: undefined })}>
            Explore
          </button>
          <button type="button" className="btn" aria-pressed={research} onClick={() => setParams({ mode: 'research' })}>
            Research
          </button>
        </div>
      </header>

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
        {site.status === 'ready' && sites.status === 'ready' && (
          <SitePage key={site.data.id} site={site.data} sites={sites.data} research={research} params={params} setParams={setParams} />
        )}
      </main>
    </div>
  )
}
