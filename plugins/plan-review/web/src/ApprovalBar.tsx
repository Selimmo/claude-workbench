import { useState } from 'react'

interface Props {
  approved: boolean
  unresolved: number
  onApprove: () => Promise<void>
}

export function ApprovalBar({ approved, unresolved, onApprove }: Props) {
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
        disabled={unresolved > 0}
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
      {error && <span className="error">{error}</span>}
    </div>
  )
}
