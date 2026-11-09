import { useCallback, useEffect, useRef, useState } from 'react'

import {
  type PlanResult,
  approve,
  fetchApproval,
  fetchDrafts,
  fetchPlan,
  fetchThreads,
} from './api'
import { useAgent } from './useAgent'
import { useFileErrors } from './useFileErrors'
import { changedIds } from './revisions'
import type { AgentStatus, Draft, LastEvent, Thread } from './threads'

export interface Live {
  result: PlanResult | null
  threads: Thread[]
  refreshThreads: () => Promise<void>
  /** What the agent is doing with the review, or null if it hasn't said. */
  status: AgentStatus | null
  /** The last event sent to the agent, or null if nothing was sent yet. */
  lastEvent: LastEvent | null
  /** The owner's unsent review comments. */
  drafts: Draft[]
  /** Re-read threads and drafts, after the page changed either. */
  refreshReview: () => Promise<void>
  /** Elements changed by revisions since the owner last marked them seen. */
  revised: Set<string>
  markSeen: () => void
  /** Send the last event to the agent again (a no-op if the agent has answered it). */
  resend: () => Promise<void>
  approved: boolean
  /** The lines naming each broken file: comments, drafts, status, last event, approval. */
  brokenFiles: string[]
  approvePlan: () => Promise<void>
}

/** The plan, its threads and approval, kept current by the server's update pushes. */
export function useLive(): Live {
  const [result, setResult] = useState<PlanResult | null>(null)
  const [threads, setThreads] = useState<Thread[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const { errors: brokenFiles, report } = useFileErrors()
  const { status, lastEvent, resend, refreshStatus, refreshLastEvent } = useAgent(report)
  const [revised, setRevised] = useState<Set<string>>(new Set())
  const [approved, setApproved] = useState(false)
  const shown = useRef<PlanResult | null>(null)

  const refreshThreads = useCallback(async () => {
    const part = await fetchThreads()
    report('comments', part.errors)
    setThreads(part.value)
  }, [report])
  const refreshDrafts = useCallback(async () => {
    const part = await fetchDrafts()
    report('drafts', part.errors)
    setDrafts(part.value)
  }, [report])
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
      fetchApproval().then((part) => {
        report('approval', part.errors)
        setApproved(part.value)
      }),
      refreshStatus(),
    ])
    /* oxlint-enable react/set-state-in-effect */
    const socket = new WebSocket(`ws://${location.host}/api/updates`)
    socket.onmessage = (event: MessageEvent<string>) => {
      const { type } = JSON.parse(event.data) as { type: string }
      if (type === 'plan_changed') void refreshPlan()
      if (type === 'threads_changed') void refreshThreads()
      if (type === 'drafts_changed') void refreshDrafts()
      if (type === 'status_changed') {
        void refreshStatus()
        void refreshLastEvent()
      }
    }
    return () => socket.close()
  }, [
    refreshPlan,
    refreshReview,
    refreshThreads,
    refreshDrafts,
    refreshLastEvent,
    refreshStatus,
    report,
  ])

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
    resend,
    approved,
    brokenFiles,
    approvePlan: async () => {
      await approve()
      setApproved(true)
      await refreshLastEvent()
    },
  }
}
