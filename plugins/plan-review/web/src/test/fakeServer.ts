// A fake plan-review server for page tests: routes fetch() and the updates WebSocket.

import example from '../../../examples/plan.json'
import type { AnswerDraft, Grill } from '../grill'
import type { ClaudeStatus, Draft, LastEvent, Thread } from '../threads'

export interface Call {
  method: string
  url: string
  body: unknown
}

export class FakeServer {
  /** Null: no plan yet, as while the grill is still on. */
  plan: unknown = example
  /** Null: no grill.json. */
  grill: Grill | null = null
  grillDrafts: Record<string, AnswerDraft> = {}
  threads: Thread[] = []
  drafts: Draft[] = []
  status: ClaudeStatus | null = null
  /** What was last sent to Claude; set by review and approve, as the server does. */
  lastEvent: LastEvent | null = null
  reviewError: string | null = null
  /** When set, a submit waits for it: lets a test look at the page mid-submit. */
  reviewHold: Promise<void> | null = null
  resendHold: Promise<void> | null = null
  approved = false
  /** When set, the grill's drafts, submit, confirm and reopen are refused with this message (409). */
  grillRefusal: string | null = null
  /** When set, the routes that read grill.json answer 422 with these errors, as for a grill.json that does not parse. */
  grillErrors: string[] | null = null
  /** Url -> lines: that route answers 422 for every method, as for a broken file behind it. */
  brokenFiles: Record<string, string[]> = {}
  /** Url -> body: that route answers 422 with this body as is, e.g. FastAPI's own validation reply. */
  rawBroken: Record<string, unknown> = {}
  /** Urls whose fetch is rejected, as when the server has stopped. */
  down = new Set<string>()
  calls: Call[] = []

  install() {
    vi.stubGlobal('fetch', vi.fn(this.handle))
    vi.stubGlobal('WebSocket', FakeSocket)
  }

