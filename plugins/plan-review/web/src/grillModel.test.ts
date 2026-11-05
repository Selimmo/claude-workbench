import type { AnswerDraft } from './grill'
import {
  answerLine,
  asksLeft,
  canSubmit,
  openQuestions,
  responded,
  roundIsOpen,
} from './grillModel'
import { answered, grill, question } from './test/grillData'

test('open questions come from every round', () => {
  const g = grill(
    [question('q1', { answer: answered('own', { text: 'x' }) }), question('q2')],
    [question('q3')],
  )

  expect(openQuestions(g).map((q) => q.id)).toEqual(['q2', 'q3'])
  expect(roundIsOpen(g.rounds[0])).toBe(true)
  expect(roundIsOpen({ n: 9, questions: [question('q9', { answer: answered('own') })] })).toBe(
    false,
  )
})

test('a response is a pick that still exists, or a written answer or ask', () => {
  const q = question('q1')

  expect(responded(q)).toBe(false)
  expect(responded(q, { kind: 'choice', choice_id: 'a' })).toBe(true)
  expect(responded(q, { kind: 'choice', choice_id: 'gone' })).toBe(false) // revised away
  expect(responded(q, { kind: 'own', text: '  ' })).toBe(false)
  expect(responded(q, { kind: 'own', text: 'Mine' })).toBe(true)
  expect(responded(q, { kind: 'ask', text: 'Why?' })).toBe(true)
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

test('asks left counts the owner’s messages against the limit', () => {
  const thread = [
    { author: 'owner' as const, text: '?', at: '' },
    { author: 'claude' as const, text: '.', at: '' },
    { author: 'owner' as const, text: '??', at: '' },
  ]

  expect(asksLeft(question('q1'), 3)).toBe(3)
  expect(asksLeft(question('q1', { thread }), 3)).toBe(1)
})

test('an answer line reads title → answer', () => {
  const picked = question('q1', {
    answer: answered('choice', { choice_id: 'b', text: 'for now' }),
  })
  const own = question('q2', { answer: answered('own', { text: 'Mine' }) })

  expect(answerLine(picked)).toBe('Question q1? → Choice b (for now)')
  expect(answerLine(own)).toBe('Question q2? → Mine')
  expect(answerLine(question('q3', { answer: answered('choice', { choice_id: 'a' }) }))).toBe(
    'Question q3? → Choice a',
  )
})
