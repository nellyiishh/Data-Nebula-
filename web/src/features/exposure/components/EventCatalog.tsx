import type { SlopeEcho } from '../../sites/model/types'
import './ExposureCard.css'

// Owner: story. Registered natural events near the site (NASA Global Landslide Catalog style).

export function EventCatalog({ catalog }: { catalog: SlopeEcho['catalog'] }) {
  if (!catalog?.length) return <p className="state-msg">No registered events for this site yet.</p>
  return (
    <ol className="catalog">
      {[...catalog]
        .sort((a, b) => b.date.localeCompare(a.date))
        .map((e) => (
          <li key={`${e.date}-${e.name}`}>
            <time dateTime={e.date}>{e.date}</time>
            <span>
              <strong>{e.type}</strong> · {e.name}
            </span>
            {e.source.url ? (
              <a className="source-link" href={e.source.url} target="_blank" rel="noreferrer">
                {e.source.name}
              </a>
            ) : (
              <span className="source-link source-link--todo">{e.source.name}</span>
            )}
          </li>
        ))}
    </ol>
  )
}
