import { cpSync, createReadStream, existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { extname, join, normalize, resolve, sep } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// Website data made by the backend export (`python -m pipeline.export_static`) lives in
// data/web/ at the repo root, separate from the fake data in public/data/. Both are
// served at /data: a file in data/web/ wins, anything else falls back to public/data/.
// sites.json lists the backend sites first, then the fakes whose id is not taken.
// TODO(server-backend): goes away once the data comes from Cloud Storage / the API.
const SITE_DATA = resolve(import.meta.dirname, '../data/web')
const FAKE_DATA = resolve(import.meta.dirname, 'public/data')
const CONTENT_TYPES: Record<string, string> = {
  '.json': 'application/json',
  '.geojson': 'application/geo+json',
  '.png': 'image/png',
}

interface IndexEntry {
  id: string
}

function readIndex(dir: string): IndexEntry[] {
  const path = join(dir, 'sites.json')
  return existsSync(path) ? (JSON.parse(readFileSync(path, 'utf8')) as IndexEntry[]) : []
}

/** Combined sites.json, or null when the backend has exported nothing yet. */
function mergedIndex(): string | null {
  const backend = readIndex(SITE_DATA)
  if (backend.length === 0) return null
  const taken = new Set(backend.map((site) => site.id))
  const fakes = readIndex(FAKE_DATA).filter((site) => !taken.has(site.id))
  return `${JSON.stringify([...backend, ...fakes], null, 2)}\n`
}

/** A file under data/web/ for a path relative to /data/, or null (never outside it). */
function siteDataFile(relative: string): string | null {
  const file = normalize(join(SITE_DATA, relative))
  if (!file.startsWith(SITE_DATA + sep)) return null
  return existsSync(file) && statSync(file).isFile() ? file : null
}

function siteData(): Plugin {
  let outDir = 'dist'
  let isBuild = false
  return {
    name: 'site-data',
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir)
      isBuild = config.command === 'build'
    },
    configureServer(server) {
      const prefix = `${server.config.base}data/`
      // Registered directly (not returned), so it runs before Vite serves public/.
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? '').split('?')[0]
        if (!url.startsWith(prefix)) return next()
        const relative = decodeURIComponent(url.slice(prefix.length))
        if (relative === 'sites.json') {
          const index = mergedIndex()
          if (index === null) return next()
          res.setHeader('Content-Type', 'application/json')
          return res.end(index)
        }
        const file = siteDataFile(relative)
        if (file === null) return next()
        res.setHeader('Content-Type', CONTENT_TYPES[extname(file)] ?? 'application/octet-stream')
        createReadStream(file).pipe(res)
      })
    },
    closeBundle() {
      if (!isBuild || !existsSync(SITE_DATA)) return
      // public/data/ is already in the build; backend files are copied over it.
      cpSync(SITE_DATA, join(outDir, 'data'), { recursive: true })
      const index = mergedIndex()
      if (index !== null) writeFileSync(join(outDir, 'data', 'sites.json'), index)
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), siteData()],
})
