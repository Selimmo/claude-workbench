// The colour theme: Auto follows the OS; Light or Dark is remembered in browser storage.

export const STORAGE_KEY = 'plan-review-theme'

export type Theme = 'auto' | 'light' | 'dark'

export const OPTIONS: { value: Theme; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

// Storage can be unavailable (private windows, blocked site data): fall back to Auto.
export function stored(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'auto'
  } catch {
    return 'auto'
  }
}

export function apply(theme: Theme) {
  // Auto sets no attribute, so the CSS follows prefers-color-scheme.
  if (theme === 'auto') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
}

/** Run before the first render so the page never flashes the wrong theme. */
export function applyStoredTheme() {
  apply(stored())
}
