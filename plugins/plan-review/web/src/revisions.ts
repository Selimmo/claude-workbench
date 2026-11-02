// What changed between two versions of a plan, element by element.

import type { Plan } from './plan'

/** Each element's own content (a class without its members, a flow without its steps). */
function elements(plan: Plan): Map<string, string> {
  const map = new Map<string, string>()
  const put = (id: string, value: unknown) => map.set(id, JSON.stringify(value))
  for (const { members, ...cls } of plan.classes) {
    put(cls.id, cls)
    for (const m of members) put(m.id, m)
  }
  for (const r of plan.relations) put(r.id, r)
  for (const flow of plan.flows) {
    put(flow.id, { title: flow.title, kind: flow.kind })
    const parts =
      flow.kind === 'sequence'
        ? [...flow.participants, ...flow.steps]
        : [...flow.nodes, ...flow.edges]
    for (const part of parts) put(part.id, part)
  }
  for (const x of [...(plan.architecture?.nodes ?? []), ...(plan.architecture?.edges ?? [])])
    put(x.id, x)
  for (const x of [...plan.files, ...plan.tests, ...plan.risks]) put(x.id, x)
  return map
}

/** Ids of elements that are new in `next`, or whose content differs from `previous`. */
export function changedIds(previous: Plan, next: Plan): Set<string> {
  const before = elements(previous)
  const changed = new Set<string>()
  for (const [id, value] of elements(next)) if (before.get(id) !== value) changed.add(id)
  return changed
}
