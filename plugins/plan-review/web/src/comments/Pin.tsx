import { useState } from 'react'

import { useSpot } from './position'

interface Props {
  anchor: string
  /** What the pin shows: a thread's message count, or a mark for a draft. */
  badge: string
  label: string
  preview: string
  draft?: boolean
  /** Pixels to the left of the anchor's corner, so pins on one element don't stack. */
  offset?: number
  onOpen: () => void
}

export function Pin({ anchor, badge, label, preview, draft = false, offset = 0, onOpen }: Props) {
  const spot = useSpot(anchor)
  const [hover, setHover] = useState(false)
  if (spot === null) return null
  return (
    <div className="pin-spot" style={{ top: spot.top, left: spot.left - offset }}>
      <button
        className="pin"
        data-draft={draft}
        aria-label={label}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        onClick={() => {
          setHover(false) // the card replaces the preview
          onOpen()
        }}
      >
        {badge}
      </button>
      {hover && (
        <div role="tooltip" className="pin-tip">
          {preview.length > 80 ? `${preview.slice(0, 80)}…` : preview}
        </div>
      )}
    </div>
  )
}
