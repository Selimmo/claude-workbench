// Positions a Diagram with ELK. Boxes are sized from their text: measured in the real
// font in the browser (see measure.ts), estimated in tests.

import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js'

import {
  type Diagram,
  type DiagramEdge,
  type DiagramNode,
  LABEL_LINE_HEIGHT,
  ROOMY,
  type Spacing,
} from './diagram'
import { clipToOutline, flowNodeSize, tagSize, tagsCollide } from './flowShapes'
import { CHAR_WIDTH, TITLE_CHAR_WIDTH, type Measure, estimate, wrapLabel } from './measure'

export { CHAR_WIDTH, TITLE_CHAR_WIDTH, wrapLabel }
export const PADDING = 12
/** Between the title and the subtitle on a card's header line (at least the CSS gap). */
export const HEADER_GAP = 2 * CHAR_WIDTH
/** The card's left (3px) and right (1px) borders plus a row's 3px status stripe (styles.css). */
export const CARD_BORDERS = 7
export const HEADER_HEIGHT = 44
export const ROW_HEIGHT = 22
export const MIN_WIDTH = 140

export interface Point {
  x: number
  y: number
}

export interface LaidNode extends DiagramNode, Point {
  width: number
  height: number
  /** Flowchart steps: the text, wrapped to fit the shape. */
  lines?: string[]
}

export interface LaidEdge extends DiagramEdge {
  points: Point[]
  labelAt: Point | null
  /** The label, broken into lines that fit the spacing's label width. */
  labelLines: string[]
}

export interface LaidDiagram {
  nodes: LaidNode[]
  edges: LaidEdge[]
  width: number
  height: number
}

/** Measures the text on a card. */
export type CardMeasure = (text: string, kind: 'title' | 'subtitle' | 'row') => number

export function nodeSize(
  node: DiagramNode,
  measure: CardMeasure = estimate,
): { width: number; height: number } {
  // The header shows the title, then the subtitle after a gap.
  const header =
    measure(node.title, 'title') +
    (node.subtitle ? HEADER_GAP + measure(node.subtitle, 'subtitle') : 0)
  const rows = node.rows.map((r) => measure(r.text, 'row'))
  return {
    width: Math.max(MIN_WIDTH, Math.max(header, ...rows) + 2 * PADDING + CARD_BORDERS),
    height: HEADER_HEIGHT + node.rows.length * ROW_HEIGHT,
  }
}

const elk = new ELK()

interface Size {
  width: number
  height: number
}

/** Tags are placed next to the step they leave; if two would collide, or one would cover a step,
 * they go back to the middle of their line. */
type TagPlacement = 'TAIL' | 'CENTER'

export async function layoutDiagram(
  diagram: Diagram,
  direction: 'RIGHT' | 'DOWN' = 'RIGHT',
  measure: Measure = estimate,
  spacing: Spacing = ROOMY,
): Promise<LaidDiagram> {
  if (!diagram.nodes.some((n) => n.shape)) return layoutOnce(diagram, direction, measure, spacing)
  const tails = await layoutOnce(diagram, direction, measure, spacing, 'TAIL')
  if (!tagsCollideIn(tails, measure)) return tails
  return layoutOnce(diagram, direction, measure, spacing, 'CENTER')
}

function tagsCollideIn(laid: LaidDiagram, measure: Measure): boolean {
  const tags = laid.edges.flatMap((e) =>
    e.label && e.labelAt ? [{ ...e.labelAt, ...tagSize(e.label, measure) }] : [],
  )
  return tagsCollide(tags, laid.nodes)
}

async function layoutOnce(
  diagram: Diagram,
  direction: 'RIGHT' | 'DOWN',
  measure: Measure,
  spacing: Spacing,
  tags?: TagPlacement,
): Promise<LaidDiagram> {
  const sizes = new Map<string, Size & { lines?: string[] }>(
    diagram.nodes.map((n) => [n.id, n.shape ? flowNodeSize(n, measure) : nodeSize(n, measure)]),
  )
  const wrapped = new Map(
    diagram.edges.map((e) => [
      e.id,
      !e.label
        ? []
        : tags
          ? [e.label]
          : wrapLabel(e.label, spacing.labelWidth, (t) => measure(t, 'row')),
    ]),
  )
  const labelSize = (edge: DiagramEdge) =>
    tags && edge.label
      ? tagSize(edge.label, measure)
      : {
          width: Math.max(...(wrapped.get(edge.id) ?? []).map((l) => measure(l, 'row'))),
          height: LABEL_LINE_HEIGHT * (wrapped.get(edge.id)?.length ?? 1),
        }
  const input: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': direction,
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': String(spacing.nodeNode),
      'elk.layered.spacing.nodeNodeBetweenLayers': String(spacing.betweenLayers),
      'elk.padding': '[top=20,left=20,bottom=20,right=20]',
    },
    children: diagram.nodes.map((node) => ({
      id: node.id,
      width: sizes.get(node.id)?.width,
      height: sizes.get(node.id)?.height,
    })),
    edges: diagram.edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
      labels: edge.label
        ? [
            {
              text: edge.label,
              ...labelSize(edge),
              ...(tags ? { layoutOptions: { 'elk.edgeLabels.placement': tags } } : {}),
            },
          ]
        : [],
    })),
  }
  const graph = await elk.layout(input)

  const placed = new Map((graph.children ?? []).map((child) => [child.id, child]))
  const routed = new Map((graph.edges ?? []).map((edge) => [edge.id, edge]))
  const nodes: LaidNode[] = diagram.nodes.map((node) => {
    const p = placed.get(node.id)
    const lines = node.shape ? sizes.get(node.id)?.lines : undefined
    return {
      ...node,
      x: p?.x ?? 0,
      y: p?.y ?? 0,
      width: p?.width ?? 0,
      height: p?.height ?? 0,
      ...(lines ? { lines } : {}),
    }
  })
  const byId = new Map(nodes.map((n) => [n.id, n]))
  return {
    nodes,
    edges: diagram.edges.map((edge) => {
      const route = routed.get(edge.id)
      const section = route?.sections?.[0]
      const label = route?.labels?.[0]
      const points = section
        ? [section.startPoint, ...(section.bendPoints ?? []), section.endPoint]
        : []
      const from = byId.get(edge.source)
      const to = byId.get(edge.target)
      return {
        ...edge,
        points: from && to ? clipToOutline(points, from, to) : points,
        labelAt:
          label?.x !== undefined && label.y !== undefined ? { x: label.x, y: label.y } : null,
        labelLines: wrapped.get(edge.id) ?? [],
      }
    }),
    width: graph.width ?? 0,
    height: graph.height ?? 0,
  }
}
