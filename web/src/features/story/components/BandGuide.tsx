import { BANDS } from '../content'
import './story.css'

// Owner: story. Why NISAR's L-band matters on vegetated mountain slopes.

export function BandGuide() {
  return (
    <table className="bands">
      <caption className="muted">Longer waves reach deeper into vegetation (not into the ground).</caption>
      <thead>
        <tr>
          <th>Band</th>
          <th>Wave</th>
          <th>Reaches</th>
          <th className="bands__depth-h">Depth into canopy</th>
        </tr>
      </thead>
      <tbody>
        {BANDS.map((b) => (
          <tr key={b.band} className={b.band === 'L' ? 'bands__nisar' : undefined}>
            <th scope="row">{b.band}</th>
            <td>{b.wavelength}</td>
            <td>
              {b.interacts}
              <span className="muted bands__sat">{b.satellites}</span>
            </td>
            <td className="bands__depth">
              <span style={{ width: `${b.depth * 100}%` }} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
