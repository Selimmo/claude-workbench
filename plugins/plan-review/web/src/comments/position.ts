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
 * Where an element's pin sits (`at`, default the top-right corner of its box), or null when
 * that point lies outside `clip` (the diagram viewport around it): a panned-away element
 * must not leave its pin floating over other parts of the page.
 */
export function spotOf(box: Box, clip: Box | null, at?: Spot): Spot | null {
  const spot = at ?? { top: box.top, left: box.right }
  if (!clip) return spot
  const inside =
    spot.left >= clip.left &&
    spot.left <= clip.right &&
    spot.top >= clip.top &&
    spot.top <= clip.bottom
  return inside ? spot : null
}

/**
 * A point on the shape's own outline near its top right. A diamond's box corner and a pill's
 * box corner are empty space; a rectangle's is on the shape.
 */
export function outlineSpot(shape: string | undefined, box: Box): Spot {
  const width = box.right - box.left
  const height = box.bottom - box.top
  if (shape === 'decision') {
    // The middle of the edge from the top point to the right point.
    return { top: box.top + height / 4, left: box.left + (3 * width) / 4 }
  }
  if (shape === 'start' || shape === 'end') {
    // The right end is a half circle: take its point at 45 degrees, up and to the right.
    const radius = height / 2
    return {
      top: box.top + radius - radius * Math.SQRT1_2,
      left: box.right - radius + radius * Math.SQRT1_2,
    }
  }
  return { top: box.top, left: box.right }
}

interface XY {
  x: number
  y: number
}

/** The point halfway along a line's length. */
export function midpoint(points: XY[]): XY {
  const lengths = points.slice(1).map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y))
  let left = lengths.reduce((sum, n) => sum + n, 0) / 2
  for (const [i, length] of lengths.entries()) {
    if (left <= length) {
      const t = length === 0 ? 0 : left / length
      return {
        x: points[i].x + (points[i + 1].x - points[i].x) * t,
        y: points[i].y + (points[i + 1].y - points[i].y) * t,
      }
    }
    left -= length
  }
  return points[0]
}

/** The midpoint of a drawn line, in viewport coordinates; null when it cannot be placed. */
export function lineSpot(line: SVGPathElement): Spot | null {
  const matrix = line.getScreenCTM?.()
  const numbers = (line.getAttribute('d') ?? '').match(/-?\d+(?:\.\d+)?/g)
  if (!matrix || !numbers || numbers.length < 2) return null
  const points: XY[] = []
  for (let i = 0; i + 1 < numbers.length; i += 2) {
    points.push({ x: Number(numbers[i]), y: Number(numbers[i + 1]) })
  }
  const { x, y } = midpoint(points)
  return {
    top: matrix.b * x + matrix.d * y + matrix.f,
    left: matrix.a * x + matrix.c * y + matrix.e,
  }
}

/** Where the pin of `element` is drawn: on the outline of a flowchart shape or line. */
export function pinSpot(element: Element, box: Box): Spot {
  const flowLine = element.hasAttribute('data-flow')
    ? element.querySelector<SVGPathElement>('path.line')
    : null
  const onLine = flowLine ? lineSpot(flowLine) : null
  return onLine ?? outlineSpot(element.getAttribute('data-shape') ?? undefined, box)
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
        const box = element?.getBoundingClientRect()
        const next = element && box ? spotOf(box, clip, pinSpot(element, box)) : null
        return old?.top === next?.top && old?.left === next?.left ? old : next
      })
      frame = nextFrame(track) as number
    }
    track()
    return () => cancelFrame(frame)
  }, [anchor])
  return spot
}
