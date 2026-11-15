/** Small PDF file icon: white page, red "PDF" band. Decorative; the button text carries the meaning. */
export function PdfIcon() {
  return (
    <svg className="pdf-icon" viewBox="0 0 20 24" width="18" height="22" aria-hidden="true" focusable="false">
      <path d="M2 1h11l5 5v16a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1z" fill="#fff" stroke="var(--bg)" strokeWidth="1" />
      <path d="M13 1v5h5" fill="none" stroke="var(--bg)" strokeWidth="1" />
      <rect x="1" y="11" width="18" height="8" fill="var(--danger)" />
      <text x="10" y="17.4" textAnchor="middle" fontSize="6.5" fontWeight="700" fontFamily="Arial, sans-serif" fill="#fff">
        PDF
      </text>
    </svg>
  )
}
