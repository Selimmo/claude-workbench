import type { AnswerDraft, Grill } from './grill'
import type { Plan } from './plan'
import type { ClaudeStatus, Draft, LastEvent, Thread } from './threads'

export type PlanResult =
  { ok: true; plan: Plan } | { ok: false; errors: string[]; missing: boolean; broken: boolean }

/** A secondary file's content, with the lines naming it when the server says it is broken. */
export interface Part<T> {
  value: T
  errors: string[]
}

/** No server, no such route or no file: the empty value and no errors; a 422 says what is broken. */
/** The server's `errors` lines, or none for a body that has no such list. */
function errorLines(body: unknown): string[] {
  const errors = (body as { errors?: unknown } | null)?.errors
  return Array.isArray(errors) ? (errors as string[]) : []
}

async function fetchPart<T>(
  url: string,
  pick: (body: unknown) => T | undefined,
  empty: T,
): Promise<Part<T>> {
  try {
    const response = await fetch(url)
    const body: unknown = await response.json()
    if (response.status === 422) return { value: empty, errors: errorLines(body) }
    return { value: pick(body) ?? empty, errors: [] }
  } catch {
    return { value: empty, errors: [] }
  }
}

export async function fetchPlan(): Promise<PlanResult> {
  let response: Response
  try {
    response = await fetch('/api/plan')
  } catch {
    return {
      ok: false,
      errors: ["Can't reach the plan-review server. Is `plan-review serve` still running?"],
      missing: false,
      broken: false,
    }
  }
  const body: unknown = await response.json()
  if (response.ok) return { ok: true, plan: body as Plan }
  return {
    ok: false,
    errors: errorLines(body),
    missing: response.status === 404,
    broken: response.status === 422,
  }
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

// Threads are secondary to the plan: if they can't be loaded, show none rather than fail.
export const fetchThreads = (): Promise<Part<Thread[]>> =>
  fetchPart('/api/threads', (body) => (body as { threads?: Thread[] }).threads, [])

// Like threads: if drafts can't be loaded (e.g. an older server), show none.
export const fetchDrafts = (): Promise<Part<Draft[]>> =>
  fetchPart('/api/drafts', (body) => (body as { drafts?: Draft[] }).drafts, [])

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

export const fetchStatus = (): Promise<Part<ClaudeStatus | null>> =>
  fetchPart('/api/status', (body) => (body as { status?: ClaudeStatus | null }).status, null)

export const fetchApproval = (): Promise<Part<boolean>> =>
  fetchPart('/api/approve', (body) => (body as { approved: boolean }).approved === true, false)

export const approve = async () => void (await send('/api/approve'))

// Secondary, like status: an older server has no such route, so show nothing.
export const fetchLastEvent = (): Promise<Part<LastEvent | null>> =>
  fetchPart(
    '/api/last-event',
    (body) => (body as { last_event?: LastEvent | null }).last_event,
    null,
  )

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

export const fetchGrillDrafts = (): Promise<Part<Record<string, AnswerDraft>>> =>
  fetchPart(
    '/api/grill/drafts',
    (body) => (body as { drafts?: Record<string, AnswerDraft> }).drafts,
    {},
  )

export const saveGrillDraft = async (questionId: string, draft: AnswerDraft) =>
  void (await send(`/api/grill/drafts/${questionId}`, draft, 'PUT'))
/** Records every draft as an answer and tells Claude. */
export const submitGrill = async () => void (await send('/api/grill/submit'))

export const confirmGrill = async () => void (await send('/api/grill/confirm'))
export const reopenGrill = async (text: string) => void (await send('/api/grill/reopen', { text }))
