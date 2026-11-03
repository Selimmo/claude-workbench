import { useEffect } from 'react'

export interface Note {
  kind: 'ok' | 'error'
  text: string
}

/** A short note at the bottom: success fades by itself, an error stays until closed. */
export function Toast({
  note,
  onClose,
  duration = 5000,
}: {
  note: Note
  onClose: () => void
  duration?: number
}) {
  useEffect(() => {
    if (note.kind === 'error') return
    const timer = setTimeout(onClose, duration)
    return () => clearTimeout(timer)
  }, [note, onClose, duration])
  return (
    <div
      role={note.kind === 'ok' ? 'status' : 'alert'}
      aria-label="Notification"
      className="toast"
      data-kind={note.kind}
    >
      <span>{note.text}</span>
      <button className="icon" aria-label="Dismiss" onClick={onClose}>
        ×
      </button>
    </div>
  )
}
