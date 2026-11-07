import type { ClassDetails as Details } from './diagram'

interface Props {
  details: Details
  /** Null while the plan is approved: the popup only shows. */
  onComment: ((anchor: string) => void) | null
  onClose: () => void
}

/** What a class box leaves out: full signatures, what this plan changes, and Comment buttons. */
export function ClassDetails({ details, onComment, onClose }: Props) {
  const comment = (anchor: string) =>
    onComment && (
      <button
        className="link"
        aria-label={`Comment on ${anchor}`}
        onClick={() => onComment(anchor)}
      >
        Comment
      </button>
    )
  return (
    <div
      role="dialog"
      aria-label={`Details of ${details.title}`}
      className="thread-card class-details"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="card-top">
        <strong>{details.title}</strong>
        <span className="badge">{details.kind}</span>
        <span className="badge">{details.status}</span>
        {comment(details.id)}
        <button className="icon" aria-label="Close" autoFocus onClick={onClose}>
          ×
        </button>
      </div>
      {details.note && <p>{details.note}</p>}
      <ul className="member-details">
        {details.members.map((m) => (
          <li key={m.id} data-status-word={m.status}>
            <code>{m.signature}</code> <span className="badge">{m.status}</span>
            {comment(m.id)}
            {m.note && <p>{m.note}</p>}
          </li>
        ))}
      </ul>
    </div>
  )
}
