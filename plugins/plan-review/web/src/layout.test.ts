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
  classDiagram,
  flowchartDiagram,
  type Diagram,
  type DiagramNode,
} from './diagram'
import example from '../../examples/plan.json'
import type { Plan } from './plan'
import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js'
import { flowNodeSize, tagSize } from './flowShapes'
import { estimate } from './measure'

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

test.each([['the example plan', example]])(
  'the compact spacing lays out the architecture of %s tighter',
  async (_, raw) => {
    const diagram = architectureDiagram(raw as Plan)

    const roomy = await layoutDiagram(diagram, 'RIGHT', undefined, ROOMY)
    const compact = await layoutDiagram(diagram, 'RIGHT', undefined, COMPACT)

    expect(compact.width).toBeLessThan(roomy.width)
    expect(longest(compact)).toBeLessThan(longest(roomy))
  },
)

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

test('a long edge label breaks into the exact lines that fit the label width', async () => {
  const diagram: Diagram = {
    nodes: [
      { ...node([]), id: 'a' },
      { ...node([]), id: 'b' },
    ],
    edges: [
      { id: 'e', source: 'a', target: 'b', label: 'one two three four five six', status: 'added' },
    ],
  }

  const [edge] = (await layoutDiagram(diagram, 'RIGHT', estimate, COMPACT)).edges

  expect(edge.labelLines).toEqual(['one two three four', 'five six'])
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

const chart = (plan: Plan, id = 'flow:level') => {
  const flow = plan.flows.find((f) => f.id === id)
  if (flow?.kind !== 'flowchart') throw new Error(`no flowchart ${id}`)
  return flowchartDiagram(flow)
}

interface Box {
  x: number
  y: number
  width: number
  height: number
}
const overlap = (a: Box, b: Box) =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height

test('flowchart steps are sized by their shape, and keep their wrapped lines', async () => {
  const diagram = chart(example as Plan)

  const laid = await layoutDiagram(diagram, 'DOWN', estimate)

  for (const n of laid.nodes) {
    const { width, height, lines } = flowNodeSize(n, estimate)
    expect([n.width, n.height, n.lines]).toEqual([width, height, lines])
  }
})

test('a flowchart is laid out with room for its tags: none overlap each other or a step', async () => {
  const demo = (await import('../../examples/demo/plan.json')).default as Plan
  for (const plan of [example as Plan, demo]) {
    const laid = await layoutDiagram(chart(plan), 'DOWN', estimate)

    const tags = laid.edges.flatMap((e) =>
      e.label && e.labelAt ? [{ ...e.labelAt, ...tagSize(e.label, estimate) }] : [],
    )
    expect(tags.length).toBeGreaterThanOrEqual(2)
    tags.forEach((tag, i) => {
      for (const other of tags.slice(i + 1)) expect(overlap(tag, other)).toBe(false)
      for (const n of laid.nodes) expect(overlap(tag, n)).toBe(false)
    })
  }
})

test('the lines leaving a decision start on the diamond, not in its empty corners', async () => {
  const laid = await layoutDiagram(chart(example as Plan), 'DOWN', estimate)
  const decision = laid.nodes.find((n) => n.shape === 'decision')
  if (!decision) throw new Error('the example has a decision')

  const leaving = laid.edges.filter((e) => e.source === decision.id)

  expect(leaving.length).toBe(2)
  for (const e of leaving) {
    const { x, y } = e.points[0]
    const reach =
      Math.abs(x - (decision.x + decision.width / 2)) / (decision.width / 2) +
      Math.abs(y - (decision.y + decision.height / 2)) / (decision.height / 2)
    expect(reach).toBeCloseTo(1)
  }
})

test('a tag is laid out as one line of its text', async () => {
  const laid = await layoutDiagram(chart(example as Plan), 'DOWN', estimate)

  expect(laid.edges.find((e) => e.label === 'yes')?.labelLines).toEqual(['yes'])
})

test('a diagram without shapes is laid out as before: card sizes, no wrapped lines', async () => {
  const diagram = classDiagram(example as Plan)

  const laid = await layoutDiagram(diagram, 'RIGHT', estimate)

  for (const n of laid.nodes) {
    expect({ width: n.width, height: n.height }).toEqual(nodeSize(n, estimate))
    expect(n).not.toHaveProperty('lines')
  }
})

const labelsOf = (graph: ElkNode) => graph.edges?.flatMap((e) => e.labels ?? []) ?? []

const placementOf = (graph: ElkNode) =>
  graph.edges
    ?.flatMap((e) => e.labels ?? [])
    .map((l) => l.layoutOptions?.['elk.edgeLabels.placement'])[0]

/** Runs ELK for real and records how its tags were placed; `pile` then moves a TAIL layout's tags. */
function watchElk(
  placed: (string | undefined)[],
  pile?: { x: number; y: number },
  sizes: { width?: number; height?: number }[] = [],
) {
  const real = ELK.prototype.layout as (this: unknown, ...args: unknown[]) => Promise<ElkNode>
  vi.spyOn(ELK.prototype, 'layout').mockImplementation(async function (
    this: unknown,
    ...args: unknown[]
  ) {
    const result = await real.apply(this, args)
    const placement = placementOf(args[0] as ElkNode)
    placed.push(placement)
    sizes.push(...labelsOf(args[0] as ElkNode).map(({ width, height }) => ({ width, height })))
    if (pile && placement === 'TAIL')
      for (const edge of result.edges ?? [])
        for (const label of edge.labels ?? []) Object.assign(label, pile)
    return result
  })
}

afterEach(() => vi.restoreAllMocks())

test('tags are asked to sit next to the step they leave, and one layout is enough when they fit', async () => {
  const placed: (string | undefined)[] = []
  watchElk(placed)

  await layoutDiagram(chart(example as Plan), 'DOWN', estimate)

  expect(placed).toEqual(['TAIL'])
})

test.each([
  ['over each other', { x: 5000, y: 5000 }],
  ['over a step', { x: 0, y: 0 }],
])('when tags collide %s, they go back to the middle of their lines', async (_, pile) => {
  const placed: (string | undefined)[] = []
  watchElk(placed, pile)

  const laid = await layoutDiagram(chart(example as Plan), 'DOWN', estimate)

  expect(placed).toEqual(['TAIL', 'CENTER'])
  for (const e of laid.edges) if (e.labelAt) expect(e.labelAt).not.toEqual(pile)
})

test('a diagram without shapes asks ELK for no tag placement, once', async () => {
  const placed: (string | undefined)[] = []
  watchElk(placed)

  await layoutDiagram(classDiagram(example as Plan), 'RIGHT', estimate)

  expect(placed).toEqual([undefined])
})

test('the room ELK keeps for each tag is the size of the tag', async () => {
  const sizes: { width?: number; height?: number }[] = []
  watchElk([], undefined, sizes)
  const diagram = chart(example as Plan)

  await layoutDiagram(diagram, 'DOWN', estimate)

  expect(sizes).toEqual(diagram.edges.flatMap((e) => (e.label ? [tagSize(e.label, estimate)] : [])))
})

test('a diagram where only some steps have a shape still gets tags beside their steps', async () => {
  const placed: (string | undefined)[] = []
  watchElk(placed)
  const diagram = chart(example as Plan)
  const mixed = {
    ...diagram,
    nodes: diagram.nodes.map((n, i) => (i === 0 ? { ...n, shape: undefined } : n)),
  }

  const laid = await layoutDiagram(mixed, 'DOWN', estimate)

  expect(placed).toEqual(['TAIL'])
  expect(laid.nodes[0]).toMatchObject(nodeSize(mixed.nodes[0], estimate))
  expect(laid.nodes[1]).toMatchObject(flowNodeSize(mixed.nodes[1], estimate))
})
