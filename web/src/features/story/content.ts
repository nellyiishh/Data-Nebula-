// Owner: Frontend 4 (story) + captain (methods/validity). Site-independent text for the
// "What we know and what we don't" screen. Site-specific text lives in site.json → slope_echo.

export const PROJECT = {
  name: 'Slope Echo',
  tagline: 'Rain loads it. Radar hears it. People live below it.',
  // TODO(team): confirm the repo URL that judges should see.
  repo: 'https://github.com/nellyiishh/Data-Nebula-',
}

export interface Dataset {
  name: string
  provider: string
  url: string
  usedFor: string
}

export const DATASETS: Dataset[] = [
  {
    name: 'NISAR L2 GCOV (L-band, HH/HV backscatter)',
    provider: 'NASA-ISRO · ASF DAAC',
    url: 'https://nisar-docs.asf.alaska.edu/gcov',
    usedFor: 'Surface brightness per pass, change maps',
  },
  {
    name: 'NISAR L2 GUNW (unwrapped interferograms)',
    provider: 'NASA-ISRO · ASF DAAC',
    url: 'https://search.asf.alaska.edu/',
    usedFor: 'Coherence and line-of-sight displacement',
  },
  {
    name: 'GPM IMERG Late Run, daily',
    provider: 'NASA GES DISC',
    url: 'https://gpm.nasa.gov/data/imerg',
    usedFor: 'Rain before and after the event',
  },
  {
    name: 'Sentinel-2 / Harmonized Landsat Sentinel-2 (HLS)',
    provider: 'ESA · NASA LP DAAC',
    url: 'https://hls.gsfc.nasa.gov/',
    usedFor: 'Optical check of the scar, cloud comparison',
  },
  {
    name: 'OpenStreetMap buildings and roads',
    provider: 'OpenStreetMap contributors',
    url: 'https://www.openstreetmap.org/copyright',
    usedFor: 'What is near the slope',
  },
  {
    name: 'Basemap',
    provider: '© OpenStreetMap contributors © CARTO',
    url: 'https://carto.com/attributions',
    usedFor: 'Background map',
  },
]

export const METHODS: string[] = [
  'All radar dates come from one track and frame, so the viewing geometry is the same.',
  'Backscatter change = smoothed dB(after) − dB(before); only |Δ| above the threshold is coloured. The threshold is tuned on a stable reference area.',
  'Displacement = −λ / (4π) × unwrapped phase, λ ≈ 0.238 m (L-band), relative to the stable area, masked where coherence < 0.3.',
  'The scar outline is drawn on post-event optical imagery and used only to check the radar result, never to make it.',
]

export const GLOBAL_LIMITS: string[] = [
  'NISAR does not predict landslides. It shows slow movement and change after the fact.',
  'This is a visual tool, not an official warning. For safety follow your local emergency service.',
]

// TODO(team): agree on the final wording before submitting (Space Apps asks for it).
export const AI_USE =
  'AI assistants helped us brainstorm the concept and write parts of the web code and the demo-data generator. ' +
  'Data choices, thresholds and every claim on this page were checked by the team.'
