// How wide a piece of text is drawn, so diagram boxes fit their text exactly.
// In the browser a canvas measures it in the real font; tests (jsdom has no canvas) use
// estimates, which keeps layout deterministic there.

export type TextKind = 'title' | 'subtitle' | 'row' | 'participant' | 'label'
export type Measure = (text: string, kind: TextKind) => number

export const CHAR_WIDTH = 7.8 // px per character at the diagram's 13px monospace font
export const TITLE_CHAR_WIDTH = 9.2 // bold proportional titles run wider per character

const ESTIMATE: Record<TextKind, number> = {
  title: TITLE_CHAR_WIDTH,
  subtitle: CHAR_WIDTH,
  row: CHAR_WIDTH,
  participant: 8.5, // semibold 13px
  label: 7.2, // 12px monospace
}

export const estimate: Measure = (text, kind) => text.length * ESTIMATE[kind]

const MONO = "ui-monospace, 'SF Mono', Menlo, monospace"

/** The fonts styles.css draws each kind of text in. */
function fonts(): Record<TextKind, string> {
  const family = getComputedStyle(document.documentElement).fontFamily || 'system-ui, sans-serif'
  return {
    title: `bold 16px ${family}`,
    subtitle: `12px ${family}`,
    row: `13px ${MONO}`,
    participant: `600 13px ${family}`,
    label: `12px ${MONO}`,
  }
}

export function canvasMeasure(): Measure {
  const context = document.createElement('canvas').getContext('2d')
  if (!context) return estimate
  const font = fonts()
  const cache = new Map<string, number>()
  return (text, kind) => {
    const key = `${kind}\u0000${text}`
    let width = cache.get(key)
    if (width === undefined) {
      context.font = font[kind]
      width = Math.ceil(context.measureText(text).width) // round up: never a pixel short
      cache.set(key, width)
    }
    return width
  }
}
