// Owner: story. Plain-language text for the "For everyone" section. Facts about a site come
// from its data (site.json → slope_echo); this file holds only what is true for every site.

export const EVERYONE = {
  kicker: 'For everyone · satellites watching mountain slopes',
  title: 'See how the mountains move.',
  lede: 'A NASA-ISRO satellite called NISAR sends radio waves to the ground and listens to the echo, through clouds, day and night. Here is what it saw on a slope in Kyrgyzstan.',
  start: 'Show me',
}

export interface ViewMode {
  id: 'before-after' | 'timelapse' | 'changed' | 'photo'
  label: string
  explain: string
}

export const VIEW_MODES: ViewMode[] = [
  {
    id: 'before-after',
    label: 'Before / after',
    explain:
      'Drag the line. Left is the first satellite pass, right is the last one. Bright means rough ground (rocks, fresh soil, houses); dark means smooth ground or water.',
  },
  {
    id: 'timelapse',
    label: 'Time-lapse',
    explain: 'Press play to see every pass of the satellite, about every 12 days.',
  },
  {
    id: 'changed',
    label: 'What changed',
    explain:
      'Coloured spots are places where the radar echo changed a lot between two passes: blue got brighter, red got darker. Change is a reason to look closer, not proof of a landslide.',
  },
  {
    id: 'photo',
    label: 'Photo vs radar',
    explain:
      'Left is an ordinary satellite photo, right is the radar picture of the same day. Clouds block the camera; the radar sees through them.',
  },
]

export const HOW_RADAR_SEES: { title: string; text: string }[] = [
  { title: 'It sends a pulse', text: 'The satellite fires a radio pulse about 24 cm long at the ground. It brings its own light, so night and clouds do not matter.' },
  { title: 'The ground echoes', text: 'Rough ground (rocks, broken soil) sends more echo back; smooth ground and water send less.' },
  { title: 'Passes are compared', text: 'The satellite comes back every 12 days. Comparing the echoes shows where the surface changed or moved.' },
]

// General landslide warning signs (as listed by the USGS and national emergency services).
export const WARNING_SIGNS: string[] = [
  'New cracks in the ground, roads or walls, or cracks that grow',
  'Trees, poles or fences that start to tilt',
  'Doors and windows that suddenly stick',
  'Water seeping out of a slope, or a stream that turns muddy or suddenly drops',
  'Rumbling sounds or small falls of soil and stones',
]

export const SAFETY_NOTE =
  'If you notice these signs, move away from the slope and tell your local emergency service. This website is not a warning system and cannot tell whether a place is safe.'
