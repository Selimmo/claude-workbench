import { useState } from 'react'

import type { Thread } from '../threads'
import { useSpot } from './position'

const count = (n: number) => `${n} message${n === 1 ? '' : 's'}`

export function Pin({ thread, onOpen }: { thread: Thread; onOpen: () => void }) {
  const spot = useSpot(thread.anchor)
  const [hover, setHover] = useState(false)
  if (spot === null) return null
  const first = thread.messages[0]?.text ?? ''
  return (
    <div className="pin-spot" style={{ top: spot.top, left: spot.left }}>
      <button
        className="pin"
        data-resolved={thread.resolved}
        aria-label={`${count(thread.messages.length)} on ${thread.anchor}`}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        onClick={() => {
          setHover(false) // the card replaces the preview
          onOpen()
        }}
      >
        {thread.messages.length}
      </button>
      {hover && (
        <div role="tooltip" className="pin-tip">
          {first.length > 80 ? `${first.slice(0, 80)}…` : first}
        </div>
      )}
    </div>
  )
}
