// Pins and cards follow their element through pan, zoom, scroll and re-layout by
// re-reading its on-screen box every animation frame.

import { useEffect, useState } from 'react'

export interface Spot {
  top: number
  left: number
}

export function elementFor(anchor: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[data-element-id="${CSS.escape(anchor)}"]`)
}

const nextFrame = (callback: () => void) =>
  typeof requestAnimationFrame === 'function'
    ? requestAnimationFrame(callback)
    : setTimeout(callback, 16)
const cancelFrame = (id: number) =>
  typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame(id) : clearTimeout(id)

/** The top-right corner of the anchor's element, in viewport coordinates; null if not shown. */
export function useSpot(anchor: string): Spot | null {
  const [spot, setSpot] = useState<Spot | null>(null)
  useEffect(() => {
    let frame = 0
    const track = () => {
      const box = elementFor(anchor)?.getBoundingClientRect()
      setSpot((old) => {
        const next = box ? { top: box.top, left: box.right } : null
        return old?.top === next?.top && old?.left === next?.left ? old : next
      })
      frame = nextFrame(track) as number
    }
    track()
    return () => cancelFrame(frame)
  }, [anchor])
  return spot
}
