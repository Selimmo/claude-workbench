// The geometry of a pan-and-zoom view: pure functions, so they are tested without a DOM.
// A view maps content point p to screen point p * scale + (x, y), relative to the viewport.

export interface View {
  x: number
  y: number
  scale: number
}

export interface Size {
  width: number
  height: number
}

export interface Point {
  x: number
  y: number
}

/** Small diagrams are enlarged to fill the space, but not so far that text looks bloated. */
export const MAX_FIT_SCALE = 1.5

function centred(viewport: Size, content: Size, scale: number): View {
  return {
    x: (viewport.width - content.width * scale) / 2,
    y: (viewport.height - content.height * scale) / 2,
    scale,
  }
}

const unmeasured = (viewport: Size) => viewport.width === 0 || viewport.height === 0

/** The whole diagram, as large as the viewport allows, centred. */
export function fitAll(viewport: Size, content: Size): View {
  if (unmeasured(viewport)) return { x: 0, y: 0, scale: 1 }
  const scale = Math.min(
    MAX_FIT_SCALE,
    viewport.width / content.width,
    viewport.height / content.height,
  )
  return centred(viewport, content, scale)
}

/**
 * The diagram filling the viewport's tighter side (as tall as it for a wide diagram, as
 * wide as it for a tall one): larger than fit all, read by panning along the other side.
 */
export function fill(viewport: Size, content: Size): View {
  if (unmeasured(viewport)) return { x: 0, y: 0, scale: 1 }
  const scale = Math.min(
    MAX_FIT_SCALE,
    Math.max(viewport.width / content.width, viewport.height / content.height),
  )
  const view = centred(viewport, content, scale)
  // Start at the left or top end of an axis that overflows, rather than its middle.
  return { scale, x: Math.max(0, view.x), y: Math.max(0, view.y) }
}

/** Change the scale while keeping the content under the screen point `at` still. */
export function zoomAt(view: View, at: Point, scale: number): View {
  return {
    scale,
    x: at.x - ((at.x - view.x) * scale) / view.scale,
    y: at.y - ((at.y - view.y) * scale) / view.scale,
  }
}

/** Pan so the content point `point` sits in the middle of the viewport. */
export function centerOn(view: View, viewport: Size, point: Point): View {
  return {
    ...view,
    x: viewport.width / 2 - point.x * view.scale,
    y: viewport.height / 2 - point.y * view.scale,
  }
}

/** The part of the content the viewport shows, in content coordinates. */
export function visibleArea(view: View, viewport: Size): Point & Size {
  return {
    x: -view.x / view.scale,
    y: -view.y / view.scale,
    width: viewport.width / view.scale,
    height: viewport.height / view.scale,
  }
}

const SLACK = 0.5 // px: rounding must not count as "cut off"

export function showsAll(view: View, viewport: Size, content: Size): boolean {
  const area = visibleArea(view, viewport)
  return (
    area.x <= SLACK / view.scale &&
    area.y <= SLACK / view.scale &&
    area.x + area.width >= content.width - SLACK / view.scale &&
    area.y + area.height >= content.height - SLACK / view.scale
  )
}
