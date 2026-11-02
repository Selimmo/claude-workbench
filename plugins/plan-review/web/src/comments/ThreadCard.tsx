import { useState } from 'react'

import { replyTo, setResolved } from '../api'
import type { Thread } from '../threads'

interface Props {
  thread: Thread
  onChanged: () => Promise<void>
  onClose: () => void
  readOnly: boolean
}

export function ThreadCard({ thread, onChanged, onClose, readOnly }: Props) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function act(action: () => Promise<void>) {
    setError(null)
    try {
      await action()
      await onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div
      role="dialog"
      aria-label={`Thread on ${thread.anchor}`}
      className="thread-card"
      data-resolved={thread.resolved}
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="card-top">
        <code>{thread.anchor}</code>
        <button className="icon" aria-label="Close" onClick={onClose}>
          ×
        </button>
      </div>
      <ol className="messages">
        {thread.messages.map((m, i) => (
          <li key={i} data-author={m.author}>
            <span className="author">{m.author === 'owner' ? 'You' : 'Claude'}</span>
            <span className="text">{m.text}</span>
          </li>
        ))}
      </ol>
      {!readOnly && (
        <>
          <textarea
            aria-label="Reply"
            placeholder="Reply…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          {error && <p className="error">{error}</p>}
          <div className="actions">
            <button
              disabled={!draft.trim()}
              onClick={() =>
                act(async () => {
                  await replyTo(thread.id, draft)
                  setDraft('')
                })
              }
            >
              Reply
            </button>
            <button onClick={() => act(() => setResolved(thread.id, !thread.resolved))}>
              {thread.resolved ? 'Reopen' : 'Resolve'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
