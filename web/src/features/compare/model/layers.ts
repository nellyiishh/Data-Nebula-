// Display names and one-line explanations for radar layers. Unknown ids fall back to the raw id.

export const LAYER_LABELS: Record<string, string> = {
  hh: 'HH',
  hv: 'HV',
  rgb: 'Colour mix',
  water: 'Water mask',
}

export const LAYER_HINTS: Record<string, string> = {
  hh: 'Co-polarised: bright where the surface is rough or has hard edges (rocks, debris, buildings).',
  hv: 'Cross-polarised: bright where there is volume scattering (vegetation canopy).',
  rgb: 'Red = HH, green = HV, blue = HH/HV ratio.',
  water: 'Pixels dark enough in radar to be open water.',
}
