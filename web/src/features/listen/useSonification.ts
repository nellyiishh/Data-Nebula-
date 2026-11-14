import { useEffect, useRef, useState } from 'react'

// "Listen to Earth": plays a measured series as tones. Higher value → higher pitch, on a fixed
// two-octave scale so the sound follows the data, not a mood. Missing values are silence.

const LOW_HZ = 220
const HIGH_HZ = 880
const NOTE_S = 0.38
const GAP_S = 0.07

export function useSonification(values: (number | null)[]) {
  const [step, setStep] = useState<number | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const timers = useRef<number[]>([])

  const stop = () => {
    timers.current.forEach(clearTimeout)
    timers.current = []
    void ctxRef.current?.close()
    ctxRef.current = null
    setStep(null)
  }

  useEffect(() => stop, [])

  const play = () => {
    stop()
    const nums = values.filter((v): v is number => v !== null)
    if (nums.length === 0) return
    const min = Math.min(...nums)
    const max = Math.max(...nums)
    const ctx = new AudioContext()
    ctxRef.current = ctx
    values.forEach((v, i) => {
      const t0 = ctx.currentTime + 0.05 + i * (NOTE_S + GAP_S)
      timers.current.push(window.setTimeout(() => setStep(i), (t0 - ctx.currentTime) * 1000))
      if (v === null) return
      const frac = max === min ? 0.5 : (v - min) / (max - min)
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = LOW_HZ * (HIGH_HZ / LOW_HZ) ** frac // equal steps in pitch, not in Hz
      gain.gain.setValueAtTime(0, t0)
      gain.gain.linearRampToValueAtTime(0.18, t0 + 0.03)
      gain.gain.exponentialRampToValueAtTime(0.001, t0 + NOTE_S)
      osc.connect(gain).connect(ctx.destination)
      osc.start(t0)
      osc.stop(t0 + NOTE_S)
    })
    const total = values.length * (NOTE_S + GAP_S) + 0.1
    timers.current.push(window.setTimeout(stop, total * 1000))
  }

  return { play, stop, playing: step !== null, step }
}
