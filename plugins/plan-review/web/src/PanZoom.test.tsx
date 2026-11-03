import { act, fireEvent, render, screen } from '@testing-library/react'

import { PanZoom } from './PanZoom'

let viewportWidth = 1000
let resize: (() => void) | null = null

beforeEach(() => {
  // jsdom lays nothing out: give the viewport a size, as a browser would.
  viewportWidth = 1000
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => viewportWidth)
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(500)
  resize = null
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resize = callback
      }
      observe() {}
      disconnect() {}
    },
  )
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const overview = { boxes: [{ x: 0, y: 0, width: 100, height: 100 }], lines: [] }
const canvas = () => document.querySelector<HTMLElement>('.canvas')!
const transform = () => canvas().style.transform
const viewport = () => document.querySelector<HTMLElement>('.viewport')!
const minimap = () => screen.queryByRole('img', { name: 'Overview of the whole diagram' })
const button = (name: string) => screen.getByRole('button', { name })

function diagram(width = 4000, height = 1000) {
  return (
    <PanZoom width={width} height={height} overview={overview}>
      <div className="content" />
    </PanZoom>
  )
}

function drag(from: { x: number; y: number }, by: { x: number; y: number }, target?: Element) {
  const on = target ?? document.querySelector('.content')!
  fireEvent.pointerDown(on, { clientX: from.x, clientY: from.y, pointerId: 1, button: 0 })
  fireEvent.pointerMove(on, { clientX: from.x + by.x, clientY: from.y + by.y, pointerId: 1 })
  fireEvent.pointerUp(on, { clientX: from.x + by.x, clientY: from.y + by.y, pointerId: 1 })
}

test('a diagram starts fitted and centred in the whole viewport', () => {
  render(diagram())

  expect(transform()).toBe('translate(0px, 125px) scale(0.25)')
  expect(screen.getByText('25%')).toBeInTheDocument()
})

test('no minimap while the whole diagram is in view', () => {
  render(diagram())

  expect(minimap()).not.toBeInTheDocument()
})

test('Fill makes a wide diagram as tall as the viewport', () => {
  render(diagram())

  fireEvent.click(button('Fill'))

  expect(transform()).toBe('translate(0px, 0px) scale(0.5)')
})

test('the minimap appears once part of the diagram is off screen', () => {
  render(diagram())

  fireEvent.click(button('Fill'))

  expect(minimap()).toBeInTheDocument()
})

test('100% shows actual size around the middle of the view', () => {
  render(diagram())

  fireEvent.click(button('100%'))

  expect(transform()).toBe('translate(-1500px, -250px) scale(1)')
})

test('clicking the minimap centres the view on that point', () => {
  render(diagram())
  fireEvent.click(button('100%'))

  // The minimap is 220px wide for 4000px of content: x=55 is content x=1000, y=27.5 is y=500.
  fireEvent.pointerDown(minimap()!, { clientX: 55, clientY: 27.5, pointerId: 1 })

  expect(transform()).toBe('translate(-500px, -250px) scale(1)')
})

test('dragging in the minimap keeps centring the view under the pointer', () => {
  render(diagram())
  fireEvent.click(button('100%'))
  fireEvent.pointerDown(minimap()!, { clientX: 55, clientY: 27.5, pointerId: 1 })

  fireEvent.pointerMove(minimap()!, { clientX: 110, clientY: 27.5, pointerId: 1, buttons: 1 })

  expect(transform()).toBe('translate(-1500px, -250px) scale(1)')
})

test('Fit all brings the whole diagram back', () => {
  render(diagram())
  fireEvent.click(button('100%'))

  fireEvent.click(button('Fit all'))

  expect(transform()).toBe('translate(0px, 125px) scale(0.25)')
})

test('the wheel zooms around the pointer', () => {
  render(diagram())

  fireEvent.wheel(viewport(), { deltaY: -500, clientX: 0, clientY: 0 })

  const scale = 0.25 * Math.E
  expect(transform()).toBe(`translate(0px, ${125 * Math.E}px) scale(${scale})`)
})

test('zooming in stops at 3x', () => {
  render(diagram())

  fireEvent.wheel(viewport(), { deltaY: -100000, clientX: 0, clientY: 0 })

  expect(transform()).toMatch(/scale\(3\)$/)
})

test('zooming out stops at 0.2x', () => {
  render(diagram())

  fireEvent.wheel(viewport(), { deltaY: 100000, clientX: 0, clientY: 0 })

  expect(transform()).toMatch(/scale\(0\.2\)$/)
})

test('click targets keep their screen size: --zoom follows the scale', () => {
  render(diagram())

  fireEvent.click(button('Fill'))

  expect(canvas().style.getPropertyValue('--zoom')).toBe('0.5')
})

test('dragging pans the diagram', () => {
  render(diagram())

  drag({ x: 100, y: 100 }, { x: 60, y: 30 })

  expect(transform()).toBe('translate(60px, 155px) scale(0.25)')
})

test('a resize re-fits an untouched diagram', () => {
  render(diagram())

  viewportWidth = 2000
  act(() => resize?.())

  expect(transform()).toBe('translate(0px, 0px) scale(0.5)')
})

test('a resize keeps the place of a diagram the owner has panned', () => {
  render(diagram())
  drag({ x: 100, y: 100 }, { x: 60, y: 30 })

  viewportWidth = 2000
  act(() => resize?.())

  expect(transform()).toBe('translate(60px, 155px) scale(0.25)')
})

test('a resize keeps the zoom the owner chose with the wheel', () => {
  render(diagram())
  fireEvent.wheel(viewport(), { deltaY: -500, clientX: 0, clientY: 0 })
  const zoomed = transform()

  viewportWidth = 2000
  act(() => resize?.())

  expect(transform()).toBe(zoomed)
})

test('a new diagram starts fitted again, even after panning the old one', () => {
  const { rerender } = render(diagram())
  drag({ x: 100, y: 100 }, { x: 60, y: 30 })

  rerender(diagram(2000, 1000))

  expect(transform()).toBe('translate(0px, 0px) scale(0.5)')
})

test('pressing and moving on a view button does not pan', () => {
  render(diagram())

  drag({ x: 100, y: 100 }, { x: 60, y: 30 }, button('Fill'))

  expect(transform()).toBe('translate(0px, 125px) scale(0.25)')
})
