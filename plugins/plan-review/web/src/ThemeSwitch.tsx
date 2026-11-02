import { useState } from 'react'

import { OPTIONS, STORAGE_KEY, type Theme, apply, stored } from './theme'

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
