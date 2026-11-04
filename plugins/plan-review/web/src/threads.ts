// Comment threads as the server returns them (see plan_review/threads.py).

export interface Message {
  author: 'owner' | 'claude'
  text: string
  at: string
}

export interface Thread {
  id: string
  anchor: string
  messages: Message[]
  resolved: boolean
  orphaned: boolean
}

/** What Claude is doing with the review, set with `plan-review status` (status.py). */
export interface ClaudeStatus {
  text: string
  /** False while Claude is still working on it. */
  done: boolean
  at: string
}

/** An unsent review comment (see plan_review/drafts.py): only the owner sees it. */
export interface Draft {
  id: string
  anchor: string
  text: string
  /** Set for a reply in an existing thread; null for a new comment on `anchor`. */
  thread_id: string | null
  at: string
}

/** The last event sent to Claude (see plan_review/last_event.py and resend.py). */
export interface LastEvent {
  type: string
  sent_at: string
  /** True once Claude set a status after it was sent. */
  answered: boolean
}
