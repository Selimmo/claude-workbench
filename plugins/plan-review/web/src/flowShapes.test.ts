import type { DiagramNode } from './diagram'
import {
  FLOW_LINE_HEIGHT,
  PAD_X,
  PAD_Y,
  PILL_MIN_HEIGHT,
  WRAP_WIDTH,
  clipToOutline,
  flowNodeSize,
  overlaps,
  tagSize,
  tagsCollide,
} from './flowShapes'
import type { LaidNode } from './layout'
import { estimate } from './measure'

const step = (shape: DiagramNode['shape'], title: string): DiagramNode => ({
  id: 'n',
  title,
  subtitle: null,
  status: 'added',
  rows: [],
  shape,
})

const SHORT = 'Give next level'
const LONG = 'Say that no hints are left for this exercise and stop asking the learner'

test('a step shorter than the wrap width stays on one line, a longer one wraps', () => {
  const short = flowNodeSize(step('action', SHORT), estimate)
  const long = flowNodeSize(step('action', LONG), estimate)

  expect(short.lines).toEqual([SHORT])
  expect(long.lines.length).toBeGreaterThan(1)
  expect(long.lines.join(' ')).toBe(LONG)
  for (const line of long.lines) expect(estimate(line, 'flow')).toBeLessThanOrEqual(WRAP_WIDTH)
})

test('an action is its text plus padding', () => {
  const { width, height, lines } = flowNodeSize(step('action', SHORT), estimate)

  expect(width).toBe(estimate(SHORT, 'flow') + 2 * PAD_X)
  expect(height).toBe(lines.length * FLOW_LINE_HEIGHT + 2 * PAD_Y)
})

test('a pill is at least 40px high, with a half circle at each end beside its text', () => {
  const one = flowNodeSize(step('start', SHORT), estimate)
  const many = flowNodeSize(step('end', LONG), estimate)

  expect(PILL_MIN_HEIGHT).toBe(40)
  expect(one.height).toBe(PILL_MIN_HEIGHT)
  expect(many.height).toBe(many.lines.length * FLOW_LINE_HEIGHT + 2 * PAD_Y)
  expect(many.height).toBeGreaterThan(PILL_MIN_HEIGHT)
  expect(one.width).toBe(estimate(SHORT, 'flow') + one.height)
})

test('a step with no shape is sized as an action', () => {
  expect(flowNodeSize(step(undefined, SHORT), estimate)).toEqual(
    flowNodeSize(step('action', SHORT), estimate),
  )
})

/** The text block's corners, relative to the shape's centre. */
function corners(size: ReturnType<typeof flowNodeSize>, padded: boolean) {
  const w = Math.max(...size.lines.map((l) => estimate(l, 'flow'))) + (padded ? 2 * PAD_X : 0)
  const h = size.lines.length * FLOW_LINE_HEIGHT + (padded ? 2 * PAD_Y : 0)
  return [
    [w / 2, h / 2],
    [-w / 2, h / 2],
    [w / 2, -h / 2],
    [-w / 2, -h / 2],
  ]
}

test.each([SHORT, LONG])('an action holds its padded text block (%s)', (text) => {
  const size = flowNodeSize(step('action', text), estimate)

  for (const [dx, dy] of corners(size, true)) {
    expect(Math.abs(dx)).toBeLessThanOrEqual(size.width / 2)
    expect(Math.abs(dy)).toBeLessThanOrEqual(size.height / 2)
  }
})

test.each([SHORT, LONG])('a pill holds its text block inside the round ends (%s)', (text) => {
  const size = flowNodeSize(step('end', text), estimate)
  const r = size.height / 2

  for (const [dx, dy] of corners(size, false)) {
    const past = Math.abs(dx) - (size.width / 2 - r)
    expect(past <= 0 ? true : Math.hypot(past, dy) < r).toBe(true)
    expect(Math.abs(dy)).toBeLessThan(r)
  }
})

test.each([SHORT, LONG])('a diamond holds its padded text block (%s)', (text) => {
  const size = flowNodeSize(step('decision', text), estimate)

  for (const [dx, dy] of corners(size, true))
    expect(Math.abs(dx) / (size.width / 2) + Math.abs(dy) / (size.height / 2)).toBeLessThanOrEqual(
      1 + 1e-9,
    )
  for (const [dx, dy] of corners(size, false))
    expect(Math.abs(dx) / (size.width / 2) + Math.abs(dy) / (size.height / 2)).toBeLessThan(1)
})

