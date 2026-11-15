import { render, screen } from '@testing-library/react'

import { COMPACT, type Diagram, LABEL_LINE_HEIGHT } from './diagram'
import { DiagramView } from './DiagramView'
import { FLOW_LINE_HEIGHT, tagSize } from './flowShapes'
import { type LaidDiagram, layoutDiagram } from './layout'
import { estimate } from './measure'

const step = (
  id: string,
  title: string,
  shape: 'start' | 'decision' | 'action',
): Diagram['nodes'][number] => ({
  id,
  title,
  subtitle: null,
  status: 'added',
  rows: [],
  shape,
})

const DIAGRAM: Diagram = {
  nodes: [
    step('a', 'Begin', 'start'),
    step('b', 'Is this a rather long question that wraps onto several lines?', 'decision'),
    step('c', 'Do it', 'action'),
  ],
  edges: [
    { id: 'e1', source: 'a', target: 'b', label: null, status: 'added', main: true },
    { id: 'e2', source: 'b', target: 'c', label: 'yes', status: 'added', main: false },
  ],
}

const num = (el: Element | null, name: string) => Number(el?.getAttribute(name))

async function drawn(diagram: Diagram, props: Partial<Parameters<typeof DiagramView>[0]> = {}) {
  const { container } = render(
    <DiagramView diagram={diagram} empty="Nothing." direction="DOWN" {...props} />,
  )
  await vi.waitFor(() => expect(container.querySelector('path.line')).not.toBeNull())
  const laid = await layoutDiagram(diagram, 'DOWN', estimate, props.spacing)
  return { container, laid }
}

const at = (laid: LaidDiagram, id: string) => {
  const found = laid.nodes.find((n) => n.id === id)
  if (!found) throw new Error(`no node ${id}`)
  return found
}

test('a decision is a diamond through the middle of its four sides, its text centred on several lines', async () => {
  const { container, laid } = await drawn(DIAGRAM, { look: 'flow' })
  const node = at(laid, 'b')
  const cx = node.x + node.width / 2
  const cy = node.y + node.height / 2

  const g = container.querySelector('[data-element-id="b"]')
  expect(g?.querySelector('polygon')?.getAttribute('points')).toBe(
    `${cx},${node.y} ${node.x + node.width},${cy} ${cx},${node.y + node.height} ${node.x},${cy}`,
  )
  const text = g?.querySelector('text')
  const lines = [...(text?.querySelectorAll('tspan') ?? [])]
  expect(lines.length).toBeGreaterThan(1)
  expect(lines.map((l) => l.textContent).join(' ')).toBe(DIAGRAM.nodes[1].title)
  expect(num(text ?? null, 'x')).toBe(cx)
  expect(num(text ?? null, 'y')).toBe(cy - ((lines.length - 1) * FLOW_LINE_HEIGHT) / 2)
  lines.forEach((line, i) => {
    expect(num(line, 'x')).toBe(cx)
    expect(num(line, 'dy')).toBe(i === 0 ? 0 : FLOW_LINE_HEIGHT)
  })
})

test('an action or a pill is a rounded rectangle on its laid-out box, its text in the middle', async () => {
  const { container, laid } = await drawn(DIAGRAM, { look: 'flow' })

  for (const [id, radius] of [
    ['a', (h: number) => h / 2],
    ['c', () => 8],
  ] as const) {
    const node = at(laid, id)
    const g = container.querySelector(`[data-element-id="${id}"]`)
    const rect = g?.querySelector('rect.shape')
    expect([num(rect ?? null, 'x'), num(rect ?? null, 'y')]).toEqual([node.x, node.y])
    expect([num(rect ?? null, 'width'), num(rect ?? null, 'height')]).toEqual([
      node.width,
      node.height,
    ])
    expect(num(rect ?? null, 'rx')).toBe(radius(node.height))
    const text = g?.querySelector('text')
    expect([num(text ?? null, 'x'), num(text ?? null, 'y')]).toEqual([
      node.x + node.width / 2,
      node.y + node.height / 2,
    ])
  }
})

