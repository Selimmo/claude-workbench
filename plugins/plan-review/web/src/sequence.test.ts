import example from '../../examples/plan.json'
import type { Plan, SequenceFlow } from './plan'
import { COLUMN_WIDTH, HEAD_HEIGHT, STEP_HEIGHT, sequenceLayout } from './sequence'

const flow = (example as Plan).flows[0] as SequenceFlow

test('participants become evenly spaced columns, in plan order', () => {
  const laid = sequenceLayout(flow)

  expect(laid.participants.map((p) => [p.name, p.x])).toEqual([
    ['Web client', COLUMN_WIDTH / 2],
    ['Agent worker', COLUMN_WIDTH * 1.5],
    ['Orchestrator', COLUMN_WIDTH * 2.5],
    ['LLM', COLUMN_WIDTH * 3.5],
  ])
  expect(laid.width).toBe(COLUMN_WIDTH * 4)
})

test('messages go down the page in step order, between their participants columns', () => {
  const laid = sequenceLayout(flow)

  expect(laid.messages.map((m) => m.y)).toEqual(
    [0, 1, 2, 3, 4].map((i) => HEAD_HEIGHT + (i + 0.5) * STEP_HEIGHT),
  )
  const reply = laid.messages.find((m) => m.id === 'flow:hint/4')
  expect(reply).toMatchObject({ fromX: COLUMN_WIDTH * 2.5, toX: COLUMN_WIDTH / 2, status: 'added' })
  expect(laid.height).toBe(HEAD_HEIGHT + 5 * STEP_HEIGHT)
})
