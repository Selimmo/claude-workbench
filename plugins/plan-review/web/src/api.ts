import type { Plan } from './plan'
import type { Thread } from './threads'

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

async function send(url: string, body?: object): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const { errors } = (await response.json()) as { errors: string[] }
    throw new Error(errors.join('\n'))
  }
}

export async function fetchThreads(): Promise<Thread[]> {
  // Threads are secondary to the plan: if they can't be loaded, show none rather than fail.
  try {
    const response = await fetch('/api/threads')
    return ((await response.json()) as { threads?: Thread[] }).threads ?? []
  } catch {
    return []
  }
}

export const createThread = (anchor: string, text: string) => send('/api/threads', { anchor, text })
export const replyTo = (id: string, text: string) => send(`/api/threads/${id}/replies`, { text })
export const setResolved = (id: string, resolved: boolean) =>
  send(`/api/threads/${id}/${resolved ? 'resolve' : 'reopen'}`)

export async function fetchApproval(): Promise<boolean> {
  try {
    const response = await fetch('/api/approve')
    return ((await response.json()) as { approved: boolean }).approved === true
  } catch {
    return false
  }
}

export const approve = () => send('/api/approve')
