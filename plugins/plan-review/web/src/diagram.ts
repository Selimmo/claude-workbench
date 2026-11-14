// A box-and-arrow diagram, independent of what it depicts: classes, architecture, flowcharts.

import type { Edge, Flowchart, Member, Plan, PlanClass, Side, Status } from './plan'

export interface DiagramRow {
  id: string
  text: string
  status: Status
  /** A colour mark beside the name: this plan adds, changes or removes it. */
  marked?: boolean
}

export interface DiagramNode {
  id: string
  title: string
  subtitle: string | null
  status: Status
  rows: DiagramRow[]
  /** An unchanged class drawn only because it is linked to a changed one. */
  faded?: boolean
  /** A click opens the details popup, not the comment box. */
  details?: boolean
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

/** The gaps ELK leaves around boxes. Here, not in layout.ts, so the main bundle does not pull in ELK. */
export interface Spacing {
  nodeNode: number
  betweenLayers: number
  /** Edge labels wrap at about this many pixels. */
  labelWidth: number
}

export const LABEL_LINE_HEIGHT = 16

export const ROOMY: Spacing = { nodeNode: 40, betweenLayers: 80, labelWidth: Infinity }
export const COMPACT: Spacing = { nodeNode: 24, betweenLayers: 40, labelWidth: 160 }

/** Plans written before 0.1.12 have no sides and are drawn as one diagram. */
export function currentShape(plan: Plan): boolean {
  return plan.classes.length > 0 && plan.classes.every((c) => c.side)
}

export function classSides(plan: Plan): Side[] {
  return (['front', 'back'] as const).filter((side) => plan.classes.some((c) => c.side === side))
}

export function sideOf(plan: Plan, id: string): Side | null {
  const from = plan.relations.find((r) => r.id === id)?.from ?? id
  const owner = plan.classes.find((c) => c.id === from || c.members.some((m) => m.id === from))
  return owner?.side ?? null
}

const isChanged = (c: PlanClass) =>
  c.status !== 'unchanged' || c.members.some((m) => m.status !== 'unchanged')

export function sideDiagram(plan: Plan, side: Side): Diagram {
  const onSide = plan.classes.filter((c) => c.side === side)
  const changed = new Set(onSide.filter(isChanged).map((c) => c.id))
  const linked = new Set<string>()
  for (const r of plan.relations) {
    if (changed.has(r.from)) linked.add(r.to)
    if (changed.has(r.to)) linked.add(r.from)
  }
  const drawn = onSide.filter((c) => changed.has(c.id) || linked.has(c.id))
  const ids = new Set(drawn.map((c) => c.id))
  return {
    nodes: drawn.map((c) => ({
      id: c.id,
      title: c.bases?.length ? `${c.name}: ${c.bases.join(', ')}` : c.name,
      subtitle: c.kind,
      status: c.status,
      faded: !changed.has(c.id),
      details: true,
      rows: [
        ...c.members.filter((m) => m.kind !== 'method'),
        ...c.members.filter((m) => m.kind === 'method'),
      ].map((m) => ({
        id: m.id,
        text: m.name ? (m.kind === 'method' ? `${m.name}()` : m.name) : m.signature,
        status: m.status,
        marked: m.status !== 'unchanged',
      })),
    })),
    edges: plan.relations
      .filter((r) => ids.has(r.from) && ids.has(r.to))
      .map((r) => ({ id: r.id, source: r.from, target: r.to, label: r.kind, status: r.status })),
  }
}

export interface MemberLine {
  id: string
  /** The short name; for a member from a plan before 0.1.12, the whole signature. */
  name: string
  /** Fields only: what follows the name in the signature. */
  type: string | null
  /** Methods only: the full signature shown when the line opens. */
  signature: string | null
  note: string | null
}

export interface MemberGroup {
  status: 'added' | 'modified' | 'removed'
  members: MemberLine[]
}

export interface ClassDetails {
  id: string
  /** The dialog's accessible name: `Name: Base, Base`. */
  title: string
  name: string
  bases: string[]
  kind: string
  status: Status
  note: string | null
  groups: MemberGroup[]
  unchanged: MemberLine[]
}

export function memberLine(m: Member): MemberLine {
  const note = m.note ?? null
  if (!m.name) return { id: m.id, name: m.signature, type: null, signature: null, note }
  if (m.kind === 'method')
    return { id: m.id, name: m.name, type: null, signature: m.signature, note }
  const rest = m.signature.startsWith(m.name) ? m.signature.slice(m.name.length) : ''
  // The name must end there: `count` is not the start of `counter: int`.
  const type = /^\w/.test(rest) ? null : rest || null
  return { id: m.id, name: m.name, type, signature: null, note }
}

const GROUP_ORDER = ['added', 'modified', 'removed'] as const

export function classDetails(plan: Plan, id: string): ClassDetails | null {
  const c = plan.classes.find((x) => x.id === id)
  if (!c) return null
  const fieldsFirst = (members: Member[]) => [
    ...members.filter((m) => m.kind !== 'method'),
    ...members.filter((m) => m.kind === 'method'),
  ]
  const withStatus = (status: Status) => fieldsFirst(c.members.filter((m) => m.status === status))
  const bases = c.bases ?? []
  return {
    id: c.id,
    title: bases.length ? `${c.name}: ${bases.join(', ')}` : c.name,
    name: c.name,
    bases,
    kind: c.kind,
    status: c.status,
    note: c.note ?? null,
    groups: GROUP_ORDER.map((status) => ({
      status,
      members: withStatus(status).map(memberLine),
    })).filter((g) => g.members.length > 0),
    unchanged: withStatus('unchanged').map(memberLine),
  }
}
