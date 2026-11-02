import { useState } from 'react'

export const STORAGE_KEY = 'plan-review-theme'

type Theme = 'auto' | 'light' | 'dark'

const OPTIONS: { value: Theme; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

// Storage can be unavailable (private windows, blocked site data): fall back to Auto.
function stored(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'auto'
  } catch {
    return 'auto'
  }
}

function apply(theme: Theme) {
  // Auto sets no attribute, so the CSS follows prefers-color-scheme.
  if (theme === 'auto') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
}

/** Run before the first render so the page never flashes the wrong theme. */
export function applyStoredTheme() {
  apply(stored())
}

export function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(stored)

  function choose(next: Theme) {
    setTheme(next)
    apply(next)
    try {
      if (next === 'auto') localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Not remembered, but still applied for this visit.
    }
  }

  return (
    <fieldset className="theme-switch">
      <legend>Theme</legend>
      {OPTIONS.map((option) => (
        <label key={option.value}>
          <input
            type="radio"
            name="theme"
            value={option.value}
            checked={theme === option.value}
            onChange={() => choose(option.value)}
          />
          {option.label}
        </label>
      ))}
    </fieldset>
  )
}
