import {
  type MouseEvent,
  type ReactNode,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'

import type { Plan } from '../plan'
import { threadsFor } from '../threadGroups'
import type { Thread } from '../threads'
import type { TabId } from '../viewModels'
import { Composer } from './Composer'
import { Pin } from './Pin'
import { useSpot } from './position'
import { ThreadCard } from './ThreadCard'

type Open = { kind: 'thread'; id: string } | { kind: 'new'; anchor: string } | null

interface Props {
  plan: Plan
  tab: TabId
  threads: Thread[]
  refresh: () => Promise<void>
  readOnly: boolean
  children: ReactNode
}

const MARGIN = 16

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
              <code>{t.anchor}</code> {t.messages[0]?.text}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function CommentLayer({ plan, tab, threads, refresh, readOnly, children }: Props) {
  const [commenting, setCommenting] = useState(false)
  const [open, setOpen] = useState<Open>(null)
  const groups = threadsFor(threads, plan, tab)

  useEffect(() => {
    if (!commenting) return
    const cancel = (e: KeyboardEvent) => e.key === 'Escape' && setCommenting(false)
    window.addEventListener('keydown', cancel)
    return () => window.removeEventListener('keydown', cancel)
  }, [commenting])
  const openThread = open?.kind === 'thread' ? threads.find((t) => t.id === open.id) : undefined

  function onClickCapture(event: MouseEvent) {
    if (!commenting) return
    const target = (event.target as Element).closest('[data-element-id]')
    if (!target) return
    event.preventDefault()
    event.stopPropagation()
    setOpen({ kind: 'new', anchor: target.getAttribute('data-element-id') ?? '' })
    setCommenting(false)
  }

  const close = () => setOpen(null)
  return (
    <>
      {!readOnly && (
        <div className="comment-bar">
          <button aria-pressed={commenting} onClick={() => setCommenting((on) => !on)}>
            {commenting ? 'Click an element… (Esc to cancel)' : 'Add comment'}
          </button>
          <button onClick={() => setOpen({ kind: 'new', anchor: `tab:${tab}` })}>
            Comment on this tab
          </button>
        </div>
      )}
      <ThreadList
        title="Orphaned comments"
        threads={groups.orphaned}
        onOpen={(id) => setOpen({ kind: 'thread', id })}
      />
      <ThreadList
        title="Comments on this tab"
        threads={groups.onTab}
        onOpen={(id) => setOpen({ kind: 'thread', id })}
      />
      <div
        className={commenting ? 'commentable commenting' : 'commentable'}
        onClickCapture={onClickCapture}
      >
        {children}
      </div>
      {groups.pinned.map((t) => (
        <Pin key={t.id} thread={t} onOpen={() => setOpen({ kind: 'thread', id: t.id })} />
      ))}
      {openThread && (
        <Floating anchor={openThread.anchor}>
          <ThreadCard thread={openThread} onChanged={refresh} onClose={close} readOnly={readOnly} />
        </Floating>
      )}
      {open?.kind === 'new' && (
        <Floating anchor={open.anchor}>
          <Composer anchor={open.anchor} onPosted={refresh} onClose={close} />
        </Floating>
      )}
    </>
  )
}