test('a diamond is wider and taller than the action with the same text', () => {
  const action = flowNodeSize(step('action', SHORT), estimate)
  const diamond = flowNodeSize(step('decision', SHORT), estimate)

  expect(diamond.width).toBe(action.width + 2 * action.height)
  expect(diamond.height).toBe(action.width / 2 + action.height)
})

test('a tag is its text plus 8px each side, 18px high', () => {
  expect(tagSize('yes', estimate)).toEqual({ width: estimate('yes', 'tag') + 16, height: 18 })
  expect(tagSize('start or end', estimate).width).toBeGreaterThan(tagSize('yes', estimate).width)
})

function laid(shape: DiagramNode['shape'], x: number, y: number, size: [number, number]): LaidNode {
  return { ...step(shape, 'x'), x, y, width: size[0], height: size[1] }
}

test('a line leaving a diamond starts on its side, not in the empty corner', () => {
  const diamond = laid('decision', 100, 100, [200, 100]) // centre (200, 150)
  const target = laid('action', 100, 300, [200, 40])
  const points = [
    { x: 230, y: 200 },
    { x: 230, y: 300 },
  ]

  const clipped = clipToOutline(points, diamond, target)

  expect(clipped[0].x).toBe(230)
  expect(clipped[0].y).toBeCloseTo(150 + 50 * (1 - 30 / 100))
  expect(Math.abs(clipped[0].x - 200) / 100 + Math.abs(clipped[0].y - 150) / 50).toBeCloseTo(1)
  expect(clipped[1]).toEqual({ x: 230, y: 300 })
})

test('a line arriving at the top or the side of a diamond ends on its outline', () => {
  const source = laid('action', 100, 0, [200, 40])
  const diamond = laid('decision', 100, 100, [200, 100]) // centre (200, 150)

  const top = clipToOutline(
    [
      { x: 170, y: 40 },
      { x: 170, y: 100 },
    ],
    source,
    diamond,
  )
  const side = clipToOutline(
    [
      { x: 400, y: 170 },
      { x: 300, y: 170 },
    ],
    source,
    diamond,
  )

  expect(top[1].x).toBe(170)
  expect(top[1].y).toBeCloseTo(150 - 50 * (1 - 30 / 100))
  expect(side[1].y).toBe(170)
  expect(side[1].x).toBeCloseTo(200 + 100 * (1 - 20 / 50))
})

test('a horizontal line meets a diamond on the outline too', () => {
  const diamond = laid('decision', 100, 100, [200, 100]) // centre (200, 150)
  const other = laid('action', 400, 100, [100, 40])

  const [start] = clipToOutline(
    [
      { x: 300, y: 170 },
      { x: 400, y: 170 },
    ],
    diamond,
    other,
  )

  expect(start.y).toBe(170)
  expect(start.x).toBeCloseTo(200 + 100 * (1 - 20 / 50))
})

test('a line arriving at a pill ends on the curve', () => {
  const source = laid('action', 0, 0, [100, 40])
  const pill = laid('end', 100, 100, [200, 40]) // centre (200, 120), radius 20
  // arrives horizontally at the right end, 10px above the centre
  const right = clipToOutline(
    [
      { x: 350, y: 110 },
      { x: 300, y: 110 },
    ],
    source,
    pill,
  )
  // arrives vertically at the top, over the curved part
  const top = clipToOutline(
    [
      { x: 0, y: 0 },
      { x: 110, y: 50 },
      { x: 110, y: 100 },
    ],
    source,
    pill,
  )

  expect(right[1].y).toBe(110)
  expect(Math.hypot(right[1].x - 280, right[1].y - 120)).toBeCloseTo(20)
  expect(top[2].x).toBe(110)
  expect(Math.hypot(top[2].x - 120, top[2].y - 120)).toBeCloseTo(20)
  expect(top[1]).toEqual({ x: 110, y: 50 })
})

test('a line over the flat part of a pill, or at an action, is left as it was', () => {
  const pill = laid('start', 100, 100, [200, 40])
  const action = laid('action', 100, 300, [200, 40])
  const points = [
    { x: 200, y: 140 },
    { x: 200, y: 300 },
  ]

  expect(clipToOutline(points, pill, action)).toEqual(points)
})

test('a line with a slanting end, or one point, is left alone', () => {
  const diamond = laid('decision', 100, 100, [200, 100])
  const slanted = [
    { x: 230, y: 200 },
    { x: 260, y: 260 },
  ]
  const lone = [{ x: 230, y: 200 }]

  expect(clipToOutline(slanted, diamond, diamond)).toEqual(slanted)
  expect(clipToOutline(lone, diamond, diamond)).toEqual(lone)
})

