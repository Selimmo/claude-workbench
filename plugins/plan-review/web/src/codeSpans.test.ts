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
