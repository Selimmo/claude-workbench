// A box-and-arrow diagram, independent of what it depicts: classes, architecture, flowcharts.

import type { Edge, Flowchart, Plan, Status } from './plan'

export interface DiagramRow {
  id: string
  text: string
  status: Status
}

export interface DiagramNode {
  id: string
  title: string
  subtitle: string | null
  status: Status
  rows: DiagramRow[]
}

export interface DiagramEdge {
  id: string
  source: string
  target: string
  label: string | null
  status: Status
}

export interface Diagram {
  nodes: DiagramNode[]
  edges: DiagramEdge[]
}

export function classDiagram(plan: Plan): Diagram {
  return {
    nodes: plan.classes.map((c) => ({
      id: c.id,
      title: c.name,
      subtitle: c.kind,
      status: c.status,
      rows: c.members.map((m) => ({ id: m.id, text: m.signature, status: m.status })),
    })),
    edges: plan.relations.map((r) => ({
      id: r.id,
      source: r.from,
      target: r.to,
      label: r.kind,
      status: r.status,
    })),
  }
}

function edgeOf(e: Edge): DiagramEdge {
  return { id: e.id, source: e.from, target: e.to, label: e.label ?? null, status: e.status }
}

export function architectureDiagram(plan: Plan): Diagram {
  const architecture = plan.architecture ?? { nodes: [], edges: [] }
  return {
    nodes: architecture.nodes.map((n) => ({
      id: n.id,
      title: n.name,
      subtitle: n.kind,
      status: n.status,
      rows: [],
    })),
    edges: architecture.edges.map(edgeOf),
  }
}

export function flowchartDiagram(flow: Flowchart): Diagram {
  return {
    nodes: flow.nodes.map((n) => ({
      id: n.id,
      title: n.name,
      subtitle: null,
      status: n.status,
      rows: [],
    })),
    edges: flow.edges.map(edgeOf),
  }
}
