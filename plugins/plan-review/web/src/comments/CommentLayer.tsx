import {
  type MouseEvent,
  type ReactNode,
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'

import { ClassDetails } from '../ClassDetails'
import { classDetails } from '../diagram'
import type { Plan, Side } from '../plan'
import { threadsFor } from '../threadGroups'
import type { Draft, Thread } from '../threads'
import type { TabId } from '../viewModels'
import { Composer } from './Composer'
import { Pin } from './Pin'
import { useSpot } from './position'
import { ReviewPanel } from './ReviewPanel'
import { type Note, Toast } from './Toast'
import { ThreadCard } from './ThreadCard'
import { Prose } from '../Prose'

type Open =
  | { kind: 'thread'; id: string }
  | { kind: 'new'; anchor: string }
  | { kind: 'draft'; draft: Draft }
  | { kind: 'details'; id: string }
  | null

interface Props {
  plan: Plan
  tab: TabId
  /** The class side being shown, if the Classes tab is split by side. */
  side?: Side
  threads: Thread[]
  drafts: Draft[]
  refresh: () => Promise<void>
  readOnly: boolean
  header: ReactNode
  tabs: ReactNode
  children: ReactNode
}

const MARGIN = 16
/** Clicking these does their own job; it never opens a comment on the element around them. */
const CONTROLS = 'button, a, input, textarea, select, label, [role="dialog"]'

/** The element id a click comments on, or null if the click was meant for something else. */
function anchorOfClick(target: Element): string | null {
  if (target.closest(CONTROLS)) return null
  return target.closest('[data-element-id]')?.getAttribute('data-element-id') ?? null
}

function Floating({ anchor, children }: { anchor: string; children: ReactNode }) {
  // Cards open beside their element when it is on screen, else in the corner,
  // and are measured so they never run off the bottom or right of the window.
  const spot = useSpot(anchor)
  const box = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 340, height: 320 })
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const measure = () => setSize({ width: el.offsetWidth, height: el.offsetHeight })
    measure()
    if (typeof ResizeObserver !== 'function') return // jsdom
    const observer = new ResizeObserver(measure) // e.g. a new reply makes the card taller
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const style = spot
    ? {
        top: Math.max(MARGIN, Math.min(spot.top, window.innerHeight - size.height - MARGIN)),
        left: Math.max(MARGIN, Math.min(spot.left + 12, window.innerWidth - size.width - MARGIN)),
      }
    : { top: 80, right: 24 }
  return (
    <div ref={box} className="floating" style={style}>
      {children}
    </div>
  )
}

