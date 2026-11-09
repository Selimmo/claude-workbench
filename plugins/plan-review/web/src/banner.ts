// What the Agent banner shows, given what was last sent to the agent and what it answered.

import type { AgentStatus, LastEvent } from './threads'

/** How long to wait for any status before suggesting a Resend. */
export const NO_RESPONSE_AFTER_MS = 120_000

export type Banner =
  | { kind: 'none' }
  | { kind: 'waiting' }
  | { kind: 'no-response' }
  | { kind: 'status'; status: AgentStatus }

export function bannerState(
  status: AgentStatus | null,
  last: LastEvent | null,
  now: number,
): Banner {
  if (last && !last.answered) {
    return now - Date.parse(last.sent_at) >= NO_RESPONSE_AFTER_MS
      ? { kind: 'no-response' }
      : { kind: 'waiting' }
  }
  return status ? { kind: 'status', status } : { kind: 'none' }
}
