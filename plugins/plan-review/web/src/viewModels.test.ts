import example from '../../examples/plan.json'
import type { Plan } from './plan'
import { filesByKind, risksByKind, tabOf, tabsFor } from './viewModels'

const plan = example as Plan

test('tabs list every section, architecture only when the plan has one', () => {
  expect(tabsFor(plan).map((t) => t.id)).toEqual([
    'classes',
    'flows',
    'architecture',
    'files',
    'tests',
    'risks',
  ])
  expect(tabsFor({ ...plan, architecture: null }).map((t) => t.id)).not.toContain('architecture')
})

test('files are grouped by kind in a fixed order, skipping empty groups', () => {
  const groups = filesByKind({ ...plan, files: plan.files.filter((f) => f.kind !== 'config') })

  expect(groups.map((g) => g.kind)).toEqual(['code', 'test', 'doc'])
  expect(groups[0].files.map((f) => f.path)).toEqual([
    'backend/src/app/core/hints.py',
    'backend/src/app/core/orchestrator.py',
    'backend/src/app/core/events.py',
    'backend/src/app/core/commands.py',
  ])
})

test('risks and questions are separated and sorted by severity, high first', () => {
  const risk = (id: string, kind: 'risk' | 'question', severity: 'low' | 'medium' | 'high') => ({
    id,
    kind,
    severity,
    text: id,
  })
  const sections = risksByKind({
    ...plan,
    risks: [
      risk('r-low', 'risk', 'low'),
      risk('q-med', 'question', 'medium'),
      risk('r-high', 'risk', 'high'),
      risk('r-low-2', 'risk', 'low'),
      risk('q-high', 'question', 'high'),
    ],
  })

  expect(sections.risks.map((r) => r.id)).toEqual(['r-high', 'r-low', 'r-low-2'])
  expect(sections.questions.map((r) => r.id)).toEqual(['q-high', 'q-med'])
})

test.each([
  ['class:HintPolicy', 'classes'],
  ['class:HintPolicy.next_level', 'classes'],
  ['rel:orch-policy', 'classes'],
  ['flow:hint', 'flows'],
  ['flow:hint/orch', 'flows'],
  ['flow:level/e2', 'flows'],
  ['arch:agent', 'architecture'],
  ['arch:agent-db', 'architecture'],
  ['file:hints', 'files'],
  ['test:3', 'tests'],
  ['risk:1', 'risks'],
])('element %s lives on the %s tab', (id, tab) => {
  expect(tabOf(plan, id)).toBe(tab)
})

test('an id not in the plan has no tab', () => {
  expect(tabOf(plan, 'class:Gone')).toBeNull()
})
