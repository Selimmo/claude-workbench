import type { AnswerDraft } from './grill'
import {
  answerParts,
  canSubmit,
  decisionsByTopic,
  openQuestions,
  otherIsFinal,
  pick,
  replacedCount,
  responded,
} from './grillModel'
import { answered, grill, question } from './test/grillData'

test('open questions come from every round', () => {
  const g = grill(
    [question('q1', { answer: answered('choice', { choice_id: 'a' }) }), question('q2')],
    [question('q3')],
  )

  expect(openQuestions(g).map((q) => q.id)).toEqual(['q2', 'q3'])
})

test('a response is a pick that still exists, or an Other with text', () => {
  const q = question('q1')

  expect(responded(q)).toBe(false)
  expect(responded(q, { kind: 'choice', choice_id: 'a' })).toBe(true)
  expect(responded(q, { kind: 'choice', choice_id: 'gone' })).toBe(false) // revised away
  expect(responded(q, { kind: 'other', text: '  ' })).toBe(false)
  expect(responded(q, { kind: 'other' })).toBe(false)
  expect(responded(q, { kind: 'other', text: 'Mine' })).toBe(true)
})

test('submit needs a response to every open question, and the owner’s turn', () => {
  const g = grill([question('q1'), question('q2')])
  const pick: AnswerDraft = { kind: 'choice', choice_id: 'a' }

  expect(canSubmit(g, { q1: pick })).toBe(false)
  expect(canSubmit(g, { q1: pick, q2: pick })).toBe(true)
  expect(
    canSubmit({ ...g, log: [{ kind: 'answers', text: null, at: '' }] }, { q1: pick, q2: pick }),
  ).toBe(false)
  expect(canSubmit({ ...g, done: true }, { q1: pick, q2: pick })).toBe(false)
  expect(canSubmit(grill([]), {})).toBe(false)
})

test('picking another option keeps the text already typed', () => {
  const typed: AnswerDraft = { kind: 'choice', choice_id: 'b', text: 'x' }

  expect(pick(typed, { kind: 'choice', choice_id: 'c' })).toEqual({
    kind: 'choice',
    choice_id: 'c',
    text: 'x',
  })
  expect(pick(typed, { kind: 'other' })).toEqual({ kind: 'other', text: 'x' })
  expect(pick(undefined, { kind: 'choice', choice_id: 'a' })).toEqual({
    kind: 'choice',
    choice_id: 'a',
  })
  expect(pick(undefined, { kind: 'other' })).toEqual({ kind: 'other' })
  expect(pick({ kind: 'other', text: 'y' }, { kind: 'choice', choice_id: 'a' })).toEqual({
    kind: 'choice',
    choice_id: 'a',
    text: 'y',
  })
})

test('Other is final once Claude has replied the limit', () => {
  const thread = (claude: number) =>
    Array.from({ length: claude }, () => [
      { author: 'owner' as const, text: '?', at: '' },
      { author: 'claude' as const, text: '.', at: '' },
    ]).flat()

  expect(otherIsFinal(question('q1', { thread: thread(2) }), 3)).toBe(false)
  expect(otherIsFinal(question('q1', { thread: thread(3) }), 3)).toBe(true)
})

test('an answered question reads as its answer and note', () => {
  const picked = question('q1', {
    answer: answered('choice', { choice_id: 'b', text: 'for now' }),
  })
  const plain = question('q3', { answer: answered('choice', { choice_id: 'a' }) })

  expect(answerParts(picked)).toEqual({ answer: 'Choice b', note: 'for now' })
  expect(answerParts(plain)).toEqual({ answer: 'Choice a', note: null })
  expect(answerParts(question('q2', { answer: answered('other', { text: 'Mine' }) }))).toEqual({
    answer: 'Mine',
    note: null,
  })
  expect(answerParts(question('q4', { answer: answered('own', { text: 'Old' }) }))).toEqual({
    answer: 'Old',
    note: null,
  })
})

test('decisions are grouped by topic, replaced ones only when asked', () => {
  const decision = (id: string, topic: string, replaces: string | null = null) => ({
    id,
    topic,
    decision: `Decision ${id}`,
    choice: 'Yes',
    why: null,
    question_id: null,
    replaces,
  })
  const g = grill([question('q1')])
  g.decisions = [
    decision('d1', 'Scoring'),
    decision('d2', 'Content'),
    decision('d3', 'Scoring', 'd1'),
  ]

  expect(decisionsByTopic(g, false).map((t) => [t.topic, t.decisions.map((d) => d.id)])).toEqual([
    ['Scoring', ['d3']],
    ['Content', ['d2']],
  ])
  const all = decisionsByTopic(g, true)
  expect(all.map((t) => [t.topic, t.decisions.map((d) => [d.id, d.replaced])])).toEqual([
    [
      'Scoring',
      [
        ['d1', true],
        ['d3', false],
      ],
    ],
    ['Content', [['d2', false]]],
  ])
  expect(replacedCount(g)).toBe(1)
  expect(replacedCount(grill([]))).toBe(0)
})

test('a topic whose decisions are all replaced is left out until replaced ones show', () => {
  const decision = (id: string, topic: string, replaces: string | null = null) => ({
    id,
    topic,
    decision: `Decision ${id}`,
    choice: 'Yes',
    why: null,
    question_id: null,
    replaces,
  })
  const g = grill([question('q1')])
  g.decisions = [decision('d1', 'Old topic'), decision('d2', 'New topic', 'd1')]

  expect(decisionsByTopic(g, false).map((t) => t.topic)).toEqual(['New topic'])
  expect(decisionsByTopic(g, true).map((t) => t.topic)).toEqual(['Old topic', 'New topic'])
})
