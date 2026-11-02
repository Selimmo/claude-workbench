// Positions a Diagram with ELK. Sizes are estimated from text (monospace), so layout
// needs no DOM measuring and is deterministic in tests.

import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js'

import type { Diagram, DiagramEdge, DiagramNode } from './diagram'

export const CHAR_WIDTH = 7.8 // px per character at the diagram's 13px monospace font
export const PADDING = 12
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
}

export interface LaidEdge extends DiagramEdge {
  points: Point[]
  labelAt: Point | null
}

export interface LaidDiagram {
  nodes: LaidNode[]
  edges: LaidEdge[]
  width: number
  height: number
}

export function nodeSize(node: DiagramNode): { width: number; height: number } {
  // The header shows title and subtitle on one line, about two characters apart.
  const header = node.subtitle ? `${node.title}  ${node.subtitle}` : node.title
  const lines = [header, ...node.rows.map((r) => r.text)]
  const longest = Math.max(...lines.map((line) => line.length))
  return {
    width: Math.max(MIN_WIDTH, longest * CHAR_WIDTH + 2 * PADDING),
    height: HEADER_HEIGHT + node.rows.length * ROW_HEIGHT,
  }
}

const elk = new ELK()

export async function layoutDiagram(diagram: Diagram): Promise<LaidDiagram> {
  const input: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': '40',
      'elk.layered.spacing.nodeNodeBetweenLayers': '80',
      'elk.padding': '[top=20,left=20,bottom=20,right=20]',
    },
    children: diagram.nodes.map((node) => ({ id: node.id, ...nodeSize(node) })),
    edges: diagram.edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
      labels: edge.label
        ? [{ text: edge.label, width: edge.label.length * CHAR_WIDTH, height: 16 }]
        : [],
    })),
  }
  const graph = await elk.layout(input)

  const placed = new Map((graph.children ?? []).map((child) => [child.id, child]))
  const routed = new Map((graph.edges ?? []).map((edge) => [edge.id, edge]))
  return {
    nodes: diagram.nodes.map((node) => {
      const p = placed.get(node.id)
      return { ...node, x: p?.x ?? 0, y: p?.y ?? 0, width: p?.width ?? 0, height: p?.height ?? 0 }
    }),
    edges: diagram.edges.map((edge) => {
      const route = routed.get(edge.id)
      const section = route?.sections?.[0]
      const label = route?.labels?.[0]
      return {
        ...edge,
        points: section
          ? [section.startPoint, ...(section.bendPoints ?? []), section.endPoint]
          : [],
        labelAt:
          label?.x !== undefined && label.y !== undefined ? { x: label.x, y: label.y } : null,
      }
    }),
    width: graph.width ?? 0,
    height: graph.height ?? 0,
  }
}
