// Map colour for each overlay id; unknown ids fall back to the text colour.
const OVERLAY_COLOR: Record<string, string> = {
  radar_blind: '#78788299',
  scar: 'var(--scar)',
  stable: 'var(--stable)',
  exposure: 'var(--building)',
  aoi: 'var(--text-muted)',
}

export const overlayColor = (id: string) => OVERLAY_COLOR[id] ?? 'var(--text)'
