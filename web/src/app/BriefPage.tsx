import { useState } from 'react'
import { ReportBody } from '../features/report/components/ReportBody'
import { useRain } from '../features/sites/api'
import type { SiteDetail } from '../features/sites/model/types'

// Printable investigation report (?site=…&view=brief): browser Print → Save as PDF.

export function BriefPage({ site }: { site: SiteDetail }) {
  const rain = useRain(site)
  const [generated] = useState(() => new Date().toISOString().slice(0, 10))
  return (
    <article className="brief">
      <div className="brief__actions no-print">
        <button type="button" className="btn" onClick={() => window.print()}>
          Print / save as PDF
        </button>
        <a className="btn" href={`?site=${site.id}`}>
          Back to the map
        </a>
      </div>
      <ReportBody site={site} rain={rain} generated={generated} />
    </article>
  )
}
