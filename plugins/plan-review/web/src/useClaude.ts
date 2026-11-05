import { useCallback, useState } from 'react'

import { fetchLastEvent, fetchStatus, resend as resendLast } from './api'
import type { ClaudeStatus, LastEvent } from './threads'

/** What Claude is doing and the last event sent to it: the data of the banner on both pages. */
export function useClaude(report: (source: string, lines: string[]) => void) {
  const [status, setStatus] = useState<ClaudeStatus | null>(null)
  const [lastEvent, setLastEvent] = useState<LastEvent | null>(null)
  const refreshStatus = useCallback(async () => {
    const part = await fetchStatus()
    report('status', part.errors)
    setStatus(part.value)
  }, [report])
  const refreshLastEvent = useCallback(async () => {
    const part = await fetchLastEvent()
    report('last event', part.errors)
    setLastEvent(part.value)
  }, [report])
  const resend = useCallback(async () => {
    try {
      const result = await resendLast()
      if (!result.sent) setStatus(result.status)
    } catch {
      // Refused (nothing is kept) or the server is gone: the refresh below shows what is true.
    }
    await refreshLastEvent()
  }, [refreshLastEvent])
  return { status, lastEvent, resend, refreshStatus, refreshLastEvent }
}