test("a tag is drawn at its label's spot, the text in its middle; a line is a path through its points", async () => {
  const { container, laid } = await drawn(DIAGRAM, { look: 'flow' })
  const edge = laid.edges.find((e) => e.id === 'e2')
  if (!edge?.labelAt) throw new Error('the yes line has a tag spot')
  const size = tagSize('yes', estimate)

  const tag = container.querySelector('[data-element-id="e2"] g.tag')
  const rect = tag?.querySelector('rect')
  expect([num(rect ?? null, 'x'), num(rect ?? null, 'y')]).toEqual([edge.labelAt.x, edge.labelAt.y])
  expect([num(rect ?? null, 'width'), num(rect ?? null, 'height')]).toEqual([
    size.width,
    size.height,
  ])
  const text = tag?.querySelector('text')
  expect([num(text ?? null, 'x'), num(text ?? null, 'y')]).toEqual([
    edge.labelAt.x + size.width / 2,
    edge.labelAt.y + size.height / 2,
  ])
  const expected = edge.points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
  expect(container.querySelector('[data-element-id="e2"] path.line')?.getAttribute('d')).toBe(
    expected,
  )
  expect(container.querySelector('[data-element-id="e1"] g.tag')).toBeNull()
  // the text is only in the tag, not drawn a second time as plain text
  expect(container.querySelector('[data-element-id="e2"] > text')).toBeNull()
})

test('with the cards look, line text is drawn plain at the label spot, one tspan per wrapped line', async () => {
  const cards: Diagram = {
    nodes: [
      { ...step('a', 'A', 'action'), shape: undefined },
      { ...step('b', 'B', 'action'), shape: undefined },
    ],
    edges: [
      {
        id: 'e',
        source: 'a',
        target: 'b',
        label: 'one two three four five six',
        status: 'added',
      },
    ],
  }
  const { container, laid } = await drawn(cards, { look: 'cards', spacing: COMPACT })
  const edge = laid.edges[0]
  if (!edge.labelAt) throw new Error('the line has a label spot')

  const text = container.querySelector('[data-element-id="e"] > text')
  const lines = [...(text?.querySelectorAll('tspan') ?? [])]
  expect(lines.length).toBeGreaterThan(1)
  expect(num(text ?? null, 'x')).toBe(edge.labelAt.x)
  expect(num(text ?? null, 'y')).toBe(edge.labelAt.y + 12)
  lines.forEach((line, i) => {
    expect(num(line, 'x')).toBe(edge.labelAt?.x)
    expect(num(line, 'dy')).toBe(i === 0 ? 0 : LABEL_LINE_HEIGHT)
  })
  expect(container.querySelector('g.tag, .flow-node')).toBeNull()
  expect(container.querySelectorAll('.card')).toHaveLength(2)
})

test('in the flow look a node with no shape still shows its title, on one line', async () => {
  const plain: Diagram = {
    nodes: [{ ...step('a', 'Plain title', 'action'), shape: undefined }],
    edges: [],
  }

  const { container } = render(
    <DiagramView diagram={plain} empty="Nothing." look="flow" direction="DOWN" />,
  )

  await vi.waitFor(() => expect(container.querySelector('.flow-node')).not.toBeNull())
  const tspans = container.querySelectorAll('.flow-node tspan')
  expect([...tspans].map((t) => t.textContent)).toEqual(['Plain title'])
})

test('the cards look is the default', async () => {
  const boxes: Diagram = {
    nodes: [
      { ...step('a', 'A', 'action'), shape: undefined },
      { ...step('b', 'B', 'action'), shape: undefined },
    ],
    edges: [{ id: 'e', source: 'a', target: 'b', label: null, status: 'added' }],
  }

  const { container } = await drawn(boxes)

  expect(container.querySelectorAll('.card')).toHaveLength(2)
  expect(container.querySelector('.flow-node')).toBeNull()
})

test('an empty diagram says so', () => {
  render(<DiagramView diagram={{ nodes: [], edges: [] }} empty="Nothing to draw." />)

  expect(screen.getByText('Nothing to draw.')).toBeInTheDocument()
})
