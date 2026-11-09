import { authorLabel, canResolve, type Thread } from './threads'

test('authorLabel names the owner You and both agent values Agent', () => {
  expect(authorLabel('owner')).toBe('You')
  expect(authorLabel('agent')).toBe('Agent')
  expect(authorLabel('claude')).toBe('Agent') // saved before the agent was neutral
})

test('canResolve is true only when the agent spoke last', () => {
  const at = '2026-11-02T10:00:00Z'
  const make = (...authors: Thread['messages'][number]['author'][]): Thread => ({
    id: 't-1',
    anchor: 'tab:risks',
    messages: authors.map((author) => ({ author, text: 'x', at })),
    resolved: false,
    orphaned: false,
  })
  expect(canResolve(make('owner'))).toBe(false)
  expect(canResolve(make('owner', 'agent'))).toBe(true)
  expect(canResolve(make('owner', 'claude'))).toBe(true)
  expect(canResolve(make('owner', 'agent', 'owner'))).toBe(false)
})
