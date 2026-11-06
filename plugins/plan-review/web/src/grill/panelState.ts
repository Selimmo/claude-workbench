// Whether the decisions list is open: remembered in browser storage, like the theme.

export const PANEL_KEY = 'plan-review-decisions-panel'

// Storage can be unavailable (private windows, blocked site data): fall back to open.
export function storedOpen(): boolean {
  try {
    return localStorage.getItem(PANEL_KEY) !== 'closed'
  } catch {
    return true
  }
}

export function storeOpen(open: boolean) {
  try {
    if (open) localStorage.removeItem(PANEL_KEY)
    else localStorage.setItem(PANEL_KEY, 'closed')
  } catch {
    // Not remembered, but still applied for this visit.
  }
}
