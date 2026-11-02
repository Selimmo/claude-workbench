// A fake plan-review server for page tests: routes fetch() and the updates WebSocket.

import example from '../../../examples/plan.json'
import type { Thread } from '../threads'

export interface Call {
  method: string
  url: string
  body: unknown
}

export class FakeServer {
  plan: unknown = example
  threads: Thread[] = []
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
    if (url === '/api/plan') return json(this.plan)
    if (url === '/api/threads' && method === 'GET') return json({ threads: this.threads })
    if (url === '/api/threads' && method === 'POST') {
      const { anchor, text } = body as { anchor: string; text: string }
      const created = thread(`t-${this.threads.length + 1}`, anchor, text)
      this.threads = [...this.threads, created]
      return json(created, 201)
    }
    const action = url.match(/^\/api\/threads\/([^/]+)\/(replies|resolve|reopen)$/)
    if (action) {
      const [, id, verb] = action
      this.threads = this.threads.map((t) =>
        t.id !== id
          ? t
          : verb === 'replies'
            ? { ...t, messages: [...t.messages, message('owner', (body as { text: string }).text)] }
            : { ...t, resolved: verb === 'resolve' },
      )
      return json(this.threads.find((t) => t.id === id))
    }
    return json({ errors: [`no route ${method} ${url}`] }, 404)
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
