import { paths } from '../../../core/api/client'
import type { ContractLayer, ExtLayer, SiteDetail, SourceRef } from './types'

// One shape for every raster the explorer can show, whether it comes from the backend
// contract (hh, hv, rgb, water, change) or from the slope_echo extension.

export interface Frame {
  /** Stable key for URL state: a date or "from_to". */
  key: string
  label: string
  /** Date the frame belongs to on the timeline (the later date of a pair). */
  date: string
  from?: string
  url: string
}

export interface LayerView {
  id: string
  title: string
  kind: 'backscatter' | 'change' | 'coherence' | 'displacement' | 'optical' | (string & {})
  description: string
  unit: string
  source: SourceRef
  legend: { colors: string[]; labels: string[] } | null
  frames: Frame[]
}

const NISAR: SourceRef = { name: 'NISAR L2 GCOV, ASF DAAC', url: 'https://search.asf.alaska.edu/' }

const CONTRACT: Record<ContractLayer, Omit<LayerView, 'frames' | 'source'>> = {
  hh: {
    id: 'hh',
    title: 'HH',
    kind: 'backscatter',
    unit: 'dB',
    description: 'Bright where the ground is rough: rocks, fresh debris, buildings.',
    // TODO(legend-api): confirm the fixed stretch with backend/pipeline/writer.py.
    legend: { colors: ['#000000', '#ffffff'], labels: ['smooth / dark', 'rough / bright'] },
  },
  hv: {
    id: 'hv',
    title: 'HV',
    kind: 'backscatter',
    unit: 'dB',
    description: 'Bright where there is vegetation volume (bushes, trees, crops).',
    legend: { colors: ['#000000', '#ffffff'], labels: ['bare', 'vegetated'] },
  },
  rgb: {
    id: 'rgb',
    title: 'Colour mix',
    kind: 'backscatter',
    unit: '',
    description: 'Red = HH, green = HV, blue = HH/HV ratio. Combines roughness and vegetation in one picture.',
    legend: null,
  },
  water: {
    id: 'water',
    title: 'Water mask',
    kind: 'backscatter',
    unit: '',
    description: 'Pixels dark enough in radar to be open water.',
    legend: { colors: ['#2878ff'], labels: ['open water'] },
  },
}

const pairsOf = (dates: string[]) => dates.slice(1).map((to, i) => [dates[i], to] as const)

export function buildLayers(site: SiteDetail): LayerView[] {
  const { id, dates } = site
  const contract = site.layers.map<LayerView>((l) => ({
    ...CONTRACT[l],
    source: NISAR,
    frames: dates.map((d) => ({ key: d, label: d, date: d, url: paths.layer(id, l, d) })),
  }))

  const change: LayerView = {
    id: 'change',
    title: 'Change (HH)',
    kind: 'change',
    unit: 'dB',
    source: NISAR,
    description: 'Difference between two passes. Only changes larger than ±3 dB are coloured.',
    legend: { colors: ['#e63232', '#3270f0'], labels: ['got darker', 'got brighter'] },
    frames: pairsOf(dates).map(([from, to]) => ({
      key: `${from}_${to}`,
      label: `${from} → ${to}`,
      date: to,
      from,
      url: paths.change(id, from, to),
    })),
  }

  const ext = (site.slope_echo?.layers ?? []).map<LayerView>((l: ExtLayer) => ({
    id: l.id,
    title: l.title,
    kind: l.kind,
    unit: l.unit,
    description: l.description,
    source: l.source,
    legend: l.legend,
    frames: l.frames.map((f) => {
      const date = f.date ?? f.to ?? ''
      return f.from
        ? { key: `${f.from}_${f.to}`, label: `${f.from} → ${f.to}`, date, from: f.from, url: paths.siteFile(id, f.file) }
        : { key: date, label: date, date, url: paths.siteFile(id, f.file) }
    }),
  }))

  return [...contract, change, ...ext]
}

/** Frame of `layer` closest to (at or before) `date`, so switching layers keeps the time. */
export function frameIndexFor(layer: LayerView, date: string | undefined): number {
  if (!date) return 0
  let best = 0
  layer.frames.forEach((f, i) => {
    if (f.date <= date) best = i
  })
  return best
}
