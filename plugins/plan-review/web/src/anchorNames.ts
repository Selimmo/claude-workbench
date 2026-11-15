// A readable name for the id a comment is attached to, built from the names in the plan.

import type { Plan } from './plan'
import { tabsFor } from './viewModels'

export interface AnchorName {
  /** The name as shown: cut with … when long. */
  short: string
  /** The whole name, for hovering. */
  full: string
  /** The raw id. */
  id: string
}

export const SHORT_LIMIT = 60

const BREADCRUMB = ' › '

/** The fallback for an id the plan has no element for: `flow:level/check` → `level › check`. */
export function tidyId(anchor: string): string {
  const colon = anchor.indexOf(':')
  if (colon < 0) return anchor
  const rest = anchor.slice(colon + 1)
  if (/^\d+$/.test(rest)) return `${anchor.slice(0, colon)} ${rest}`
  return rest.replace(/[/.]/g, BREADCRUMB)
}

function lineName(
  from: string,
  to: string,
  label: string | null | undefined,
  names: Map<string, string>,
) {
  const ends = `${names.get(from) ?? from} → ${names.get(to) ?? to}`
  return label ? `${ends} (${label})` : ends
}

/** The element's name, or null when the plan has no such element. */
function nameOf(plan: Plan, anchor: string): string | null {
  const fixed: Record<string, string> = { 'header:title': 'Title', 'header:summary': 'Summary' }
  if (anchor in fixed) return fixed[anchor]
  if (anchor.startsWith('tab:')) {
    const tab = tabsFor(plan).find((t) => `tab:${t.id}` === anchor)
    return tab ? `Tab${BREADCRUMB}${tab.label}` : null
  }
  const criterion = /^criterion:(\d+)$/.exec(anchor)
  if (criterion) {
    const text = plan.acceptance_criteria?.[Number(criterion[1]) - 1]
    return text === undefined ? null : `Criterion ${criterion[1]}${BREADCRUMB}${text}`
  }

  for (const cls of plan.classes) {
    if (cls.id === anchor) return cls.name
    const member = cls.members.find((m) => m.id === anchor)
    if (member) return `${cls.name}${BREADCRUMB}${member.name ?? member.signature}`
  }
  const classNames = new Map(plan.classes.map((c) => [c.id, c.name]))
  const relation = plan.relations.find((r) => r.id === anchor)
  if (relation) return lineName(relation.from, relation.to, null, classNames)

  for (const flow of plan.flows) {
    if (flow.id === anchor) return flow.title
    if (flow.kind === 'sequence') {
      const part = flow.participants.find((p) => p.id === anchor)
      if (part) return `${flow.title}${BREADCRUMB}${part.name}`
      const step = flow.steps.find((s) => s.id === anchor)
      if (step) return `${flow.title}${BREADCRUMB}${step.label}`
    } else {
      const node = flow.nodes.find((n) => n.id === anchor)
      if (node) return `${flow.title}${BREADCRUMB}${node.name}`
      const edge = flow.edges.find((e) => e.id === anchor)
      if (edge)
        return lineName(
          edge.from,
          edge.to,
          edge.label,
          new Map(flow.nodes.map((n) => [n.id, n.name])),
        )
    }
  }

  const arch = plan.architecture
  const box = arch?.nodes.find((n) => n.id === anchor)
  if (box) return box.name
  const line = arch?.edges.find((e) => e.id === anchor)
  if (arch && line)
    return lineName(line.from, line.to, line.label, new Map(arch.nodes.map((n) => [n.id, n.name])))

  const file = plan.files.find((f) => f.id === anchor)
  if (file) return file.path
  const test = plan.tests.find((t) => t.id === anchor)
  if (test) return `Test${BREADCRUMB}${test.name}`
  const risk = plan.risks.find((r) => r.id === anchor)
  if (risk) return `${risk.kind === 'risk' ? 'Risk' : 'Question'}${BREADCRUMB}${risk.text}`
  return null
}

export function anchorName(plan: Plan, anchor: string): AnchorName {
  const full = nameOf(plan, anchor) ?? tidyId(anchor)
  const short = full.length > SHORT_LIMIT ? `${full.slice(0, SHORT_LIMIT)}…` : full
  return { short, full, id: anchor }
}
