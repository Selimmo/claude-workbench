import { centerOn, fill, fitAll, showsAll, visibleArea, zoomAt } from './fit'

const viewport = { width: 1000, height: 500 }

test('fit all shrinks large content to fit, keeping its aspect ratio, and centres it', () => {
  expect(fitAll(viewport, { width: 4000, height: 1000 })).toEqual({ x: 0, y: 125, scale: 0.25 })
})

test('fit all enlarges small content to fill the space, up to 1.5x', () => {
  expect(fitAll(viewport, { width: 400, height: 100 })).toEqual({ x: 200, y: 175, scale: 1.5 })
})

test('an unmeasured viewport (zero size) keeps full size', () => {
  expect(fitAll({ width: 0, height: 0 }, { width: 300, height: 100 })).toEqual({
    x: 0,
    y: 0,
    scale: 1,
  })
})

test('fill makes a wide diagram as tall as the viewport, starting at its left end', () => {
  expect(fill(viewport, { width: 4000, height: 1000 })).toEqual({ x: 0, y: 0, scale: 0.5 })
})

test('fill makes a tall diagram as wide as the viewport, starting at its top', () => {
  expect(fill(viewport, { width: 500, height: 2000 })).toEqual({ x: 125, y: 0, scale: 1.5 })
})

test('fill enlarges at most 1.5x, centring an axis that then fits', () => {
  expect(fill(viewport, { width: 300, height: 100 })).toEqual({ x: 275, y: 175, scale: 1.5 })
})

test('zooming at a point keeps that point still on screen', () => {
  const view = zoomAt({ x: 0, y: 0, scale: 0.5 }, { x: 100, y: 50 }, 1)
  // Content point (200, 100) was under the pointer at scale 0.5 and still is.
  expect(view).toEqual({ x: -100, y: -50, scale: 1 })
})

test('centring on a content point puts it in the middle of the viewport', () => {
  expect(centerOn({ x: 0, y: 0, scale: 2 }, viewport, { x: 100, y: 100 })).toEqual({
    x: 300,
    y: 50,
    scale: 2,
  })
})

test('the visible area is the viewport in content coordinates', () => {
  expect(visibleArea({ x: -100, y: -50, scale: 2 }, viewport)).toEqual({
    x: 50,
    y: 25,
    width: 500,
    height: 250,
  })
})

test('a view shows all the content only when every edge is inside the viewport', () => {
  const content = { width: 4000, height: 1000 }
  expect(showsAll(fitAll(viewport, content), viewport, content)).toBe(true)
  expect(showsAll({ x: 0, y: 0, scale: 1 }, viewport, content)).toBe(false)
})
