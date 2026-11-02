import {
  CHAR_WIDTH,
  HEADER_HEIGHT,
  MIN_WIDTH,
  PADDING,
  ROW_HEIGHT,
  TITLE_CHAR_WIDTH,
  layoutDiagram,
  nodeSize,
} from './layout'
import type { Diagram, DiagramNode } from './diagram'

const node = (rows: string[], title = 'T'): DiagramNode => ({
  id: 'n',
  title,
  subtitle: null,
  status: 'added',
  rows: rows.map((text, i) => ({ id: `r${i}`, text, status: 'added' })),
})

test('a node is as wide as its longest line and as tall as its rows', () => {
  const longest = 'next_level(given: int) -> HintLevel | None'

  expect(nodeSize(node(['a', longest]))).toEqual({
    width: longest.length * CHAR_WIDTH + 2 * PADDING,
    height: HEADER_HEIGHT + 2 * ROW_HEIGHT,
  })
})

test('a node is never narrower than the minimum', () => {
  expect(nodeSize(node([])).width).toBe(MIN_WIDTH)
})

test('layout positions every node and routes every edge', async () => {
  const diagram: Diagram = {
    nodes: [
      { ...node([]), id: 'a' },
      { ...node(['x']), id: 'b' },
    ],
    edges: [{ id: 'e', source: 'a', target: 'b', label: 'uses', status: 'added' }],
  }

  const laid = await layoutDiagram(diagram)

  expect(laid.nodes.map((n) => n.id)).toEqual(['a', 'b'])
  for (const n of laid.nodes)
    expect(n).toMatchObject({ x: expect.any(Number), y: expect.any(Number) })
  expect(laid.edges[0].points.length).toBeGreaterThanOrEqual(2)
  expect(laid.width).toBeGreaterThan(0)
  expect(laid.height).toBeGreaterThan(0)
})

test('the header line (bold title, then subtitle) is measured with the wider title font', () => {
  const header = { ...node([], 'hints_given < max_hints?'), subtitle: 'step' }

  expect(nodeSize(header).width).toBe(
    'hints_given < max_hints?'.length * TITLE_CHAR_WIDTH +
      ('step'.length + 2) * CHAR_WIDTH +
      2 * PADDING,
  )
})

test('layout can run top to bottom', async () => {
  const diagram: Diagram = {
    nodes: [
      { ...node([]), id: 'a' },
      { ...node([]), id: 'b' },
    ],
    edges: [{ id: 'e', source: 'a', target: 'b', label: null, status: 'added' }],
  }

  const [a, b] = (await layoutDiagram(diagram, 'DOWN')).nodes

  expect(b.y).toBeGreaterThan(a.y)
  expect(b.x).toBe(a.x)
})
