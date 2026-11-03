import '@testing-library/jest-dom/vitest'

// Node 25 defines a global localStorage that is unusable without --localstorage-file and
// shadows jsdom's. Give tests a working in-memory one when that happens.
if (typeof globalThis.localStorage?.clear !== 'function') {
  const items = new Map<string, string>()
  const memory: Storage = {
    get length() {
      return items.size
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => void items.delete(key),
    setItem: (key, value) => void items.set(key, String(value)),
  }
  Object.defineProperty(globalThis, 'localStorage', { value: memory, configurable: true })
}

// jsdom has no canvas: say so quietly (getContext would log "Not implemented"), as a
// browser without canvas support would, so text measuring falls back to estimates.
HTMLCanvasElement.prototype.getContext = (() =>
  null) as typeof HTMLCanvasElement.prototype.getContext