  private handle = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const body: unknown = init?.body ? JSON.parse(String(init.body)) : null
    this.calls.push({ method, url, body })
    const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
    if (this.down.has(url)) throw new TypeError('Failed to fetch')
    if (url in this.rawBroken) return json(this.rawBroken[url], 422)
    const broken = this.brokenFiles[url]
    if (broken) return json({ errors: broken }, 422)
    if (url === '/api/plan')
      return this.plan === null
        ? json({ errors: ['.claude/work/42/plan.json: file not found'] }, 404)
        : json(this.plan)
    const grillReply = this.handleGrill(url, method, body, json)
    if (grillReply) return grillReply
    if (url === '/api/approve' && method === 'GET') return json({ approved: this.approved })
    if (url === '/api/approve' && method === 'POST') {
      if (this.drafts.length)
        return json(
          { errors: [`${this.drafts.length} unsent draft(s): submit or discard them first`] },
          409,
        )
      const open = this.threads.filter((t) => !t.resolved).length
      if (open) return json({ errors: [`${open} unresolved thread(s): resolve them first`] }, 409)
      this.approved = true
      this.sent('approved')
      return json({ approved_at: '2026-11-02T12:00:00Z', plan_sha256: 'abc' })
    }
    if (url === '/api/threads' && method === 'GET') return json({ threads: this.threads })
    if (url === '/api/drafts' && method === 'GET') return json({ drafts: this.drafts })
    if (url === '/api/drafts' && method === 'POST') {
      const { anchor, thread_id, text } = body as Partial<Draft> & { text: string }
      const parent = this.threads.find((t) => t.id === thread_id)
      const created = draft(
        `d-${this.drafts.length + 1}`,
        parent?.anchor ?? anchor ?? '',
        text,
        thread_id ?? null,
      )
      this.drafts = [...this.drafts, created]
      return json(created, 201)
    }
    const oneDraft = url.match(/^\/api\/drafts\/([^/]+)$/)
    if (oneDraft && method === 'PUT') {
      const { text } = body as { text: string }
      this.drafts = this.drafts.map((d) => (d.id === oneDraft[1] ? { ...d, text } : d))
      return json(this.drafts.find((d) => d.id === oneDraft[1]))
    }
    if (oneDraft && method === 'DELETE') {
      this.drafts = this.drafts.filter((d) => d.id !== oneDraft[1])
      return new Response(null, { status: 204 })
    }
    if (url === '/api/status') return json({ status: this.status })
    if (url === '/api/last-event') return json({ last_event: this.lastEvent })
    if (url === '/api/resend' && method === 'POST') {
      if (this.resendHold) await this.resendHold
      if (!this.lastEvent) return json({ errors: ['nothing has been sent to Claude yet'] }, 409)
      if (this.lastEvent.answered) return json({ sent: false, status: this.status })
      this.sent(this.lastEvent.type)
      return json({ sent: true })
    }
    if (url === '/api/review' && method === 'POST') {
      if (this.reviewHold) await this.reviewHold
      if (this.reviewError) return json({ errors: [this.reviewError] }, 500)
      const comments = this.drafts.map((d) => ({
        type: d.thread_id ? 'reply' : 'comment',
        anchor: d.anchor,
        text: d.text,
      }))
      for (const d of this.drafts) {
        this.threads = d.thread_id
          ? this.threads.map((t) =>
              t.id === d.thread_id
                ? { ...t, messages: [...t.messages, message('owner', d.text)] }
                : t,
            )
          : [...this.threads, thread(`t-${this.threads.length + 1}`, d.anchor, d.text)]
      }
      this.drafts = []
      this.sent('review_submitted')
      return json({ comments })
    }
    const action = url.match(/^\/api\/threads\/([^/]+)\/(resolve|reopen)$/)
    if (action) {
      const [, id, verb] = action
      this.threads = this.threads.map((t) =>
        t.id === id ? { ...t, resolved: verb === 'resolve' } : t,
      )
      return json(this.threads.find((t) => t.id === id))
    }
    return json({ errors: [`no route ${method} ${url}`] }, 404)
  }

  private handleGrill(
    url: string,
    method: string,
    body: unknown,
    json: (data: unknown, status?: number) => Response,
  ): Response | null {
    if (!url.startsWith('/api/grill')) return null
    const one = url.match(/^\/api\/grill\/drafts\/([^/]+)$/)
    const readsGrill =
      url === '/api/grill' ||
      (one && method === 'PUT') ||
      ['/api/grill/submit', '/api/grill/confirm', '/api/grill/reopen'].includes(url)
    if (this.grillErrors && readsGrill) return json({ errors: this.grillErrors }, 422)
    const grill = this.grill
    if (!grill && readsGrill)
      return json({ errors: ['.claude/work/42/grill.json: file not found'] }, 404)
    if (url === '/api/grill/drafts') return json({ drafts: this.grillDrafts })
    if (!grill) return json({ errors: [`no route ${method} ${url}`] }, 404)
    if (url === '/api/grill') return json(grill)
    if (this.grillRefusal && ((one && method === 'PUT') || url === '/api/grill/submit'))
      return json({ errors: [this.grillRefusal] }, 409)
    if (one && method === 'PUT') {
      this.grillDrafts = { ...this.grillDrafts, [one[1]]: body as AnswerDraft }
      return json(body)
    }
    if (one && method === 'DELETE') {
      const { [one[1]]: _, ...rest } = this.grillDrafts
      this.grillDrafts = rest
      return new Response(null, { status: 204 })
    }
    if (url === '/api/grill/submit') {
      const answers = Object.entries(this.grillDrafts).map(([question_id, d]) => ({
        question_id,
        ...d,
      }))
      for (const round of grill.rounds)
        for (const q of round.questions) {
          const d = this.grillDrafts[q.id]
          if (!d || q.answer) continue
          if (d.kind === 'ask') q.thread.push(message('owner', d.text ?? ''))
          else
            q.answer = {
              kind: d.kind,
              choice_id: d.choice_id ?? null,
              text: d.text ?? null,
            }
        }
      grill.log.push({ kind: 'answers', text: null, at: new Date().toISOString() })
      this.grillDrafts = {}
      this.sent('grill_submitted')
      return json({ answers })
    }
    if (this.grillRefusal && (url === '/api/grill/confirm' || url === '/api/grill/reopen'))
      return json({ errors: [this.grillRefusal] }, 409)
    if (url === '/api/grill/confirm') {
      grill.confirmed_at = new Date().toISOString()
      grill.log.push({ kind: 'confirm', text: null, at: grill.confirmed_at })
      this.sent('grill_confirmed')
      return json({ confirmed: true })
    }
    if (url === '/api/grill/reopen') {
      grill.done = false
      grill.log.push({ kind: 'reopen', text: (body as { text: string }).text, at: '' })
      this.sent('grill_reopened')
      return json({ reopened: true })
    }
    return json({ errors: [`no route ${method} ${url}`] }, 404)
  }

  private sent(type: string) {
    this.lastEvent = { type, sent_at: new Date().toISOString(), answered: false }
  }

  /** Simulate the server's push, e.g. after Claude replies through the CLI. */
  push(message: object) {
    for (const socket of FakeSocket.open) socket.onmessage?.({ data: JSON.stringify(message) })
  }
}

class FakeSocket {
  static open = new Set<FakeSocket>()
  onmessage: ((event: { data: string }) => void) | null = null
  constructor() {
    FakeSocket.open.add(this)
  }
  close() {
    FakeSocket.open.delete(this)
  }
}

export function message(author: 'owner' | 'claude', text: string) {
  return { author, text, at: '2026-11-02T10:00:00Z' }
}

export function thread(id: string, anchor: string, ...texts: string[]): Thread {
  return {
    id,
    anchor,
    messages: texts.map((text, i) => message(i % 2 === 0 ? 'owner' : 'claude', text)),
    resolved: false,
    orphaned: false,
  }
}

export function draft(
  id: string,
  anchor: string,
  text: string,
  thread_id: string | null = null,
): Draft {
  return { id, anchor, text, thread_id, at: '2026-11-02T11:00:00Z' }
}
