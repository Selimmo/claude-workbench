import { fitView } from './fit'

test('content larger than the viewport is shrunk to fit, keeping its aspect ratio', () => {
  expect(fitView({ width: 500, height: 400 }, { width: 1000, height: 200 })).toEqual({
    x: 0,
    y: 0,
    scale: 0.5,
  })
})

test('content that already fits is shown at full size, never enlarged', () => {
  expect(fitView({ width: 800, height: 600 }, { width: 300, height: 100 }).scale).toBe(1)
})

test('an unmeasured viewport (zero size) keeps full size', () => {
  expect(fitView({ width: 0, height: 0 }, { width: 300, height: 100 }).scale).toBe(1)
})
