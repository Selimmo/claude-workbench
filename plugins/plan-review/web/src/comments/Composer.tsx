import { useState } from 'react'

import { createThread } from '../api'

interface Props {
  anchor: string
  onPosted: () => Promise<void>
  onClose: () => void
}

export function Composer({ anchor, onPosted, onClose }: Props) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function post() {
    try {
      await createThread(anchor, draft)
      await onPosted()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div
      role="dialog"
      aria-label={`New comment on ${anchor}`}
      className="thread-card"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="card-top">
        <code>{anchor}</code>
        <button className="icon" aria-label="Close" onClick={onClose}>
          ×
        </button>
      </div>
      <textarea
        aria-label="Comment"
        placeholder="Your comment…"
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button disabled={!draft.trim()} onClick={() => void post()}>
          Post
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  )
}
