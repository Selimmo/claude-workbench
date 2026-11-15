import { lineSpot, midpoint, outlineSpot, pinSpot, spotOf } from './position'

const box = (left: number, top: number, right: number, bottom: number) =>
  ({ left, top, right, bottom }) as DOMRect

test("a spot is the element's top-right corner", () => {
  expect(spotOf(box(10, 20, 110, 60), null)).toEqual({ top: 20, left: 110 })
})

test('an element panned out of its diagram has no spot, so its pin does not float elsewhere', () => {
  const viewport = box(0, 100, 800, 600)

  expect(spotOf(box(10, 200, 110, 260), viewport)).toEqual({ top: 200, left: 110 })
  expect(spotOf(box(900, 200, 1000, 260), viewport)).toBeNull()
  expect(spotOf(box(10, 40, 110, 80), viewport)).toBeNull()
})

test('a spot can be moved onto the shape, and is still hidden when that point is outside the viewport', () => {
  const viewport = box(0, 100, 800, 600)

  expect(spotOf(box(10, 200, 110, 260), viewport, { top: 210, left: 90 })).toEqual({
    top: 210,
    left: 90,
  })
  expect(spotOf(box(10, 200, 110, 260), viewport, { top: 90, left: 90 })).toBeNull()
})

test('a decision diamond is pinned in the middle of its upper-right edge', () => {
  // The edge runs from the top point (60, 20) to the right point (110, 40).
  expect(outlineSpot('decision', box(10, 20, 110, 60))).toEqual({ top: 30, left: 85 })
})

test('a start or end pill is pinned on its round end, up and to the right', () => {
  // Height 40: the right end is a half circle of radius 20 around (90, 40).
  for (const shape of ['start', 'end']) {
    const spot = outlineSpot(shape, box(10, 20, 110, 60))
    expect(spot.left).toBeCloseTo(90 + 20 * Math.SQRT1_2)
    expect(spot.top).toBeCloseTo(40 - 20 * Math.SQRT1_2)
  }
})

test('an action, or any other shape, keeps the top-right corner', () => {
  expect(outlineSpot('action', box(10, 20, 110, 60))).toEqual({ top: 20, left: 110 })
  expect(outlineSpot(undefined, box(10, 20, 110, 60))).toEqual({ top: 20, left: 110 })
})

test('the midpoint of a line is halfway along its length, not halfway between its ends', () => {
  expect(
    midpoint([
      { x: 0, y: 0 },
      { x: 10, y: 0 },
    ]),
  ).toEqual({ x: 5, y: 0 })
  // Lengths 10 and 30: halfway is 20 along, 10 into the second part.
  expect(
    midpoint([
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 30 },
    ]),
  ).toEqual({ x: 10, y: 10 })
  expect(midpoint([{ x: 4, y: 4 }])).toEqual({ x: 4, y: 4 })
})

test('a line is pinned on its midpoint, placed on screen through its transform', () => {
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'path')
  line.setAttribute('d', 'M0,0 L10,0 L10,30')
  // Scaled by 2 and moved by (100, 200).
  Object.assign(line, { getScreenCTM: () => ({ a: 2, b: 0, c: 0, d: 2, e: 100, f: 200 }) })

  expect(lineSpot(line)).toEqual({ top: 220, left: 120 })
})

test('a line without a screen transform has no spot of its own', () => {
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'path')
  line.setAttribute('d', 'M0,0 L10,0')

  expect(lineSpot(line)).toBeNull()
})

test('the pin of a flowchart element follows its shape, and a flowchart line follows its path', () => {
  const svg = 'http://www.w3.org/2000/svg'
  const diamond = document.createElementNS(svg, 'g')
  diamond.setAttribute('data-shape', 'decision')
  expect(pinSpot(diamond, box(10, 20, 110, 60))).toEqual({ top: 30, left: 85 })

  const edge = document.createElementNS(svg, 'g')
  edge.setAttribute('data-flow', 'true')
  const line = document.createElementNS(svg, 'path')
  line.setAttribute('class', 'line')
  line.setAttribute('d', 'M0,0 L10,0')
  Object.assign(line, { getScreenCTM: () => ({ a: 1, b: 0, c: 0, d: 1, e: 50, f: 60 }) })
  edge.append(line)
  expect(pinSpot(edge, box(0, 0, 500, 500))).toEqual({ top: 60, left: 55 })

  // A line of another kind of diagram keeps the corner of its box.
  edge.removeAttribute('data-flow')
  expect(pinSpot(edge, box(0, 0, 500, 500))).toEqual({ top: 0, left: 500 })
})
