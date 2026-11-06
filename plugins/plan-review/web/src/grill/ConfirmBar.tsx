import { useState } from 'react'

import type { Grill } from '../grill'

const HINT = "What's missing or wrong?"

/** Once Claude is done: 'Is this the shared understanding?' Yes confirms; No asks what is missing. */
export function ConfirmBar({
  grill,
  onConfirm,
  onReopen,
}: {
  grill: Grill
  onConfirm: () => Promise<void>
  onReopen: (text: string) => Promise<void>
}) {
  const [saying, setSaying] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const run = (action: () => Promise<void>) => {
    setError(null)
    void action().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }
  if (grill.confirmed_at)
    return (
      <p className="approval approved" role="note">
        Confirmed
      </p>
    )
  if (!grill.done) return null
  return (
    <div className="confirm-bar">
      <p>Is this the shared understanding?</p>
      <div className="confirm-buttons">
        <button className="primary" onClick={() => run(onConfirm)}>
          Yes
        </button>
        <button aria-pressed={saying} onClick={() => setSaying(true)}>
          No
        </button>
      </div>
      {saying && (
        <>
          <textarea
            aria-label={HINT}
            placeholder={HINT}
            required
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button
            disabled={text.trim() === ''}
            onClick={() =>
              run(async () => {
                await onReopen(text)
                setSaying(false)
                setText('')
              })
            }
          >
            Send
          </button>
        </>
      )}
      {error && <span className="error">{error}</span>}
    </div>
  )
}
