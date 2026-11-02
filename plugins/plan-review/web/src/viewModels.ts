// Pure functions from a plan to what the page shows. Components only render these.

import type { FileChange, Plan, Risk } from './plan'

export type TabId = 'classes' | 'flows' | 'architecture' | 'files' | 'tests' | 'risks'

export interface Tab {
  id: TabId
  label: string
}

const TABS: Tab[] = [
  { id: 'classes', label: 'Classes' },
  { id: 'flows', label: 'Flows' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'files', label: 'Files' },
  { id: 'tests', label: 'Tests' },
  { id: 'risks', label: 'Risks & open questions' },
]

export function tabsFor(plan: Plan): Tab[] {
  return TABS.filter((tab) => tab.id !== 'architecture' || plan.architecture !== null)
}

const FILE_KINDS = ['code', 'test', 'config', 'doc'] as const

export interface FileGroup {
  kind: FileChange['kind']
  label: string
  files: FileChange[]
}

const FILE_KIND_LABELS: Record<FileChange['kind'], string> = {
  code: 'Code',
  test: 'Tests',
  config: 'Config',
  doc: 'Docs',
}

export function filesByKind(plan: Plan): FileGroup[] {
  return FILE_KINDS.map((kind) => ({
    kind,
    label: FILE_KIND_LABELS[kind],
    files: plan.files.filter((f) => f.kind === kind),
  })).filter((group) => group.files.length > 0)
}

const SEVERITY_RANK: Record<Risk['severity'], number> = { high: 0, medium: 1, low: 2 }

export function risksByKind(plan: Plan): { risks: Risk[]; questions: Risk[] } {
  // Array.prototype.sort is stable, so equal severities keep the plan's order.
  const sorted = [...plan.risks].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity],
  )
  return {
    risks: sorted.filter((r) => r.kind === 'risk'),
    questions: sorted.filter((r) => r.kind === 'question'),
  }
}

function idsOnTab(plan: Plan): Record<TabId, string[]> {
  return {
    classes: [
      ...plan.classes.flatMap((c) => [c.id, ...c.members.map((m) => m.id)]),
      ...plan.relations.map((r) => r.id),
    ],
    flows: plan.flows.flatMap((f) =>
      f.kind === 'sequence'
        ? [f.id, ...f.participants.map((p) => p.id), ...f.steps.map((s) => s.id)]
        : [f.id, ...f.nodes.map((n) => n.id), ...f.edges.map((e) => e.id)],
    ),
    architecture: plan.architecture
      ? [...plan.architecture.nodes, ...plan.architecture.edges].map((x) => x.id)
      : [],
    files: plan.files.map((f) => f.id),
    tests: plan.tests.map((t) => t.id),
    risks: plan.risks.map((r) => r.id),
  }
}

/** The tab an element is shown on, or null if the plan has no such element. */
export function tabOf(plan: Plan, elementId: string): TabId | null {
  const tabs = idsOnTab(plan)
  return (Object.keys(tabs) as TabId[]).find((tab) => tabs[tab].includes(elementId)) ?? null
}
