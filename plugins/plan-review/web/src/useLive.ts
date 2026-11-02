import { useCallback, useEffect, useRef, useState } from 'react'

import { type PlanResult, approve, fetchApproval, fetchPlan, fetchThreads } from './api'
import { changedIds } from './revisions'
import type { Thread } from './threads'

export interface Live {
  result: PlanResult | null
  threads: Thread[]
  refreshThreads: () => Promise<void>
  /** Elements changed by revisions since the owner last marked them seen. */
  revised: Set<string>
  markSeen: () => void
  approved: boolean
  approvePlan: () => Promise<void>
}

/** The plan, its threads and approval, kept current by the server's update pushes. */
export function useLive(): Live {
  const [result, setResult] = useState<PlanResult | null>(null)
  const [threads, setThreads] = useState<Thread[]>([])
  const [revised, setRevised] = useState<Set<string>>(new Set())
  const [approved, setApproved] = useState(false)
  const shown = useRef<PlanResult | null>(null)

  const refreshThreads = useCallback(async () => setThreads(await fetchThreads()), [])

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
    // oxlint-disable-next-line react/set-state-in-effect
    void Promise.all([refreshPlan(), refreshThreads(), fetchApproval().then(setApproved)])
    const socket = new WebSocket(`ws://${location.host}/api/updates`)
    socket.onmessage = (event: MessageEvent<string>) => {
      const { type } = JSON.parse(event.data) as { type: string }
      if (type === 'plan_changed') void refreshPlan()
      if (type === 'threads_changed') void refreshThreads()
    }
    return () => socket.close()
  }, [refreshPlan, refreshThreads])

  return {
    result,
    threads,
    refreshThreads,
    revised,
    markSeen: () => setRevised(new Set()),
    approved,
    approvePlan: async () => {
      await approve()
      setApproved(true)
    },
  }
}
