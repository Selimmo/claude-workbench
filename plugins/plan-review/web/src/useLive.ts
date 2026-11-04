import { useCallback, useEffect, useRef, useState } from 'react'

import {
  type PlanResult,
  approve,
  fetchApproval,
  fetchDrafts,
  fetchLastEvent,
  fetchPlan,
  fetchStatus,
  fetchThreads,
  resend,
} from './api'
import { changedIds } from './revisions'
import type { ClaudeStatus, Draft, LastEvent, Thread } from './threads'

export interface Live {
  result: PlanResult | null
  threads: Thread[]
  refreshThreads: () => Promise<void>
  /** What Claude is doing with the review, or null if it hasn't said. */
  status: ClaudeStatus | null
  /** The last event sent to Claude, or null if nothing was sent yet. */
  lastEvent: LastEvent | null
  /** The owner's unsent review comments. */
  drafts: Draft[]
  /** Re-read threads and drafts, after the page changed either. */
  refreshReview: () => Promise<void>
  /** Elements changed by revisions since the owner last marked them seen. */
  revised: Set<string>
  markSeen: () => void
  /** Send the last event to Claude again (a no-op if Claude has answered it). */
  resend: () => Promise<void>
  approved: boolean
  approvePlan: () => Promise<void>
}

/** The plan, its threads and approval, kept current by the server's update pushes. */
export function useLive(): Live {
  const [result, setResult] = useState<PlanResult | null>(null)
  const [threads, setThreads] = useState<Thread[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [status, setStatus] = useState<ClaudeStatus | null>(null)
  const [lastEvent, setLastEvent] = useState<LastEvent | null>(null)
  const [revised, setRevised] = useState<Set<string>>(new Set())
  const [approved, setApproved] = useState(false)
  const shown = useRef<PlanResult | null>(null)

  const refreshThreads = useCallback(async () => setThreads(await fetchThreads()), [])
  const refreshDrafts = useCallback(async () => setDrafts(await fetchDrafts()), [])
  const refreshLastEvent = useCallback(async () => setLastEvent(await fetchLastEvent()), [])
  const refreshReview = useCallback(
    async () => void (await Promise.all([refreshThreads(), refreshDrafts(), refreshLastEvent()])),
    [refreshThreads, refreshDrafts, refreshLastEvent],
  )

  const refreshPlan = useCallback(async () => {
    const next = await fetchPlan()
    const previous = shown.current
    if (previous?.ok && next.ok) {
      const changed = changedIds(previous.plan, next.plan)
      setRevised((old) => new Set([...old, ...changed]))
    }
    shown.current = next
    setResult(next)
  }, [])

  useEffect(() => {
    // Syncing with an external system (the server) is what effects are for.
    /* oxlint-disable react/set-state-in-effect */
    void Promise.all([
      refreshPlan(),
      refreshReview(),
      fetchApproval().then(setApproved),
      fetchStatus().then(setStatus),
    ])
    /* oxlint-enable react/set-state-in-effect */
    const socket = new WebSocket(`ws://${location.host}/api/updates`)
    socket.onmessage = (event: MessageEvent<string>) => {
      const { type } = JSON.parse(event.data) as { type: string }
      if (type === 'plan_changed') void refreshPlan()
      if (type === 'threads_changed') void refreshThreads()
      if (type === 'drafts_changed') void refreshDrafts()
      if (type === 'status_changed') {
        void fetchStatus().then(setStatus)
        void refreshLastEvent()
      }
    }
    return () => socket.close()
  }, [refreshPlan, refreshReview, refreshThreads, refreshDrafts, refreshLastEvent])

  return {
    result,
    threads,
    refreshThreads,
    drafts,
    status,
    lastEvent,
    refreshReview,
    revised,
    markSeen: () => setRevised(new Set()),
    resend: async () => {
      try {
        const result = await resend()
        if (!result.sent) setStatus(result.status)
      } catch {
        // Refused (nothing is kept) or the server is gone: the refresh below shows what is true.
      }
      await refreshLastEvent()
    },
    approved,
    approvePlan: async () => {
      await approve()
      setApproved(true)
      await refreshLastEvent()
    },
  }
}
