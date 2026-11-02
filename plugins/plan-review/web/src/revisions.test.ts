import example from '../../examples/plan.json'
import type { Plan } from './plan'
import { changedIds } from './revisions'

const plan = example as Plan

test('an identical plan has no changes', () => {
  expect(changedIds(plan, structuredClone(plan))).toEqual(new Set())
})

test('edited and added elements are reported by id, down to the member', () => {
  const next = structuredClone(plan)
  next.classes[0].members[1].signature = 'next_level(given: int) -> HintLevel'
  next.risks.push({ id: 'risk:4', kind: 'risk', text: 'New', severity: 'low' })
  next.tests[0].behaviour = 'Changed wording'

  expect(changedIds(plan, next)).toEqual(
    new Set(['class:HintPolicy.next_level', 'risk:4', 'test:1']),
  )
})

test("a class whose own fields change is reported, but not because of a member's change", () => {
  const next = structuredClone(plan)
  next.classes[0].status = 'modified'

  expect(changedIds(plan, next)).toEqual(new Set(['class:HintPolicy']))
})
