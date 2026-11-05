import { useCallback, useState } from 'react'

import { fetchLastEvent, fetchStatus, resend as resendLast } from './api'
import type { ClaudeStatus, LastEvent } from './threads'

/** What Claude is doing and the last event sent to it: the data of the banner on both pages. */
export function useClaude() {
  const [status, setStatus] = useState<ClaudeStatus | null>(null)
  const [lastEvent, setLastEvent] = useState<LastEvent | null>(null)
  const refreshStatus = useCallback(async () => setStatus(await fetchStatus()), [])
  const refreshLastEvent = useCallback(async () => setLastEvent(await fetchLastEvent()), [])
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
