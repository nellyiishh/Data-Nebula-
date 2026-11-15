import { dismiss, useSnacks } from './notify'
import './SnackbarHost.css'

/** Mount once at the root. Errors use role="alert" (announced at once), info uses "status". */
export function SnackbarHost() {
  const snacks = useSnacks()
  if (snacks.length === 0) return null
  return (
    <div className="snackbars">
      {snacks.map((s) => (
        <div key={s.id} className={`snackbar snackbar--${s.kind}`} role={s.kind === 'error' ? 'alert' : 'status'}>
          <span>{s.message}</span>
          <button type="button" className="snackbar__close" aria-label="Dismiss message" onClick={() => dismiss(s.id)}>
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
