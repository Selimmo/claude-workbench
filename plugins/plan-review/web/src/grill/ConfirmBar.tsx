import { useState } from 'react'

import type { Grill } from '../grill'

/** Once Claude says it is done: Confirm, or 'Not yet' with what is missing. Then 'Confirmed'. */
export function ConfirmBar({
  grill,
  onConfirm,
  onReopen,
}: {
  grill: Grill
  onConfirm: () => Promise<void>
  onReopen: (text: string) => Promise<void>
}) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const run = (action: () => Promise<void>) =>
    void action().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  if (grill.confirmed_at)
    return (
      <p className="approval approved" role="note">
        Confirmed
      </p>
    )
  if (!grill.done) return null
  return (
    <div className="confirm-bar">
      <p>Claude has nothing left to ask. Is this the shared understanding?</p>
      <button className="primary" onClick={() => run(onConfirm)}>
        Confirm
      </button>
      <textarea
        aria-label="What is missing?"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button disabled={text.trim() === ''} onClick={() => run(() => onReopen(text))}>
        Not yet
      </button>
      {error && <span className="error">{error}</span>}
    </div>
  )
}
