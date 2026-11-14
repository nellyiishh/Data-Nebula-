import './StoryPanel.css'

// Owner: Frontend 4 (story and design). These sections answer the three questions the
// challenge asks. TODO(story): replace the draft text with the real site story.

export function StoryPanel({ siteName }: { siteName: string }) {
  return (
    <article className="story">
      <h2>{siteName}</h2>

      <section>
        <h3>What radar sees</h3>
        <p>
          NISAR sends its own L-band microwave pulses (~24 cm wavelength) and records the echo, day or night and
          through cloud. Rough surfaces such as fresh debris bounce more energy back (bright); smooth water reflects
          it away (dark).
        </p>
      </section>

      <section>
        <h3>What changed and why</h3>
        <p className="draft">
          TODO(story): describe the event — when, what happened on the ground, and which physical driver (heavy
          rain, glacier melt, slope failure…) explains the brighter/darker areas on the change map.
        </p>
      </section>

      <section>
        <h3>Which polarisation shows it</h3>
        <p>
          <strong>HH</strong> responds to surface roughness, so a fresh mudflow scar turns brighter.{' '}
          <strong>HV</strong> responds to vegetation volume, so stripped slopes turn darker. Comparing both separates
          &quot;new debris&quot; from &quot;lost vegetation&quot;.
        </p>
      </section>

      <section>
        <h3>What NISAR could do next</h3>
        <p className="draft">
          TODO(story): early warning from slope motion (InSAR) before a flow, rapid damage maps after one, seasonal
          monitoring of glacial lakes that feed mudflows.
        </p>
      </section>
    </article>
  )
}
