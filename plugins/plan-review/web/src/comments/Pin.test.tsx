import { act, render, screen } from '@testing-library/react'

import { Pin } from './Pin'

const rect = (left: number, top: number, right: number, bottom: number) =>
  ({ left, top, right, bottom, width: right - left, height: bottom - top }) as DOMRect

function diagramWithElementAt(box: DOMRect) {
  render(
    <div className="viewport">
      <div data-element-id="class:A" />
    </div>,
  )
  const viewport = document.querySelector<HTMLElement>('.viewport')!
  viewport.getBoundingClientRect = () => rect(0, 100, 800, 600)
  document.querySelector<HTMLElement>('[data-element-id="class:A"]')!.getBoundingClientRect = () =>
    box
}

const pin = () => (
  <Pin anchor="class:A" badge="1" label="1 message on class:A" preview="Hi" onOpen={() => {}} />
)

test('a pin shows at its element while the element is inside its diagram', async () => {
  diagramWithElementAt(rect(10, 200, 110, 260))

  render(pin())

  expect(await screen.findByRole('button', { name: '1 message on class:A' })).toBeInTheDocument()
})

test('a pin hides while its element is panned out of its diagram', () => {
  vi.useFakeTimers()
  diagramWithElementAt(rect(900, 200, 1000, 260))

  render(pin())
  act(() => vi.advanceTimersByTime(100)) // several animation frames of position tracking

  expect(screen.queryByRole('button', { name: '1 message on class:A' })).not.toBeInTheDocument()
  vi.useRealTimers()
})

test('a pin hides as soon as its element is panned out of its diagram', () => {
  vi.useFakeTimers()
  diagramWithElementAt(rect(10, 200, 110, 260))
  render(pin())
  act(() => vi.advanceTimersByTime(20))
  expect(screen.getByRole('button', { name: '1 message on class:A' })).toBeInTheDocument()

  document.querySelector<HTMLElement>('[data-element-id="class:A"]')!.getBoundingClientRect = () =>
    rect(900, 200, 1000, 260)
  act(() => vi.advanceTimersByTime(100))

  expect(screen.queryByRole('button', { name: '1 message on class:A' })).not.toBeInTheDocument()
  vi.useRealTimers()
})
