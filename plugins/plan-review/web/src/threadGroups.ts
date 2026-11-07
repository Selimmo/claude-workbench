import { sideOf } from './diagram'
import type { Plan, Side } from './plan'
import type { Thread } from './threads'
import { type TabId, tabOf } from './viewModels'

export interface ThreadGroups {
  /** Threads anchored to an element shown on this tab: drawn as pins. */
  pinned: Thread[]
  /** Threads about the whole tab (anchor `tab:<id>`). */
  onTab: Thread[]
  /** Threads whose element left the plan: shown on every tab. */
  orphaned: Thread[]
  /** Threads on a class of the side that is not shown: listed beside the diagram. */
  otherSide: Thread[]
  unresolved: number
}

/** The plan's header is commentable too; it is on every tab. */
export const HEADER_ANCHORS = { title: 'header:title', summary: 'header:summary' } as const
const onEveryTab = (anchor: string) => anchor.startsWith('header:')

export function threadsFor(threads: Thread[], plan: Plan, tab: TabId, side?: Side): ThreadGroups {
  const hidden = (t: Thread) => {
    const there = tab === 'classes' && side ? sideOf(plan, t.anchor) : null
    return there !== null && there !== side
  }
  return {
    pinned: threads.filter(
      (t) => !t.orphaned && !hidden(t) && (onEveryTab(t.anchor) || tabOf(plan, t.anchor) === tab),
    ),
    otherSide: threads.filter(hidden),
    onTab: threads.filter((t) => t.anchor === `tab:${tab}`),
    orphaned: threads.filter((t) => t.orphaned),
    unresolved: threads.filter((t) => !t.resolved).length,
  }
}
