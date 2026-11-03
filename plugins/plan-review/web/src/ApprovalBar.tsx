import { useState } from 'react'

interface Props {
  approved: boolean
  unresolved: number
  /** Unsent review comments: approving would silently drop them, so they block it too. */
  drafts: number
  onApprove: () => Promise<void>
}

export function ApprovalBar({ approved, unresolved, drafts, onApprove }: Props) {
  const [error, setError] = useState<string | null>(null)

  if (approved)
    return (
      <p className="approval approved" role="note">
        ✓ Approved: handed to the implementer. This page is now read-only.
      </p>
    )
  return (
    <div className="approval">
      <button
        className="primary"
        disabled={unresolved > 0 || drafts > 0}
        onClick={() =>
          void onApprove().catch((e: unknown) =>
            setError(e instanceof Error ? e.message : String(e)),
          )
        }
      >
        Approve plan
      </button>
      {unresolved > 0 && (
        <span className="hint">
          Resolve {unresolved} thread{unresolved === 1 ? '' : 's'} to approve
        </span>
      )}
      {drafts > 0 && (
        <span className="hint">
          Submit or discard {drafts} draft{drafts === 1 ? '' : 's'} to approve
        </span>
      )}
      {error && <span className="error">{error}</span>}
    </div>
  )
}
