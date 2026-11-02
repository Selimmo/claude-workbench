import type { Plan } from './plan'

export type PlanResult = { ok: true; plan: Plan } | { ok: false; errors: string[] }

export async function fetchPlan(): Promise<PlanResult> {
  let response: Response
  try {
    response = await fetch('/api/plan')
  } catch {
    return {
      ok: false,
      errors: ["Can't reach the plan-review server. Is `plan-review serve` still running?"],
    }
  }
  const body: unknown = await response.json()
  if (response.ok) return { ok: true, plan: body as Plan }
  return { ok: false, errors: (body as { errors: string[] }).errors }
}
