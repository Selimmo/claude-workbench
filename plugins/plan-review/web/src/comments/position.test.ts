import { spotOf } from './position'

const box = (left: number, top: number, right: number, bottom: number) =>
  ({ left, top, right, bottom }) as DOMRect

test("a spot is the element's top-right corner", () => {
  expect(spotOf(box(10, 20, 110, 60), null)).toEqual({ top: 20, left: 110 })
})

test('an element panned out of its diagram has no spot, so its pin does not float elsewhere', () => {
  const viewport = box(0, 100, 800, 600)

  expect(spotOf(box(10, 200, 110, 260), viewport)).toEqual({ top: 200, left: 110 })
  expect(spotOf(box(900, 200, 1000, 260), viewport)).toBeNull()
  expect(spotOf(box(10, 40, 110, 80), viewport)).toBeNull()
})
