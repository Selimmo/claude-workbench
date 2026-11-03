import { canvasMeasure, estimate } from './measure'

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
