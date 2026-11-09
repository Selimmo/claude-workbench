// Comment threads as the server returns them (see plan_review/threads.py).

/** Files saved before the agent was neutral hold the old value: this is the one place it is named. */
export type Author = 'owner' | 'agent' | 'claude'

/** What the page calls an author: both agent values are shown as Agent. */
export const authorLabel = (author: Author): 'You' | 'Agent' =>
  author === 'owner' ? 'You' : 'Agent'

export interface Message {
  author: Author
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

/** Resolve is offered only once the agent has the last word (the server enforces it too). */
export const canResolve = (thread: Thread): boolean =>
  thread.messages[thread.messages.length - 1]?.author !== 'owner'

/** What the agent is doing with the review, set with `plan-review status` (status.py). */
export interface AgentStatus {
  text: string
  /** False while the agent is still working on it. */
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

/** The last event sent to the agent (see plan_review/last_event.py and resend.py). */
export interface LastEvent {
  type: string
  sent_at: string
  /** True once the agent set a status after it was sent. */
  answered: boolean
}
