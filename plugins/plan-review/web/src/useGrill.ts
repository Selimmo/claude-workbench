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
import { DraftSync } from './draftSync'
import { connectUpdates } from './updatesSocket'
import { useAgent } from './useAgent'
import { useFileErrors } from './useFileErrors'

/** The grill page's live state, kept current by the server's update pushes. */
export function useGrill() {
  const [grill, setGrill] = useState<Grill | null>(null)
  const [grillErrors, setGrillErrors] = useState<string[] | null>(null)
  const [drafts, setDrafts] = useState<Record<string, AnswerDraft>>({})
  const [sync] = useState(() => new DraftSync(saveGrillDraft))
  const { errors: brokenFiles, report } = useFileErrors()
  const agent = useAgent(report)
  const { refreshStatus, refreshLastEvent } = agent
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
    const mark = sync.mark()
    const part = await fetchGrillDrafts()
    report('grill drafts', part.errors)
    // Against the newest page copy: questions being typed in keep what is on the page.
    setDrafts((old) => sync.merge(part.value, old, mark))
  }, [report, sync])

  useEffect(() => {
    // Syncing with an external system (the server) is what effects are for.
    /* oxlint-disable react/set-state-in-effect */
    const refreshAll = () =>
      void Promise.all([
        refreshGrill(),
        refreshDrafts(),
        refreshPlan(),
        refreshStatus(),
        refreshLastEvent(),
      ])
    refreshAll()
    /* oxlint-enable react/set-state-in-effect */
    return connectUpdates(
      `ws://${location.host}/api/updates`,
      ({ type }) => {
        if (type === 'grill_changed') void refreshGrill()
        if (type === 'grill_drafts_changed') void refreshDrafts()
        if (type === 'plan_changed') void refreshPlan()
        if (type === 'status_changed') {
          void refreshStatus()
          void refreshLastEvent()
        }
      },
      refreshAll, // the viewer was away: read everything again
    )
  }, [refreshGrill, refreshDrafts, refreshPlan, refreshStatus, refreshLastEvent])

  return {
    ...agent,
    grill,
    grillErrors,
    brokenFiles,
    drafts,
    planReady,
    saveDraft: async (questionId: string, draft: AnswerDraft) => {
      setDrafts((old) => ({ ...old, [questionId]: draft }))
      try {
        await sync.save(questionId, draft)
      } catch (error) {
        await refreshDrafts() // show what the server has, not what it refused
        throw error
      }
    },
    submit: async () => {
      await sync.settled() // the last letters must reach the server first
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
