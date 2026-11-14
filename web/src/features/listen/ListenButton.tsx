import { useEffect } from 'react'
import { useSonification } from './useSonification'

// Owner: chart. Button + caption for the sonification of the selected point's series.

interface Props {
  label: string
  dates: string[]
  values: (number | null)[]
  onStep?: (date: string | undefined) => void
}

export function ListenButton({ label, dates, values, onStep }: Props) {
  const { play, stop, playing, step } = useSonification(values)
  const current = step === null ? undefined : dates[step]
  useEffect(() => onStep?.(current), [current, onStep])

  return (
    <div className="listen">
      <button
        type="button"
        className="btn"
        aria-pressed={playing}
        onClick={playing ? stop : play}
        disabled={values.every((v) => v === null)}
      >
        {playing ? '■ Stop' : '🔊 Listen to Earth'}
      </button>
      <span className="muted listen__caption">
        {playing && current
          ? `${current}: ${values[step!] ?? 'no reliable measurement'}`
          : `${label}: higher pitch = higher value, silence = no reliable measurement.`}
      </span>
    </div>
  )
}