test('a diagram node with no shape is never clipped', () => {
  const plain = laid(undefined, 100, 100, [200, 100])
  const points = [
    { x: 230, y: 200 },
    { x: 230, y: 300 },
  ]

  expect(clipToOutline(points, plain, plain)).toEqual(points)
})

test('the left end and the bottom of a pill are curved too', () => {
  const pill = laid('start', 100, 100, [200, 40]) // centre (200, 120), radius 20, circles at 120 and 280
  const other = laid('action', 0, 300, [100, 40])

  const [left] = clipToOutline(
    [
      { x: 100, y: 110 },
      { x: 50, y: 110 },
    ],
    pill,
    other,
  )
  const [bottom] = clipToOutline(
    [
      { x: 290, y: 140 },
      { x: 290, y: 200 },
    ],
    pill,
    other,
  )
  const [right] = clipToOutline(
    [
      { x: 300, y: 110 },
      { x: 350, y: 110 },
    ],
    pill,
    other,
  )

  expect(left.y).toBe(110)
  expect(left.x).toBeCloseTo(120 - Math.sqrt(300))
  expect(bottom.x).toBe(290)
  expect(bottom.y).toBeCloseTo(120 + Math.sqrt(300))
  expect(right.x).toBeCloseTo(280 + Math.sqrt(300))
})

test('a line leaving the left side of a diamond meets the outline there', () => {
  const diamond = laid('decision', 100, 100, [200, 100]) // centre (200, 150)
  const other = laid('action', -200, 100, [100, 40])

  const [start] = clipToOutline(
    [
      { x: 100, y: 170 },
      { x: 0, y: 170 },
    ],
    diamond,
    other,
  )

  expect(start.y).toBe(170)
  expect(start.x).toBeCloseTo(200 - 100 * (1 - 20 / 50))
})

test('the end of an end pill and of a start pill are both curved, an action is not', () => {
  const kinds = ['start', 'end', 'action'] as const
  const other = laid('action', 0, 300, [100, 40])
  const points = [
    { x: 290, y: 140 },
    { x: 290, y: 200 },
  ]

  const [start, end, action] = kinds.map(
    (kind) => clipToOutline(points, laid(kind, 100, 100, [200, 40]), other)[0],
  )

  expect(start.y).toBeCloseTo(120 + Math.sqrt(300))
  expect(end.y).toBeCloseTo(120 + Math.sqrt(300))
  expect(action).toEqual({ x: 290, y: 140 })
})

test('a zero-length first or last segment is left alone', () => {
  const diamond = laid('decision', 100, 100, [200, 100])
  const same = [
    { x: 230, y: 200 },
    { x: 230, y: 200 },
  ]

  expect(clipToOutline(same, diamond, diamond)).toEqual(same)
})

const box = (x: number, y: number, width = 10, height = 10) => ({ x, y, width, height })

test.each([
  ['inside', box(2, 2, 4, 4), true],
  ['over a corner', box(5, 5), true],
  ['one pixel over the right side', box(9, 0), true],
  ['one pixel over the left side', box(-9, 0), true],
  ['one pixel over the bottom', box(0, 9), true],
  ['one pixel over the top', box(0, -9), true],
  ['touching on the right', box(10, 0), false],
  ['touching on the left', box(-10, 0), false],
  ['touching below', box(0, 10), false],
  ['touching above', box(0, -10), false],
  ['far to the right', box(50, 0), false],
  ['far above', box(0, -50), false],
  ['beside it but at the same height as far away', box(50, 5), false],
  ['below it but at the same width as far away', box(5, 50), false],
])('two boxes: %s', (_, other, expected) => {
  expect(overlaps(box(0, 0), other)).toBe(expected)
  expect(overlaps(other, box(0, 0))).toBe(expected)
})

test('tags collide when one lies over another tag or over a step, not when they only touch', () => {
  const far = box(500, 500)

  expect(tagsCollide([box(0, 0), box(5, 5)], [far])).toBe(true)
  expect(tagsCollide([box(0, 0), far], [box(5, 5)])).toBe(true)
  expect(tagsCollide([far, box(0, 0)], [box(5, 5)])).toBe(true)
  expect(tagsCollide([box(0, 0), box(10, 0)], [box(0, 10)])).toBe(false)
  expect(tagsCollide([], [box(0, 0)])).toBe(false)
  expect(tagsCollide([box(0, 0)], [])).toBe(false)
})

test('a tag does not collide with itself', () => {
  expect(tagsCollide([box(0, 0)], [far(500)])).toBe(false)
})

function far(x: number) {
  return box(x, x)
}
