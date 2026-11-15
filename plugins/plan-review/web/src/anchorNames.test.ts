import example from '../../examples/plan.json'
import { anchorName, tidyId } from './anchorNames'
import type { Plan } from './plan'

const base = example as Plan
const plan: Plan = { ...base, acceptance_criteria: ['Hints escalate', 'No hints after the limit'] }

test.each([
  ['a class', 'class:HintPolicy', 'HintPolicy'],
  ['a member', 'class:HintPolicy.next_level', 'HintPolicy › next_level'],
  ['a relation', 'rel:orch-policy', 'Orchestrator → HintPolicy'],
  ['a flow', 'flow:level', 'Choosing the hint level'],
  ['a flowchart step', 'flow:level/check', 'Choosing the hint level › hints_given < max_hints?'],
  [
    'a flowchart line with a label',
    'flow:level/e2',
    'hints_given < max_hints? → Give next level (yes)',
  ],
  ['a flowchart line with no label', 'flow:level/e1', 'Hint requested → hints_given < max_hints?'],
  ['a sequence participant', 'flow:hint/orch', 'Candidate requests a hint › Orchestrator'],
  ['a sequence step', 'flow:hint/1', 'Candidate requests a hint › request_hint'],
  ['an architecture box', 'arch:agent', 'Agent worker'],
  ['an architecture line with a label', 'arch:agent-ollama', 'Agent worker → Ollama (HTTP)'],
  ['an architecture line with no label', 'arch:agent-db', 'Agent worker → SQLite sessions'],
  ['a file', 'file:hints', 'backend/src/app/core/hints.py'],
  ['a test', 'test:1', 'Test › test_first_hint_is_a_nudge'],
  ['a risk', 'risk:2', "Risk › Removing '/hint' breaks anyone used to typing it."],
  ['a question', 'risk:3', "Question › Should hints count against the candidate's score?"],
  ['a criterion', 'criterion:2', 'Criterion 2 › No hints after the limit'],
  ['a tab', 'tab:classes', 'Tab › Classes'],
  ['the criteria tab', 'tab:criteria', 'Tab › Acceptance criteria'],
  ['the title', 'header:title', 'Title'],
  ['the summary', 'header:summary', 'Summary'],
])('%s is named for what it is: %s', (_, anchor, expected) => {
  const short = expected.length > 60 ? `${expected.slice(0, 60)}…` : expected
  expect(anchorName(plan, anchor)).toEqual({ short, full: expected, id: anchor })
})

test('a member with no name is named by its signature', () => {
  const unnamed: Plan = {
    ...plan,
    classes: [
      {
        ...plan.classes[0],
        members: [{ id: 'class:HintPolicy.old', signature: 'old(x: int)', status: 'added' }],
      },
    ],
  }

  expect(anchorName(unnamed, 'class:HintPolicy.old').short).toBe('HintPolicy › old(x: int)')
})

test('a name of 60 characters stays whole, a longer one is cut to 60 plus an ellipsis', () => {
  const name = (length: number): Plan => ({
    ...plan,
    classes: [{ ...plan.classes[0], name: 'N'.repeat(length) }],
  })

  expect(anchorName(name(60), 'class:HintPolicy').short).toBe('N'.repeat(60))
  const cut = anchorName(name(61), 'class:HintPolicy')
  expect(cut.short).toBe(`${'N'.repeat(60)}…`)
  expect(cut.full).toBe('N'.repeat(61))
  expect(cut.id).toBe('class:HintPolicy')
})

test.each([
  ['flow:gone/step', 'gone › step'],
  ['test:9', 'test 9'],
  ['class:Old.member', 'Old › member'],
  ['criterion:7', 'criterion 7'],
  ['rel:a-b', 'a-b'],
  ['plain', 'plain'],
])('an anchor that is not in the plan is tidied: %s → %s', (anchor, tidy) => {
  expect(tidyId(anchor)).toBe(tidy)
  expect(anchorName(plan, anchor)).toEqual({ short: tidy, full: tidy, id: anchor })
})

test.each([
  [':x', 'x'],
  ['some.thing/else', 'some.thing/else'],
  ['x:a9', 'a9'],
  ['x:9a', '9a'],
  ['test:12', 'test 12'],
])('tidyId(%s) is %s', (anchor, tidy) => {
  expect(tidyId(anchor)).toBe(tidy)
})

test('criterion ids are read whole and only from the start', () => {
  const many: Plan = {
    ...plan,
    acceptance_criteria: Array.from({ length: 12 }, (_, i) => `C${i + 1}`),
  }

  expect(anchorName(many, 'criterion:12').full).toBe('Criterion 12 › C12')
  expect(anchorName(many, 'criterion:1').full).toBe('Criterion 1 › C1')
  expect(anchorName(many, 'criterion:1x').full).toBe('1x')
  expect(anchorName(many, 'xcriterion:1').full).toBe('xcriterion 1')
  expect(anchorName(many, 'criterion:13').full).toBe('criterion 13')
})

test('a plan with no criteria, or no architecture, gives tidied names for their ids', () => {
  const bare = { ...base, architecture: null } as Plan

  expect(anchorName(bare, 'criterion:1').full).toBe('criterion 1')
  expect(anchorName(bare, 'arch:web').full).toBe('web')
  expect(anchorName(bare, 'arch:web-livekit').full).toBe('web-livekit')
})
