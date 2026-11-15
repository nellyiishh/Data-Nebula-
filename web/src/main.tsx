import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './core/theme/tokens.css'
import { App } from './app/App'
import { notify } from './core/ui/notify'
import { SnackbarHost } from './core/ui/SnackbarHost'

// Last resort: a promise nobody handled (aborted fetches are not errors).
window.addEventListener('unhandledrejection', (e) => {
  if (e.reason instanceof DOMException && e.reason.name === 'AbortError') return
  notify('Something went wrong. Please try again.')
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <SnackbarHost />
  </StrictMode>,
)
