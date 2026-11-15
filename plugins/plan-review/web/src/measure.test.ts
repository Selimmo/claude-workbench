import { canvasMeasure, estimate, wrapLabel } from './measure'

afterEach(() => vi.restoreAllMocks())

test('measures with a canvas, in the font each kind of text is drawn in', () => {
  const fonts: string[] = []
  const context = {
    font: '',
    measureText(text: string) {
      fonts.push(this.font)
      return { width: text.length * 10 }
    },
  }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  )
  const measure = canvasMeasure()

  expect(measure('abc', 'row')).toBe(30)
  measure('T', 'title')
  expect(fonts[0]).toMatch(/13px .*monospace/)
  expect(fonts[1]).toMatch(/^bold 16px /)
})

test('without a canvas (as in jsdom) it falls back to the estimate', () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)

  expect(canvasMeasure()('abc', 'row')).toBe(estimate('abc', 'row'))
})

test('measured widths are rounded up, never a pixel short', () => {
  const context = { font: '', measureText: () => ({ width: 30.2 }) }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  )

  expect(canvasMeasure()('abc', 'row')).toBe(31)
})

test('the flow and tag text have estimates that grow with their length', () => {
  for (const kind of ['flow', 'tag'] as const) {
    expect(estimate('abc', kind)).toBeGreaterThan(0)
    expect(estimate('abcdef', kind)).toBeGreaterThan(estimate('abc', kind))
  }
})

test('flow text is measured in 500 13px sans-serif and tags in 600 11px sans-serif', () => {
  const fonts: string[] = []
  const context = {
    font: '',
    measureText() {
      fonts.push(this.font)
      return { width: 1 }
    },
  }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  )
  const measure = canvasMeasure()

  measure('a', 'flow')
  measure('a', 'tag')

  expect(fonts[0]).toMatch(/^500 13px /)
  expect(fonts[1]).toMatch(/^600 11px /)
})

function recordFonts() {
  const used = new Map<string, string>()
  let kind = ''
  const context = {
    font: '',
    measureText(this: { font: string }) {
      used.set(kind, this.font)
      return { width: 1 }
    },
  }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  )
  const measure = canvasMeasure()
  const kinds = ['title', 'subtitle', 'row', 'participant', 'label', 'flow', 'tag'] as const
  for (const k of kinds) {
    kind = k
    measure('x', k)
  }
  return Object.fromEntries(used)
}

const MONO = "ui-monospace, 'SF Mono', Menlo, monospace"

test('every kind of text is measured in the font it is drawn in, in the page font', () => {
  vi.spyOn(window, 'getComputedStyle').mockReturnValue({
    fontFamily: 'Fira, serif',
  } as CSSStyleDeclaration)

  expect(recordFonts()).toEqual({
    title: 'bold 16px Fira, serif',
    subtitle: '12px Fira, serif',
    row: `13px ${MONO}`,
    participant: '600 13px Fira, serif',
    label: `12px ${MONO}`,
    flow: '500 13px Fira, serif',
    tag: '600 11px Fira, serif',
  })
})

test('without a page font the system sans-serif is used', () => {
  vi.spyOn(window, 'getComputedStyle').mockReturnValue({ fontFamily: '' } as CSSStyleDeclaration)

  expect(recordFonts().flow).toBe('500 13px system-ui, sans-serif')
})

test('a measured text is measured once, then remembered', () => {
  const measureText = vi.fn(() => ({ width: 5 }))
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    font: '',
    measureText,
  } as unknown as CanvasRenderingContext2D)
  const measure = canvasMeasure()

  expect([measure('abc', 'row'), measure('abc', 'row'), measure('abc', 'tag')]).toEqual([5, 5, 5])
  expect(measureText).toHaveBeenCalledTimes(2)
})

test('wrapLabel lets a line be exactly as wide as the maximum', () => {
  const width = (text: string) => text.length * 10

  expect(wrapLabel('aa bb', 50, width)).toEqual(['aa bb'])
  expect(wrapLabel('aa bb', 49, width)).toEqual(['aa', 'bb'])
})
