import type { ReactNode } from 'react'
import { HOW_RADAR_SEES, SAFETY_NOTE, WARNING_SIGNS } from '../content'
import './everyone.css'

// Owner: story. Simple presentational blocks for the "For everyone" section.

export function EveryoneSection({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="ev-section" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{title}</h2>
      {children}
    </section>
  )
}

export function FactCard({ big, label, note }: { big: string; label: string; note?: ReactNode }) {
  return (
    <div className="ev-fact">
      <strong>{big}</strong>
      <span>{label}</span>
      {note && <small>{note}</small>}
    </div>
  )
}

export function HowRadarSees() {
  return (
    <ol className="ev-steps">
      {HOW_RADAR_SEES.map((s, i) => (
        <li key={s.title}>
          <span className="ev-steps__n" aria-hidden="true">
            {i + 1}
          </span>
          <strong>{s.title}</strong>
          <p>{s.text}</p>
        </li>
      ))}
    </ol>
  )
}

export function WarningSigns() {
  return (
    <div className="ev-safety">
      <ul>
        {WARNING_SIGNS.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      <p>{SAFETY_NOTE}</p>
    </div>
  )
}
