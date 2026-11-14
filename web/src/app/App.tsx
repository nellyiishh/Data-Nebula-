import { useState } from 'react'
import { isStatic } from '../core/api/client'
import { useSite, useSites } from '../features/sites/api'
import { SitePage } from './SitePage'
import './App.css'

export function App() {
  const sites = useSites()
  const [chosenId, setSiteId] = useState<string | null>(null)
  const siteId = chosenId ?? (sites.status === 'ready' ? (sites.data[0]?.id ?? null) : null)

  const site = useSite(siteId)

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <strong>Data Nebula</strong>
          <span className="muted">Dancing with the SARs · NISAR surface change</span>
        </div>
        {sites.status === 'ready' && sites.data.length > 1 && (
          <select
            aria-label="Study site"
            className="app__site-select"
            value={siteId ?? ''}
            onChange={(e) => setSiteId(e.target.value)}
          >
            {sites.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.change_type}
              </option>
            ))}
          </select>
        )}
        {isStatic && <span className="app__mode">static data</span>}
      </header>

      <div className="app__body">
        {sites.status === 'loading' && <p className="state-msg app__msg">Loading sites…</p>}
        {sites.status === 'error' && <p className="state-msg error app__msg">Could not load sites: {sites.error}</p>}
        {sites.status === 'ready' && sites.data.length === 0 && <p className="state-msg app__msg">No sites yet.</p>}
        {site.status === 'error' && <p className="state-msg error app__msg">Could not load site: {site.error}</p>}
        {site.status === 'ready' && <SitePage key={site.data.id} site={site.data} />}
      </div>
    </div>
  )
}
