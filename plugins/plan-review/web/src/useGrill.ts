import { useCallback, useEffect, useState } from 'react'

import {
  confirmGrill,
  fetchGrill,
  fetchGrillDrafts,
  fetchPlan,
  reopenGrill,
  saveGrillDraft,
  submitGrill,
} from './api'
import type { AnswerDraft, Grill } from './grill'
import { useClaude } from './useClaude'
import { useFileErrors } from './useFileErrors'

/** The grill page's live state, kept current by the server's update pushes. */
export function useGrill() {
  const [grill, setGrill] = useState<Grill | null>(null)
  const [grillErrors, setGrillErrors] = useState<string[] | null>(null)
  const [drafts, setDrafts] = useState<Record<string, AnswerDraft>>({})
  const { errors: brokenFiles, report } = useFileErrors()
  const claude = useClaude(report)
  const { refreshStatus, refreshLastEvent } = claude
  const [planReady, setPlanReady] = useState(false)
  const refreshPlan = useCallback(async () => {
    const plan = await fetchPlan()
    setPlanReady(plan.ok)
    // No plan yet is the normal case while grilling; one the server calls invalid is not.
    report('plan', !plan.ok && plan.broken ? plan.errors : [])
  }, [report])
  const refreshGrill = useCallback(async () => {
    const result = await fetchGrill()
    setGrill(result?.ok ? result.grill : null)
    setGrillErrors(result && !result.ok ? result.errors : null)
  }, [])
  const refreshDrafts = useCallback(async () => {
    const part = await fetchGrillDrafts()
    report('grill drafts', part.errors)
    setDrafts(part.value)
  }, [report])

  useEffect(() => {
    // Syncing with an external system (the server) is what effects are for.
    /* oxlint-disable react/set-state-in-effect */
    void Promise.all([
      refreshGrill(),
      refreshDrafts(),
      refreshPlan(),
      refreshStatus(),
      refreshLastEvent(),
    ])
    /* oxlint-enable react/set-state-in-effect */
    const socket = new WebSocket(`ws://${location.host}/api/updates`)
    socket.onmessage = (event: MessageEvent<string>) => {
      const { type } = JSON.parse(event.data) as { type: string }
      if (type === 'grill_changed') void refreshGrill()
      if (type === 'grill_drafts_changed') void refreshDrafts()
      if (type === 'plan_changed') void refreshPlan()
      if (type === 'status_changed') {
        void refreshStatus()
        void refreshLastEvent()
      }
    }
    return () => socket.close()
  }, [refreshGrill, refreshDrafts, refreshPlan, refreshStatus, refreshLastEvent])

  return {
    ...claude,
    grill,
    grillErrors,
    brokenFiles,
    drafts,
    planReady,
    saveDraft: async (questionId: string, draft: AnswerDraft) => {
      setDrafts((old) => ({ ...old, [questionId]: draft }))
      try {
        await saveGrillDraft(questionId, draft)
      } catch (error) {
        await refreshDrafts() // show what the server has, not what it refused
        throw error
      }
    },
    submit: async () => {
      await submitGrill()
      setDrafts({})
      await Promise.all([refreshGrill(), refreshLastEvent()])
    },
    confirm: async () => {
      await confirmGrill()
      await Promise.all([refreshGrill(), refreshLastEvent()])
    },
    reopen: async (text: string) => {
      await reopenGrill(text)
      await Promise.all([refreshGrill(), refreshLastEvent()])
    },
  }
}
