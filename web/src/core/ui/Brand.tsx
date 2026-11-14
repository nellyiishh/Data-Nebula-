import './Brand.css'

// TRACE logo mark + name. The mark is cut from the team's logo (public/brand/trace-mark.png).

interface Props {
  name: string
  subtitle?: string
  href?: string
}

export function Brand({ name, subtitle, href = '#top' }: Props) {
  return (
    <a className="brand" href={href} aria-label={`${name}${subtitle ? ` — ${subtitle}` : ''}, home`}>
      <img className="brand__mark" src={`${import.meta.env.BASE_URL}brand/trace-mark.png`} alt="" width="36" height="33" />
      <span className="brand__text">
        <strong className="brand__name">{name}</strong>
        {subtitle && <span className="brand__sub">{subtitle}</span>}
      </span>
    </a>
  )
}
