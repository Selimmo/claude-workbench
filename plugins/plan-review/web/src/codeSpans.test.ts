import { codeSpans } from './codeSpans'

test('text in backticks becomes a code span', () => {
  expect(codeSpans('run `uv sync` then `pytest`')).toEqual([
    { code: false, text: 'run ' },
    { code: true, text: 'uv sync' },
    { code: false, text: ' then ' },
    { code: true, text: 'pytest' },
  ])
  expect(codeSpans('no code here')).toEqual([{ code: false, text: 'no code here' }])
})

test('a lone backtick or an empty pair stays as written', () => {
  expect(codeSpans('a ` b')).toEqual([{ code: false, text: 'a ` b' }])
  expect(codeSpans('a `` b')).toEqual([{ code: false, text: 'a `` b' }])
})

test('a pair at the very start of the text is a code span', () => {
  expect(codeSpans('`run` it')).toEqual([
    { code: true, text: 'run' },
    { code: false, text: ' it' },
  ])
  expect(codeSpans('`only`')).toEqual([{ code: true, text: 'only' }])
})

test('a pair at the very end, and text after the last pair, are kept', () => {
  expect(codeSpans('see `it`')).toEqual([
    { code: false, text: 'see ' },
    { code: true, text: 'it' },
  ])
  expect(codeSpans('`a` and then some')).toEqual([
    { code: true, text: 'a' },
    { code: false, text: ' and then some' },
  ])
})

test('two pairs touching make two code spans', () => {
  expect(codeSpans('`a``b`')).toEqual([
    { code: true, text: 'a' },
    { code: true, text: 'b' },
  ])
})

test('a lone backtick after a pair stays as written', () => {
  expect(codeSpans('`a` then `')).toEqual([
    { code: true, text: 'a' },
    { code: false, text: ' then `' },
  ])
})
