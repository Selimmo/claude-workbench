import { useState } from 'react'

import { discardDraft, submitReview } from '../api'
import type { Draft } from '../threads'
import type { Note } from './Toast'

interface Props {
  drafts: Draft[]
  onChanged: () => Promise<void>
  onEdit: (draft: Draft) => void
  /** Tells the owner how submitting went (the panel itself disappears on success). */
  onNotify: (note: Note) => void
}

const comments = (n: number) => `${n} comment${n === 1 ? '' : 's'}`

/** The owner's pending review, like a pull request's: edit or discard, then submit it all. */
export function ReviewPanel({ drafts, onChanged, onEdit, onNotify }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function act(action: () => Promise<void>) {
    setError(null)
    setBusy(true)
    try {
      await action()
      await onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    // Reported by toast only: on success this panel disappears, and one message is enough.
    setBusy(true)
    try {
      const sent = await submitReview() // the server's count: it may include another tab's
      await onChanged()
      onNotify({ kind: 'ok', text: `Review sent (${comments(sent)})` })
    } catch (e) {
      const reason = e instanceof Error ? e.message : String(e)
      onNotify({ kind: 'error', text: `Review not sent: ${reason}` })
    } finally {
      setBusy(false)
    }
  }

  if (drafts.length === 0) return null
  return (
    <section className="review-panel" aria-label="Your review">
      <h3>Your review</h3>
      <button className="primary" disabled={busy} onClick={() => void submit()}>
        Submit review ({drafts.length})
      </button>
      <p className="hint">Claude sees these comments only when you submit.</p>
      {error && <p className="error">{error}</p>}
      <ul>
        {drafts.map((d) => (
          <li key={d.id}>
            <code>{d.anchor}</code>
            {d.thread_id && <span className="kind"> reply</span>}
            <span className="text">{d.text}</span>
            <span className="draft-actions">
              <button className="link" onClick={() => onEdit(d)}>
                Edit
              </button>
              <button className="link" onClick={() => void act(() => discardDraft(d.id))}>
                Discard
              </button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
