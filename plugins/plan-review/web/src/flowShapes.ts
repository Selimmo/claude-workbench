// The sizes of flowchart shapes and where lines meet them. Pure functions, kept apart from
// drawing so each rule has its own test.

import type { DiagramNode } from './diagram'
import type { LaidNode, Point } from './layout'
import { type Measure, wrapLabel } from './measure'

/** A step's text wraps at about this many pixels. */
export const WRAP_WIDTH = 180
export const FLOW_LINE_HEIGHT = 18
export const PAD_X = 16
export const PAD_Y = 10
export const PILL_MIN_HEIGHT = 40
export const TAG_PAD = 8
export const TAG_HEIGHT = 18

export function flowNodeSize(
  node: DiagramNode,
  measure: Measure,
): { width: number; height: number; lines: string[] } {
  const lines = wrapLabel(node.title, WRAP_WIDTH, (t) => measure(t, 'flow'))
  const text = Math.max(...lines.map((l) => measure(l, 'flow')))
  // The text block with its padding: the box of an action.
  const w = text + 2 * PAD_X
  const h = lines.length * FLOW_LINE_HEIGHT + 2 * PAD_Y
  if (node.shape === 'decision') {
    // A diamond whose edges pass through the corners of the padded block.
    return { width: w + 2 * h, height: w / 2 + h, lines }
  }
  if (node.shape === 'start' || node.shape === 'end') {
    // Each round end is a half circle of the pill's height: the text sits between them.
    const height = Math.max(PILL_MIN_HEIGHT, h)
    return { width: text + height, height, lines }
  }
  return { width: w, height: h, lines }
}

export function tagSize(label: string, measure: Measure): { width: number; height: number } {
  return { width: measure(label, 'tag') + 2 * TAG_PAD, height: TAG_HEIGHT }
}

/**
 * Where a line leaving `node` along `away` (a unit step, pointing away from the node) from
 * point `p` on its bounding box meets the shape's outline. ELK routes to the box; the
 * outline of a diamond or a pill is inside it.
 */
function onOutline(node: LaidNode, p: Point, away: Point): Point {
  const cx = node.x + node.width / 2
  const cy = node.y + node.height / 2
  const halfW = node.width / 2
  const halfH = node.height / 2
  if (node.shape === 'decision') {
    if (away.x === 0)
      return { x: p.x, y: cy + Math.sign(away.y) * halfH * (1 - Math.abs(p.x - cx) / halfW) }
    return { x: cx + Math.sign(away.x) * halfW * (1 - Math.abs(p.y - cy) / halfH), y: p.y }
  }
  if (node.shape === 'start' || node.shape === 'end') {
    const flat = halfW - halfH // the straight part: from -flat to +flat around the centre
    if (away.x === 0) {
      // Over the straight part this is the box's edge, as it was.
      const past = Math.max(0, Math.abs(p.x - cx) - flat)
      return { x: p.x, y: cy + Math.sign(away.y) * Math.sqrt(halfH ** 2 - past ** 2) }
    }
    const dy = p.y - cy
    return { x: cx + Math.sign(away.x) * (flat + Math.sqrt(halfH ** 2 - dy ** 2)), y: p.y }
  }
  return p
}

/** The step `from` `p` toward `q`, when that is straight along one axis; otherwise null. */
function straight(p: Point, q: Point): Point | null {
  if (p.x === q.x && p.y !== q.y) return { x: 0, y: q.y - p.y }
  if (p.y === q.y && p.x !== q.x) return { x: q.x - p.x, y: 0 }
  return null
}

/** Moves a line's two ends from the edge of the bounding box onto the shape itself. */
export function clipToOutline(points: Point[], from: LaidNode, to: LaidNode): Point[] {
  if (points.length < 2) return points
  const result = [...points]
  const last = points.length - 1
  const leaving = straight(points[0], points[1])
  if (leaving) result[0] = onOutline(from, points[0], leaving)
  const arriving = straight(points[last], points[last - 1])
  if (arriving) result[last] = onOutline(to, points[last], arriving)
  return result
}

interface Box {
  x: number
  y: number
  width: number
  height: number
}

/** Whether two boxes share some area; boxes that only touch do not. */
export function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
}

/** Whether any tag lies over another tag or over a step. */
export function tagsCollide(tags: Box[], steps: Box[]): boolean {
  return tags.some(
    (tag, i) =>
      tags.slice(i + 1).some((other) => overlaps(tag, other)) ||
      steps.some((step) => overlaps(tag, step)),
  )
}
