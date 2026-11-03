import { act, render, screen } from '@testing-library/react'

import { Toast } from './Toast'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('a success toast closes by itself after its duration', () => {
  const onClose = vi.fn()
  render(<Toast note={{ kind: 'ok', text: 'Review sent' }} onClose={onClose} duration={1000} />)

  act(() => vi.advanceTimersByTime(1000))

  expect(onClose).toHaveBeenCalled()
})

test('an error toast stays until it is dismissed', () => {
  const onClose = vi.fn()
  render(<Toast note={{ kind: 'error', text: 'Not sent' }} onClose={onClose} duration={1000} />)

  act(() => vi.advanceTimersByTime(60_000))

  expect(onClose).not.toHaveBeenCalled()
  expect(screen.getByRole('alert')).toHaveTextContent('Not sent')
})
