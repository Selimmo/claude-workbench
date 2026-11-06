import { act, render } from '@testing-library/react'

import { StickyHead } from './StickyHead'

type Callback = () => void
let callbacks: Callback[] = []

beforeEach(() => {
  callbacks = []
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(cb: Callback) {
        callbacks.push(cb)
      }
      observe() {}
      disconnect() {}
    },
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.documentElement.style.removeProperty('--sticky-head-height')
})

test('publishes its real height as --sticky-head-height and follows it when it changes', () => {
  const { container } = render(<StickyHead>notice</StickyHead>)
  const head = container.querySelector<HTMLElement>('.sticky-head')!
  let height = 144
  vi.spyOn(head, 'getBoundingClientRect').mockImplementation(
    () => ({ height, bottom: height }) as DOMRect,
  )

  act(() => callbacks.forEach((cb) => cb()))
  expect(document.documentElement.style.getPropertyValue('--sticky-head-height')).toBe('144px')

  height = 100
  act(() => callbacks.forEach((cb) => cb()))
  expect(document.documentElement.style.getPropertyValue('--sticky-head-height')).toBe('100px')
})

test('without ResizeObserver it still renders', () => {
  vi.unstubAllGlobals()
  vi.stubGlobal('ResizeObserver', undefined)
  const { getByText } = render(<StickyHead>notice</StickyHead>)
  expect(getByText('notice')).toBeInTheDocument()
})
