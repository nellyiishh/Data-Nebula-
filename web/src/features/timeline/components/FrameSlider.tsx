import { useEffect, useState } from 'react'
import './FrameSlider.css'

// Owner: Frontend 1 (map lead). Steps through a layer's frames (dates or date pairs); Play animates.

interface Props {
  labels: string[]
  index: number
  onChange: (index: number) => void
  frameMs?: number
}

export function FrameSlider({ labels, index, onChange, frameMs = 1000 }: Props) {
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!playing || labels.length < 2) return
    const t = setInterval(() => onChange((index + 1) % labels.length), frameMs)
    return () => clearInterval(t)
  }, [playing, index, labels.length, frameMs, onChange])

  if (labels.length === 0) return <p className="state-msg">No frames for this layer.</p>

  return (
    <div className="frame-slider">
      <button
        type="button"
        className="btn"
        aria-pressed={playing}
        aria-label={playing ? 'Pause animation' : 'Play animation'}
        onClick={() => setPlaying((p) => !p)}
        disabled={labels.length < 2}
      >
        {playing ? '❚❚' : '▶'}
      </button>
      <input
        type="range"
        min={0}
        max={labels.length - 1}
        step={1}
        value={index}
        aria-label="Radar frame"
        aria-valuetext={labels[index]}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <output className="frame-slider__label">{labels[index]}</output>
    </div>
  )
}
