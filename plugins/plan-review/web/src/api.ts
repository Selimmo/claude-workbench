import type { AnswerDraft, Grill } from './grill'
import type { Plan } from './plan'
import type { ClaudeStatus, Draft, LastEvent, Thread } from './threads'

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

async function send(url: string, body?: object, method = 'POST'): Promise<unknown> {
  const response = await fetch(url, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const { errors } = (await response.json()) as { errors: string[] }
    throw new Error(errors.join('\n'))
  }
  return response.status === 204 ? null : response.json()
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

export async function fetchDrafts(): Promise<Draft[]> {
  // Like threads: if drafts can't be loaded (e.g. an older server), show none.
  try {
    const response = await fetch('/api/drafts')
    return ((await response.json()) as { drafts?: Draft[] }).drafts ?? []
  } catch {
    return []
  }
}

/** Comments and replies are drafts first; nothing reaches Claude until submitReview. */
export const draftComment = async (anchor: string, text: string) =>
  void (await send('/api/drafts', { anchor, text }))
export const draftReply = async (threadId: string, text: string) =>
  void (await send('/api/drafts', { thread_id: threadId, text }))
export const editDraft = async (id: string, text: string) =>
  void (await send(`/api/drafts/${id}`, { text }, 'PUT'))
export const discardDraft = async (id: string) =>
  void (await send(`/api/drafts/${id}`, undefined, 'DELETE'))
/** Submits every draft; returns how many comments the server sent to Claude. */
export async function submitReview(): Promise<number> {
  const { comments } = (await send('/api/review')) as { comments: unknown[] }
  return comments.length
}
export const setResolved = async (id: string, resolved: boolean) =>
  void (await send(`/api/threads/${id}/${resolved ? 'resolve' : 'reopen'}`))

export async function fetchStatus(): Promise<ClaudeStatus | null> {
  try {
    const response = await fetch('/api/status')
    return ((await response.json()) as { status?: ClaudeStatus | null }).status ?? null
  } catch {
    return null
  }
}

export async function fetchApproval(): Promise<boolean> {
  try {
    const response = await fetch('/api/approve')
    return ((await response.json()) as { approved: boolean }).approved === true
  } catch {
    return false
  }
}

export const approve = async () => void (await send('/api/approve'))

export async function fetchLastEvent(): Promise<LastEvent | null> {
  // Secondary, like status: an older server has no such route, so show nothing.
  try {
    const response = await fetch('/api/last-event')
    return ((await response.json()) as { last_event?: LastEvent | null }).last_event ?? null
  } catch {
    return null
  }
}

/** Sends the last event to Claude again, unless Claude already answered it. */
export const resend = async () =>
  (await send('/api/resend')) as { sent: true } | { sent: false; status: ClaudeStatus }

export type GrillResult = { ok: true; grill: Grill } | { ok: false; errors: string[] }

/** Null when there is no grill yet (or no server): the page then has nothing to show. */
export async function fetchGrill(): Promise<GrillResult | null> {
  try {
    const response = await fetch('/api/grill')
    if (response.ok) return { ok: true, grill: (await response.json()) as Grill }
    if (response.status !== 422) return null
    return { ok: false, errors: ((await response.json()) as { errors: string[] }).errors }
  } catch {
    return null
  }
}

export async function fetchGrillDrafts(): Promise<Record<string, AnswerDraft>> {
  try {
    const response = await fetch('/api/grill/drafts')
    return ((await response.json()) as { drafts?: Record<string, AnswerDraft> }).drafts ?? {}
  } catch {
    return {}
  }
}

export const saveGrillDraft = async (questionId: string, draft: AnswerDraft) =>
  void (await send(`/api/grill/drafts/${questionId}`, draft, 'PUT'))
export const discardGrillDraft = async (questionId: string) =>
  void (await send(`/api/grill/drafts/${questionId}`, undefined, 'DELETE'))
/** Records every draft as an answer and tells Claude. */
export const submitGrill = async () => void (await send('/api/grill/submit'))

export const confirmGrill = async () => void (await send('/api/grill/confirm'))
export const reopenGrill = async (text: string) => void (await send('/api/grill/reopen', { text }))
