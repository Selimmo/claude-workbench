import example from '../../examples/plan.json'
import type { Plan, SequenceFlow } from './plan'
import {
  BOX_GAP,
  BOX_PADDING,
  COLUMN_WIDTH,
  HEAD_HEIGHT,
  LABEL_PADDING,
  STEP_HEIGHT,
  sequenceLayout,
} from './sequence'

const flow = (example as Plan).flows[0] as SequenceFlow

test('participants become evenly spaced columns, in plan order', () => {
  const laid = sequenceLayout(flow, () => 10) // short text: nothing needs extra room

  expect(laid.participants.map((p) => [p.name, p.x])).toEqual([
    ['Web client', COLUMN_WIDTH / 2],
    ['Agent worker', COLUMN_WIDTH * 1.5],
    ['Orchestrator', COLUMN_WIDTH * 2.5],
    ['LLM', COLUMN_WIDTH * 3.5],
  ])
  expect(laid.width).toBe(COLUMN_WIDTH * 4)
})

test('messages go down the page in step order, between their participants columns', () => {
  const laid = sequenceLayout(flow, () => 10)

  expect(laid.messages.map((m) => m.y)).toEqual(
    [0, 1, 2, 3, 4].map((i) => HEAD_HEIGHT + (i + 0.5) * STEP_HEIGHT),
  )
  const reply = laid.messages.find((m) => m.id === 'flow:hint/4')
  expect(reply).toMatchObject({ fromX: COLUMN_WIDTH * 2.5, toX: COLUMN_WIDTH / 2, status: 'added' })
  expect(laid.height).toBe(HEAD_HEIGHT + 5 * STEP_HEIGHT)
})

const seq = (names: string[], steps: [number, number, string][]): SequenceFlow => ({
  id: 'f',
  title: 'f',
  kind: 'sequence',
  participants: names.map((name, i) => ({ id: `p${i}`, name, status: 'unchanged' })),
  steps: steps.map(([from, to, label], i) => ({
    id: `s${i}`,
    from: `p${from}`,
    to: `p${to}`,
    label,
    status: 'unchanged',
  })),
})
const tenPerChar = (text: string) => text.length * 10

test('a long participant name widens its box, and neighbouring boxes never overlap', () => {
  const laid = sequenceLayout(seq(['A', 'x'.repeat(40), 'B'], []), tenPerChar)
  const [a, long, b] = laid.participants

  expect(long.width).toBe(400 + 2 * BOX_PADDING)
  expect(long.x - long.width / 2).toBeGreaterThanOrEqual(a.x + a.width / 2 + BOX_GAP)
  expect(b.x - b.width / 2).toBeGreaterThanOrEqual(long.x + long.width / 2 + BOX_GAP)
  expect(laid.width).toBeGreaterThanOrEqual(b.x + b.width / 2)
})

test('a step label wider than its columns pushes them apart so it fits between them', () => {
  const laid = sequenceLayout(seq(['A', 'B'], [[0, 1, 'y'.repeat(50)]]), tenPerChar)
  const [m] = laid.messages

  expect(Math.abs(m.toX - m.fromX)).toBeGreaterThanOrEqual(500 + 2 * LABEL_PADDING)
})

test('a label across several columns only needs the whole span to fit', () => {
  const laid = sequenceLayout(seq(['A', 'B', 'C'], [[0, 2, 'z'.repeat(45)]]), tenPerChar)
  const [a, b, c] = laid.participants

  expect(c.x - a.x).toBeGreaterThanOrEqual(450 + 2 * LABEL_PADDING)
  expect(b.x - a.x).toBe(COLUMN_WIDTH) // the columns in between keep their normal spacing
})

const selfNeed = 400 + 2 * LABEL_PADDING // a 40-character label at 10px a character

test('a step to itself on the first column keeps its label inside the diagram', () => {
  const laid = sequenceLayout(seq(['A', 'B'], [[0, 0, 'w'.repeat(40)]]), tenPerChar)
  const [m] = laid.messages

  expect(m.fromX - selfNeed / 2).toBeGreaterThanOrEqual(0)
})

test('a step to itself on the last column keeps its label inside the diagram', () => {
  const laid = sequenceLayout(seq(['A', 'B'], [[1, 1, 'w'.repeat(40)]]), tenPerChar)
  const [m] = laid.messages

  expect(m.fromX + selfNeed / 2).toBeLessThanOrEqual(laid.width)
})

test('a step to itself between columns pushes both neighbours away from its label', () => {
  const laid = sequenceLayout(seq(['A', 'B', 'C'], [[1, 1, 'w'.repeat(40)]]), tenPerChar)
  const [a, b, c] = laid.participants

  expect(b.x - a.x).toBeGreaterThanOrEqual(selfNeed / 2)
  expect(c.x - b.x).toBeGreaterThanOrEqual(selfNeed / 2)
})

test('a step to itself reports its label width, so its click target can cover the label', () => {
  const laid = sequenceLayout(seq(['A'], [[0, 0, 'w'.repeat(40)]]), tenPerChar)

  expect(laid.messages[0].labelWidth).toBe(400)
})

test('shorter arrows claim room first, so a long arrow over them widens nothing more', () => {
  // Listed long-first: the 0→1 label alone already makes 0→2 wide enough.
  const flow = seq(
    ['A', 'B', 'C'],
    [
      [0, 2, 'z'.repeat(45)],
      [0, 1, 'y'.repeat(40)],
    ],
  )
  const [, b, c] = sequenceLayout(flow, tenPerChar).participants

  expect(c.x - b.x).toBe(COLUMN_WIDTH)
})