function ThreadList({
  title,
  threads,
  onOpen,
}: {
  title: string
  threads: Thread[]
  onOpen: (id: string) => void
}) {
  if (threads.length === 0) return null
  return (
    <section className="thread-list" aria-label={title}>
      <h3>{title}</h3>
      <ul>
        {threads.map((t) => (
          <li key={t.id}>
            <button className="link" data-resolved={t.resolved} onClick={() => onOpen(t.id)}>
              <code>{t.anchor}</code> <Prose text={t.messages[0]?.text ?? ''} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * Makes every element with a data-element-id commentable by a plain click, and lays out
 * the page around it: header, tab row, the tab's content, and a side panel with the
 * pending review and the threads that have no element to pin to.
 */
export function CommentLayer(props: Props) {
  const { plan, tab, side, threads, drafts, refresh, readOnly } = props
  const [open, setOpenState] = useState<Open>(null)
  const [note, setNote] = useState<Note | null>(null)
  // An open composer holding unsaved text: clicking another element must not throw it away.
  const writing = useRef(false)
  const groups = threadsFor(threads, plan, tab, side)
  const openThread = open?.kind === 'thread' ? threads.find((t) => t.id === open.id) : undefined
  const newDrafts = drafts.filter((d) => d.thread_id === null)

  function onClick(event: MouseEvent) {
    if (window.getSelection()?.toString()) return // the owner is selecting text to copy
    const target = event.target as Element
    // A class box opens its details (also when read-only); comments start from there.
    const card = target.closest('[data-details]')
    const cardId = card?.getAttribute('data-element-id')
    if (cardId) return setOpen({ kind: 'details', id: cardId })
    if (readOnly) return
    const anchor = anchorOfClick(target)
    if (anchor) setOpen({ kind: 'new', anchor })
  }

  // Every way of opening a card goes through here: while the open composer holds unsaved
  // text, nothing replaces it (a pin, "Comment on this tab", a draft's Edit, an element).
  // Only closing it (Cancel, ×, Esc, or saving) ends that text.
  function setOpen(next: Open) {
    if (writing.current && next !== null) return
    writing.current = false
    setOpenState(next)
  }
  const close = () => setOpen(null)
  const onDirty = (dirty: boolean) => (writing.current = dirty)
  const closeNote = useCallback(() => setNote(null), [])
  const editDraft = (draft: Draft) => setOpen({ kind: 'draft', draft })
  const aside =
    drafts.length > 0 ||
    groups.onTab.length > 0 ||
    groups.orphaned.length > 0 ||
    groups.otherSide.length > 0
  const details = open?.kind === 'details' ? classDetails(plan, open.id) : null
  return (
    <>
      <div className={readOnly ? 'plan' : 'plan commentable'} onClick={onClick}>
        {props.header}
        <div className="tab-row">
          {props.tabs}
          {!readOnly && (
            <button
              className="tab-comment"
              onClick={() => setOpen({ kind: 'new', anchor: `tab:${tab}` })}
            >
              Comment on this tab
            </button>
          )}
        </div>
        <div className="workspace">
          {props.children}
          {aside && (
            <aside className="side-panel">
              {!readOnly && (
                <ReviewPanel
                  drafts={drafts}
                  onChanged={refresh}
                  onEdit={editDraft}
                  onNotify={setNote}
                />
              )}
              <ThreadList
                title="Orphaned comments"
                threads={groups.orphaned}
                onOpen={(id) => setOpen({ kind: 'thread', id })}
              />
              <ThreadList
                title="Comments on the other side"
                threads={groups.otherSide}
                onOpen={(id) => setOpen({ kind: 'thread', id })}
              />
              <ThreadList
                title="Comments on this tab"
                threads={groups.onTab}
                onOpen={(id) => setOpen({ kind: 'thread', id })}
              />
            </aside>
          )}
        </div>
      </div>
      {note && <Toast note={note} onClose={closeNote} />}
      {groups.pinned.map((t) => (
        <Pin
          key={t.id}
          anchor={t.anchor}
          badge={String(t.messages.length)}
          label={`${t.messages.length} message${t.messages.length === 1 ? '' : 's'} on ${t.anchor}`}
          preview={t.messages[0]?.text ?? ''}
          onOpen={() => setOpen({ kind: 'thread', id: t.id })}
        />
      ))}
      {!readOnly &&
        newDrafts.map((d, i) => (
          <Pin
            key={d.id}
            anchor={d.anchor}
            badge="✎"
            label={`Draft on ${d.anchor}`}
            preview={d.text}
            draft
            // Beside any thread pin, and beside earlier drafts on the same element.
            offset={26 * (1 + newDrafts.slice(0, i).filter((o) => o.anchor === d.anchor).length)}
            onOpen={() => editDraft(d)}
          />
        ))}
      {openThread && (
        <Floating anchor={openThread.anchor}>
          <ThreadCard
            thread={openThread}
            drafts={drafts.filter((d) => d.thread_id === openThread.id)}
            onChanged={refresh}
            onEditDraft={editDraft}
            onClose={close}
            readOnly={readOnly}
          />
        </Floating>
      )}
      {details && (
        <Floating key={details.id} anchor={details.id}>
          <ClassDetails
            details={details}
            onComment={readOnly ? null : (anchor) => setOpen({ kind: 'new', anchor })}
            onClose={close}
          />
        </Floating>
      )}
      {open?.kind === 'new' && (
        <Floating anchor={open.anchor}>
          <Composer
            key={open.anchor}
            anchor={open.anchor}
            onSaved={refresh}
            onClose={close}
            onDirty={onDirty}
          />
        </Floating>
      )}
      {open?.kind === 'draft' && (
        <Floating anchor={open.draft.anchor}>
          <Composer
            key={open.draft.id}
            anchor={open.draft.anchor}
            draft={open.draft}
            onSaved={refresh}
            onClose={close}
            onDirty={onDirty}
          />
        </Floating>
      )}
    </>
  )
}
