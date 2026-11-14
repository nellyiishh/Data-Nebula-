// Owner: Frontend 4 (story) + captain (methods/validity). Site-independent text for the
// "What we know and what we don't" screen. Site-specific text lives in site.json → slope_echo.

export const PROJECT = {
  name: 'Slope Echo',
  tagline: 'Rain loads it. Radar hears it. People live below it.',
  mission: 'Explore the invisible changes of our planet: NASA-ISRO NISAR radar turned into stories you can play, compare and check.',
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
  'Every date uses one fixed dB stretch. Stretching each image separately (min-max, std-dev or 2–98 % cut, as desktop GIS does by default) would make unchanged ground look changed.',
]

export const GLOBAL_LIMITS: string[] = [
  'NISAR does not predict landslides. It shows slow movement and change after the fact.',
  'This is a visual tool, not an official warning. For safety follow your local emergency service.',
]

// TODO(team): agree on the final wording before submitting (Space Apps asks for it).
export const AI_USE =
  'AI assistants helped us brainstorm the concept and write parts of the web code and the demo-data generator. ' +
  'Data choices, thresholds and every claim on this page were checked by the team.'

// ---- Radar Vision (screen 04) --------------------------------------------------------

export const CAMERA_VS_RADAR: { title: string; camera: string; radar: string }[] = [
  { title: 'Light source', camera: 'Sunlight reflected by the ground.', radar: 'Its own microwave pulse, sent and received by the satellite.' },
  { title: 'Clouds, smoke, night', camera: 'Blocked. Nothing usable under clouds or at night.', radar: 'Goes through clouds and smoke, works day and night.' },
  { title: 'What it records', camera: 'Colour: how green, brown or bright the surface looks.', radar: 'Echo strength (roughness, moisture, structure) and the phase of the wave (distance).' },
  { title: 'What change it can show', camera: 'A new brown scar, when the sky is clear.', radar: 'Rougher or smoother ground, lost vegetation, and centimetre-scale movement between passes.' },
]

export const RADAR_IS_NOT: string[] = [
  'Radar does not see underground. L-band passes through leaves and branches, not through soil or rock.',
  'A bright or dark patch is not automatically a landslide: wet soil, snow and crops also change the echo.',
  'Radar measures movement along its line of sight, not the full 3D motion of the slope.',
]

export interface Band {
  band: string
  wavelength: string
  satellites: string
  interacts: string
  /** Relative depth into a forest canopy, 0–1, for the bar. */
  depth: number
}

export const BANDS: Band[] = [
  { band: 'X', wavelength: '~3 cm', satellites: 'TerraSAR-X, COSMO-SkyMed', interacts: 'Leaves and the top of the canopy', depth: 0.15 },
  { band: 'C', wavelength: '~5.6 cm', satellites: 'Sentinel-1, RADARSAT', interacts: 'Leaves and small branches', depth: 0.35 },
  { band: 'S', wavelength: '~9 cm', satellites: 'NISAR S-SAR (mostly over India)', interacts: 'Branches', depth: 0.55 },
  { band: 'L', wavelength: '~24 cm', satellites: 'NISAR L-SAR (global), SAOCOM', interacts: 'Trunks and the ground below the canopy', depth: 0.9 },
]
