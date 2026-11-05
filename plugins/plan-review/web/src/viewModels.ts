// Pure functions from a plan to what the page shows. Components only render these.

import type { FileChange, Plan, Risk } from './plan'

export type TabId = 'criteria' | 'classes' | 'flows' | 'architecture' | 'files' | 'tests' | 'risks'

export interface Tab {
  id: TabId
  label: string
}

const CRITERIA_TAB: Tab = { id: 'criteria', label: 'Acceptance criteria' }

const TABS: Tab[] = [
  { id: 'classes', label: 'Classes' },
  { id: 'flows', label: 'Flows' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'files', label: 'Files' },
  { id: 'tests', label: 'Tests' },
  { id: 'risks', label: 'Risks & open questions' },
]

/** A run's label, as the CLI prints it: `#42` for an all-digit id, otherwise the id itself. */
export function issueLabel(id: string): string {
  return /^\d+$/.test(id) ? `#${id}` : id
}

export const criteriaOf = (plan: Plan): string[] => plan.acceptance_criteria ?? []

/** The element id of the criterion at `index` (0-based), as the plan numbers them from 1. */
export const criterionId = (index: number): string => `criterion:${index + 1}`

export function tabsFor(plan: Plan): Tab[] {
  const tabs = TABS.filter((tab) => tab.id !== 'architecture' || plan.architecture !== null)
  return criteriaOf(plan).length > 0 ? [CRITERIA_TAB, ...tabs] : tabs
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

/** Risks and questions apart, each in the architect's order (they may order by importance). */
export function risksByKind(plan: Plan): { risks: Risk[]; questions: Risk[] } {
  return {
    risks: plan.risks.filter((r) => r.kind === 'risk'),
    questions: plan.risks.filter((r) => r.kind === 'question'),
  }
}

function idsOnTab(plan: Plan): Record<TabId, string[]> {
  return {
    criteria: criteriaOf(plan).map((_, index) => criterionId(index)),
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
