import { useEffect, useState } from 'react'
import './TimeSlider.css'

// Owner: Frontend 1 (map lead). Steps through acquisition dates; Play animates them.

interface Props {
  dates: string[]
  index: number
  onChange: (index: number) => void
  frameMs?: number
}

export function TimeSlider({ dates, index, onChange, frameMs = 900 }: Props) {
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!playing || dates.length < 2) return
    const t = setInterval(() => onChange((index + 1) % dates.length), frameMs)
    return () => clearInterval(t)
  }, [playing, index, dates.length, frameMs, onChange])

  if (dates.length === 0) return <p className="state-msg">No dates for this site yet.</p>

  return (
    <div className="time-slider">
      <button
        type="button"
        className="btn"
        aria-pressed={playing}
        aria-label={playing ? 'Pause animation' : 'Play animation'}
        onClick={() => setPlaying((p) => !p)}
      >
        {playing ? '❚❚' : '▶'}
      </button>
      <input
        type="range"
        min={0}
        max={dates.length - 1}
        step={1}
        value={index}
        aria-label="Acquisition date"
        aria-valuetext={dates[index]}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <time className="time-slider__date" dateTime={dates[index]}>
        {dates[index]}
      </time>
      <div className="time-slider__ticks" aria-hidden>
        {dates.map((d, i) => (
          <span key={d} className={i === index ? 'active' : ''} />
        ))}
      </div>
    </div>
  )
}
