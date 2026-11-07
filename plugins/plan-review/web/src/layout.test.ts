import {
  CHAR_WIDTH,
  HEADER_HEIGHT,
  MIN_WIDTH,
  PADDING,
  CARD_BORDERS,
  HEADER_GAP,
  ROW_HEIGHT,
  TITLE_CHAR_WIDTH,
  layoutDiagram,
  nodeSize,
  wrapLabel,
} from './layout'
import {
  COMPACT,
  LABEL_LINE_HEIGHT,
  ROOMY,
  architectureDiagram,
  type Diagram,
  type DiagramNode,
} from './diagram'
import example from '../../examples/plan.json'
import after56 from '../../examples/before-after/56/plan.json'
import type { Plan } from './plan'

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
    width: longest.length * CHAR_WIDTH + 2 * PADDING + CARD_BORDERS,
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
      2 * PADDING +
      CARD_BORDERS,
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

test('with a text measurer, a card is sized from the measured text, not estimates', () => {
  const measure = (text: string, kind: 'title' | 'subtitle' | 'row') =>
    text.length * { title: 30, subtitle: 5, row: 20 }[kind]
  const card = { ...node(['ab'], 'Wide'), subtitle: 'kind' }

  // Title 4×30 + gap + subtitle 4×5 = 148, wider than the row's 2×20.
  expect(nodeSize(card, measure).width).toBe(
    4 * 30 + HEADER_GAP + 4 * 5 + 2 * PADDING + CARD_BORDERS,
  )
})

test('layout sizes cards with the measurer it is given', async () => {
  const measure = (text: string) => text.length * 50
  const diagram: Diagram = { nodes: [{ ...node(['xyz'], 'ab'), id: 'a' }], edges: [] }

  const [a] = (await layoutDiagram(diagram, 'RIGHT', measure)).nodes

  expect(a.width).toBe(3 * 50 + 2 * PADDING + CARD_BORDERS)
})

test("a card's width also leaves room for its borders and the rows' status stripe", () => {
  const measure = (text: string) => text.length * 20

  expect(nodeSize(node(['abcdefghij'], 'T'), measure).width).toBe(200 + 2 * PADDING + CARD_BORDERS)
})

test("an arrow's label is measured, so the boxes either side make room for it", async () => {
  const measure = (text: string) => (text === 'a-long-label' ? 600 : 10)
  const diagram: Diagram = {
    nodes: [
      { ...node([]), id: 'a' },
      { ...node([]), id: 'b' },
    ],
    edges: [{ id: 'e', source: 'a', target: 'b', label: 'a-long-label', status: 'added' }],
  }

  const [a, b] = (await layoutDiagram(diagram, 'RIGHT', measure)).nodes

  expect(b.x - (a.x + a.width)).toBeGreaterThanOrEqual(600)
})

test('wrapLabel breaks a long label at spaces within the width', () => {
  const measure = (text: string) => text.length * 10

  const lines = wrapLabel('writes side, names and bases', 120, measure)

  expect(lines.length).toBeGreaterThan(1)
  for (const line of lines) expect(measure(line)).toBeLessThanOrEqual(120)
  expect(lines.join(' ')).toBe('writes side, names and bases')
  expect(wrapLabel('Supercalifragilistic word', 50, measure)).toEqual([
    'Supercalifragilistic',
    'word',
  ])
  expect(wrapLabel('runs', 120, measure)).toEqual(['runs'])
})

const longest = (laid: Awaited<ReturnType<typeof layoutDiagram>>) =>
  Math.max(
    ...laid.edges.map((e) =>
      e.points
        .slice(1)
        .reduce((sum, p, i) => sum + Math.hypot(p.x - e.points[i].x, p.y - e.points[i].y), 0),
    ),
  )

test.each([
  ['the #56 plan', after56],
  ['the example plan', example],
])('the compact spacing lays out the architecture of %s tighter', async (_, raw) => {
  const diagram = architectureDiagram(raw as Plan)

  const roomy = await layoutDiagram(diagram, 'RIGHT', undefined, ROOMY)
  const compact = await layoutDiagram(diagram, 'RIGHT', undefined, COMPACT)

  expect(compact.width).toBeLessThan(roomy.width)
  expect(longest(compact)).toBeLessThan(longest(roomy))
})

test('a long edge label is wrapped into lines', async () => {
  const diagram: Diagram = {
    nodes: [
      { ...node([]), id: 'a' },
      { ...node([]), id: 'b' },
    ],
    edges: [
      { id: 'e', source: 'a', target: 'b', label: 'one two three four five six', status: 'added' },
    ],
  }

  const [edge] = (await layoutDiagram(diagram, 'RIGHT', undefined, COMPACT)).edges

  expect(edge.labelLines.length).toBeGreaterThan(1)
  expect(edge.labelLines.join(' ')).toBe('one two three four five six')
})

test('the room an edge label takes between two boxes is that of its wrapped lines', async () => {
  const diagram: Diagram = {
    nodes: [
      { ...node([]), id: 'a' },
      { ...node([]), id: 'b' },
    ],
    edges: [
      { id: 'e', source: 'a', target: 'b', label: 'one two three four five six', status: 'added' },
    ],
  }

  const across = await layoutDiagram(diagram, 'RIGHT', undefined, COMPACT)
  const down = await layoutDiagram(diagram, 'DOWN', undefined, COMPACT)

  const [a, b] = across.nodes
  const widest = Math.max(...across.edges[0].labelLines.map((l) => l.length * CHAR_WIDTH))
  expect(b.x - (a.x + a.width) - 2 * COMPACT.betweenLayers).toBeCloseTo(widest)
  const [top, bottom] = down.nodes
  expect(bottom.y - (top.y + top.height) - 2 * COMPACT.betweenLayers).toBeCloseTo(
    down.edges[0].labelLines.length * LABEL_LINE_HEIGHT,
  )
})
