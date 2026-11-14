import { useState } from 'react'

import { discardDraft, draftComment, editDraft } from '../api'
import type { Draft } from '../threads'

interface Props {
  anchor: string
  /** Set to edit a pending draft; otherwise this writes a new comment on `anchor`. */
  draft?: Draft
  onSaved: () => Promise<void>
  onClose: () => void
  /** Told whether the text differs from what the composer opened with. */
  onDirty?: (dirty: boolean) => void
}

/** Writes a comment into the owner's pending review. Nothing reaches the agent until submit. */
export function Composer({ anchor, draft, onSaved, onClose, onDirty }: Props) {
  const [text, setText] = useState(draft?.text ?? '')
  const [error, setError] = useState<string | null>(null)

  async function act(action: () => Promise<void>) {
    try {
      await action()
      await onSaved()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const title = !draft
    ? `New comment on ${anchor}`
    : draft.thread_id
      ? `Draft reply on ${anchor}`
      : `Draft on ${anchor}`
  return (
    <div
      role="dialog"
      aria-label={title}
      className="thread-card"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="card-top">
        <code>{anchor}</code>
        {draft && <span className="badge">Draft</span>}
        <button className="icon" aria-label="Close" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="card-body">
        <textarea
          aria-label="Comment"
          placeholder="Your comment…"
          autoFocus
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            onDirty?.(e.target.value !== (draft?.text ?? ''))
          }}
        />
        {error && <p className="error">{error}</p>}
        <div className="actions">
          {draft ? (
            <>
              <button
                disabled={!text.trim()}
                onClick={() => void act(() => editDraft(draft.id, text))}
              >
                Save draft
              </button>
              <button onClick={() => void act(() => discardDraft(draft.id))}>Discard draft</button>
            </>
          ) : (
            <button
              disabled={!text.trim()}
              onClick={() => void act(() => draftComment(anchor, text))}
            >
              Add to review
            </button>
          )}
          <button onClick={onClose}>Cancel</button>
        </div>
        {!draft && (
          <p className="hint">Saved as a draft. The agent sees it when you submit the review.</p>
        )}
      </div>
    </div>
  )
}
