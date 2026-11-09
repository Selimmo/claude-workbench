import { useEffect, useState } from 'react'

import { NO_RESPONSE_AFTER_MS, bannerState } from './banner'
import type { AgentStatus, LastEvent } from './threads'

/** What the agent is doing with the owner's last review or approval, full width above the plan. */
export function AgentBanner({
  status,
  lastEvent,
  onResend,
}: {
  status: AgentStatus | null
  lastEvent: LastEvent | null
  onResend: () => void | Promise<void>
}) {
  const [now, setNow] = useState(() => Date.now())
  const [resending, setResending] = useState(false)
  const state = bannerState(status, lastEvent, now)
  const waiting = state.kind === 'waiting'
  const sentAt = lastEvent?.sent_at
  useEffect(() => {
    // Re-render once the wait is over, so the banner can turn red without any other change.
    // Syncing with the clock is what effects are for.
    if (!waiting || !sentAt) return
    const remaining = Date.parse(sentAt) + NO_RESPONSE_AFTER_MS - Date.now()
    const timer = setTimeout(() => setNow(Date.now()), remaining)
    return () => clearTimeout(timer)
  }, [waiting, sentAt])
  if (state.kind === 'none') return null
  const resend = async () => {
    setResending(true)
    try {
      await onResend()
    } finally {
      setResending(false)
    }
  }
  return (
    <div
      role="status"
      aria-label="Agent"
      className="agent-banner"
      data-state={state.kind}
      data-done={state.kind === 'status' ? state.status.done : undefined}
    >
      <span className="agent-banner-mark" aria-hidden="true" />
      {state.kind === 'status' && (
        <>
          Agent: <span>{state.status.text}</span>
        </>
      )}
      {state.kind === 'waiting' && 'Sent to the agent, waiting for a response'}
      {state.kind === 'no-response' && (
        <>
          No response from the agent yet
          <button onClick={resend} disabled={resending}>
            Resend
          </button>
        </>
      )}
    </div>
  )
}
