import { authorLabel } from './threads'

test('authorLabel names the owner You and both agent values Agent', () => {
  expect(authorLabel('owner')).toBe('You')
  expect(authorLabel('agent')).toBe('Agent')
  expect(authorLabel('claude')).toBe('Agent') // saved before the agent was neutral
})
