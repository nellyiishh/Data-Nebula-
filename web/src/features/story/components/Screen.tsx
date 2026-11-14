import type { ReactNode } from 'react'
import type { DualText } from '../../sites/model/types'
import './story.css'

// Owner: Frontend 4 (story). One numbered screen of the scrolling story.

interface Props {
  id: string
  n: number
  title: string
  text?: DualText
  research: boolean
  children?: ReactNode
  wide?: boolean
}

export function Screen({ id, n, title, text, research, children, wide }: Props) {
  return (
    <section id={id} className={`screen${wide ? ' screen--wide' : ''}`} aria-labelledby={`${id}-title`}>
      <header className="screen__head">
        <span className="screen__n">{String(n).padStart(2, '0')}</span>
        <h2 id={`${id}-title`}>{title}</h2>
      </header>
      {text && <p className="screen__text">{research ? text.research : text.explore}</p>}
      {children}
    </section>
  )
}

export function SourceLink({ source }: { source?: { name: string; url?: string } }) {
  if (!source) return null
  return source.url ? (
    <a className="source-link" href={source.url} target="_blank" rel="noreferrer">
      {source.name}
    </a>
  ) : (
    <span className="source-link source-link--todo">{source.name}</span>
  )
}
