import { useState } from 'react'

import type { ClassDetails as Details, MemberGroup, MemberLine } from './diagram'
import { Prose } from './Prose'

interface Props {
  details: Details
  /** Null while the plan is approved: the popup only shows. */
  onComment: ((anchor: string) => void) | null
  onClose: () => void
}

/** Only the label a screen reader reads out for each box, like "New members, 2". */
const GROUP_LABELS: Record<MemberGroup['status'], string> = {
  added: 'New',
  modified: 'Changed',
  removed: 'Removed',
}

type OnComment = Props['onComment']

/** A small speech-bubble button at the right end of a line; shown on hover or Tab by the stylesheet. */
function CommentIcon({ anchor, onComment }: { anchor: string; onComment: (a: string) => void }) {
  return (
    <button
      className="comment-icon"
      aria-label={`Comment on ${anchor}`}
      title="Comment"
      onClick={() => onComment(anchor)}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    </button>
  )
}

interface RowProps {
  line: MemberLine
  removed: boolean
  open: boolean
  onToggle: () => void
  onComment: OnComment
}

function MemberRow({ line, removed, open, onToggle, onComment }: RowProps) {
  const name = <code className="member-name">{removed ? <s>{line.name}</s> : line.name}</code>
  return (
    <li className="member-line">
      <div className="member-head">
        {line.signature ? (
          <button className="member-toggle" aria-expanded={open} onClick={onToggle}>
            {name}
            <span className="arrow" aria-hidden="true">
              ▸
            </span>
          </button>
        ) : (
          <span>
            {name}
            {line.type && <code className="member-type">{line.type}</code>}
          </span>
        )}
        {onComment && <CommentIcon anchor={line.id} onComment={onComment} />}
      </div>
      {open && line.signature && <code className="member-signature">{line.signature}</code>}
      {line.note && (
        <p className="member-note">
          <Prose text={line.note} />
        </p>
      )}
    </li>
  )
}

/** What a class box leaves out: full signatures, what this plan changes, and the comment icons. */
export function ClassDetails({ details, onComment, onClose }: Props) {
  const [openMember, setOpenMember] = useState<string | null>(null)
  const [showUnchanged, setShowUnchanged] = useState(false)
  const rows = (lines: MemberLine[], removed: boolean) =>
    lines.map((line) => (
      <MemberRow
        key={line.id}
        line={line}
        removed={removed}
        open={openMember === line.id}
        onToggle={() => setOpenMember(openMember === line.id ? null : line.id)}
        onComment={onComment}
      />
    ))
  return (
    <div
      role="dialog"
      aria-label={`Details of ${details.title}`}
      className="thread-card class-details"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div className="card-top">
        <h2 className="details-title" data-status={details.status}>
          <strong>{details.name}</strong>
          {details.bases.length > 0 && <span className="bases">{details.bases.join(', ')}</span>}
        </h2>
        <span className="kind">{details.kind}</span>
        {onComment && <CommentIcon anchor={details.id} onComment={onComment} />}
        <button className="icon" aria-label="Close" autoFocus onClick={onClose}>
          ×
        </button>
      </div>
      <div className="card-body">
        {details.note && (
          <p className="details-note">
            <Prose text={details.note} />
          </p>
        )}
        {details.groups.map((group) => (
          <ul
            key={group.status}
            className="member-group"
            data-status={group.status}
            aria-label={`${GROUP_LABELS[group.status]} members, ${group.members.length}`}
          >
            {rows(group.members, group.status === 'removed')}
          </ul>
        ))}
        {details.unchanged.length > 0 &&
          (showUnchanged ? (
            <ul
              className="member-group"
              aria-label={`Unchanged members, ${details.unchanged.length}`}
            >
              {rows(details.unchanged, false)}
            </ul>
          ) : (
            <button className="link" onClick={() => setShowUnchanged(true)}>
              Show {details.unchanged.length} unchanged
            </button>
          ))}
      </div>
    </div>
  )
}
