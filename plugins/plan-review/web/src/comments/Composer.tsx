import { useState } from 'react'

import { AnchorTitle } from './AnchorTitle'
import { discardDraft, draftComment, editDraft } from '../api'
import type { AnchorName } from '../anchorNames'
import type { Draft } from '../threads'

interface Props {
  anchor: string
  /** How the anchor reads to the owner; the card's top shows it, with the raw id under it. */
  name: AnchorName
  /** Set to edit a pending draft; otherwise this writes a new comment on `anchor`. */
  draft?: Draft
  onSaved: () => Promise<void>
  onClose: () => void
  /** Told whether the text differs from what the composer opened with. */
  onDirty?: (dirty: boolean) => void
}

/** Writes a comment into the owner's pending review. Nothing reaches the agent until submit. */
export function Composer({ anchor, name, draft, onSaved, onClose, onDirty }: Props) {
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
    ? `New comment on ${name.full}`
    : draft.thread_id
      ? `Draft reply on ${name.full}`
      : `Draft on ${name.full}`
  return (
    <div
      role="dialog"
      aria-label={title}
      className="thread-card"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="card-top">
        <AnchorTitle name={name} />
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
