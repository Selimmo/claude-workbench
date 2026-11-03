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

type Box = Pick<DOMRect, 'left' | 'top' | 'right' | 'bottom'>

/**
 * The top-right corner of an element's box, or null when that corner lies outside `clip`
 * (the diagram viewport around it): a panned-away element must not leave its pin floating
 * over other parts of the page.
 */
export function spotOf(box: Box, clip: Box | null): Spot | null {
  const spot = { top: box.top, left: box.right }
  if (!clip) return spot
  const inside =
    spot.left >= clip.left &&
    spot.left <= clip.right &&
    spot.top >= clip.top &&
    spot.top <= clip.bottom
  return inside ? spot : null
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
      const element = elementFor(anchor)
      const clip = element?.closest('.viewport')?.getBoundingClientRect() ?? null
      setSpot((old) => {
        const next = element ? spotOf(element.getBoundingClientRect(), clip) : null
        return old?.top === next?.top && old?.left === next?.left ? old : next
      })
      frame = nextFrame(track) as number
    }
    track()
    return () => cancelFrame(frame)
  }, [anchor])
  return spot
}
