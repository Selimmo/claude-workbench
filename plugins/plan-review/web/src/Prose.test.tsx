import { render } from '@testing-library/react'
import { Prose } from './Prose'

test('Prose shows backticked text as a code chip', () => {
  const { container } = render(<p>{<Prose text="Use `x: int` then here" />}</p>)

  const chips = container.querySelectorAll('code.inline-code')
  expect([...chips].map((c) => c.textContent)).toEqual(['x: int'])
  expect(container.textContent).toBe('Use x: int then here')
})
