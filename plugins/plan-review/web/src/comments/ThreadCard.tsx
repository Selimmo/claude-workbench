import { useState } from 'react'

import { discardDraft, draftReply, setResolved } from '../api'
import { authorLabel, canResolve, type Draft, type Thread } from '../threads'
import { Prose } from '../Prose'

interface Props {
  thread: Thread
  /** The owner's unsent replies in this thread. */
  drafts: Draft[]
  onChanged: () => Promise<void>
  onEditDraft: (draft: Draft) => void
  onClose: () => void
  readOnly: boolean
}

export function ThreadCard({ thread, drafts, onChanged, onEditDraft, onClose, readOnly }: Props) {
  const [text, setText] = useState('')
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
      <div className="card-body">
        <ol className="messages">
          {thread.messages.map((m, i) => (
            <li key={i} data-author={m.author === 'owner' ? 'owner' : 'agent'}>
              <span className="author">{authorLabel(m.author)}</span>
              <span className="text">
                <Prose text={m.text} />
              </span>
            </li>
          ))}
        </ol>
        {drafts.length > 0 && (
          <ol className="messages" aria-label="Your draft replies">
            {drafts.map((d) => (
              <li key={d.id} data-author="owner" data-draft="true">
                <span className="author">
                  You <span className="badge">Draft</span>
                </span>
                <span className="text">
                  <Prose text={d.text} />
                </span>
                {!readOnly && (
                  <span className="draft-actions">
                    <button className="link" onClick={() => onEditDraft(d)}>
                      Edit
                    </button>
                    <button className="link" onClick={() => void act(() => discardDraft(d.id))}>
                      Discard
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
        {!readOnly && (
          <>
            <textarea
              aria-label="Reply"
              placeholder="Reply…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            {error && <p className="error">{error}</p>}
            <div className="actions">
              <button
                disabled={!text.trim()}
                onClick={() =>
                  act(async () => {
                    await draftReply(thread.id, text)
                    setText('')
                  })
                }
              >
                Add reply to review
              </button>
              {(thread.resolved || canResolve(thread)) && (
                <button onClick={() => act(() => setResolved(thread.id, !thread.resolved))}>
                  {thread.resolved ? 'Reopen' : 'Resolve'}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
