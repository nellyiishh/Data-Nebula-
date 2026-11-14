import type { SlopeEcho } from '../../sites/model/types'
import './ExposureCard.css'

// Owner: Frontend 4. "Who lives below": counts near the slide. Proximity, not hazard.

export function ExposureCard({ exposure, research }: { exposure: SlopeEcho['exposure']; research: boolean }) {
  if (!exposure) return <p className="state-msg">Exposure data not available for this site yet.</p>
  return (
    <div className="exposure">
      <div className="exposure__stats">
        <Stat value={String(exposure.buildings)} label={`buildings within ${exposure.radius_km} km`} />
        <Stat value={`${exposure.roads_km} km`} label="of road" />
        <Stat value={`${exposure.distance_km} km`} label={`to ${exposure.nearest_settlement}`} />
      </div>
      <p className="muted exposure__note">{exposure.method}</p>
      <p className="muted exposure__note">Being close to a slope does not by itself mean being in danger.</p>
      {research && (
        <p className="muted exposure__note">
          Source:{' '}
          {exposure.source.url ? (
            <a href={exposure.source.url} target="_blank" rel="noreferrer">
              {exposure.source.name}
            </a>
          ) : (
            exposure.source.name
          )}
        </p>
      )}
    </div>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="exposure__stat">
      <strong>{value}</strong>
      <span className="muted">{label}</span>
    </div>
  )
}
