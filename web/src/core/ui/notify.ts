import { useSyncExternalStore } from 'react'

// Snackbar store: any code (hooks, map handlers) calls notify(); <SnackbarHost/> shows it.
// Owner: core/ui. Each message lives AUTO_HIDE_MS, or until dismissed.
// Same text within DEDUPE_MS is dropped, so a map retrying 50 tiles shows one snackbar, not 50.

export interface Snack {
  id: number
  message: string
  kind: 'error' | 'info'
}

const AUTO_HIDE_MS = 6000
const DEDUPE_MS = 8000
const MAX_VISIBLE = 3

let snacks: Snack[] = []
let nextId = 1
const lastShown = new Map<string, number>()
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((l) => l())
}

export function dismiss(id: number) {
  snacks = snacks.filter((s) => s.id !== id)
  emit()
}

export function notify(message: string, kind: Snack['kind'] = 'error') {
  const now = Date.now()
  if (now - (lastShown.get(message) ?? 0) < DEDUPE_MS) return
  lastShown.set(message, now)
  const id = nextId++
  snacks = [...snacks, { id, message, kind }].slice(-MAX_VISIBLE)
  emit()
  setTimeout(() => dismiss(id), AUTO_HIDE_MS)
}

export function useSnacks(): Snack[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => snacks,
  )
}
