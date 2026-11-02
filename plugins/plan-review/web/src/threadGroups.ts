import type { Plan } from './plan'
import type { Thread } from './threads'
import { type TabId, tabOf } from './viewModels'

export interface ThreadGroups {
  /** Threads anchored to an element shown on this tab: drawn as pins. */
  pinned: Thread[]
  /** Threads about the whole tab (anchor `tab:<id>`). */
  onTab: Thread[]
  /** Threads whose element left the plan: shown on every tab. */
  orphaned: Thread[]
  unresolved: number
}

export function threadsFor(threads: Thread[], plan: Plan, tab: TabId): ThreadGroups {
  return {
    pinned: threads.filter((t) => !t.orphaned && tabOf(plan, t.anchor) === tab),
    onTab: threads.filter((t) => t.anchor === `tab:${tab}`),
    orphaned: threads.filter((t) => t.orphaned),
    unresolved: threads.filter((t) => !t.resolved).length,
  }
}
