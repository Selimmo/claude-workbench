// The plan.json format, mirroring plan_review/plan/plan.py (see `plan-review schema`).

export type Status = 'added' | 'modified' | 'removed' | 'unchanged'

export type Side = 'front' | 'back'

export interface Member {
  id: string
  /** Absent in plans written before 0.1.12. */
  name?: string | null
  kind?: 'property' | 'method' | null
  signature: string
  note?: string | null
  status: Status
}

export interface PlanClass {
  id: string
  name: string
  kind: string
  /** Absent in plans written before 0.1.12, which are drawn in one diagram. */
  side?: Side | null
  bases?: string[]
  note?: string | null
  status: Status
  members: Member[]
}

export interface Edge {
  id: string
  from: string
  to: string
  status: Status
  label?: string | null
}

export interface Relation extends Edge {
  kind: string
}

export interface Node {
  id: string
  name: string
  status: Status
}

export interface SequenceFlow {
  id: string
  title: string
  kind: 'sequence'
  participants: Node[]
  steps: (Edge & { label: string })[]
}

export interface Flowchart {
  id: string
  title: string
  kind: 'flowchart'
  nodes: Node[]
  edges: Edge[]
}

export type Flow = SequenceFlow | Flowchart

export interface Component extends Node {
  kind: string
}

export interface Architecture {
  nodes: Component[]
  edges: Edge[]
}

export interface FileChange {
  id: string
  path: string
  kind: 'code' | 'test' | 'config' | 'doc'
  change: 'added' | 'modified' | 'removed'
  reason: string
}

export interface PlannedTest {
  id: string
  name: string
  target: string
  behaviour: string
}

export interface Risk {
  id: string
  kind: 'risk' | 'question'
  text: string
  severity: 'low' | 'medium' | 'high'
  mitigation?: string | null
}

export interface Plan {
  issue: { id: string; kind: 'issue' | 'prompt'; title: string; url?: string | null }
  summary: string
  /** Absent in a plan served as written; read it through `viewModels`, which defaults it to []. */
  acceptance_criteria?: string[]
  branch?: string | null
  classes: PlanClass[]
  relations: Relation[]
  flows: Flow[]
  architecture: Architecture | null
  files: FileChange[]
  tests: PlannedTest[]
  risks: Risk[]
}
