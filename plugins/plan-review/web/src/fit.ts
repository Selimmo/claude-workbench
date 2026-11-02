// The starting view of a pan-and-zoom diagram.

export interface View {
  x: number
  y: number
  scale: number
}

interface Size {
  width: number
  height: number
}

/** The starting view: shrink to fit the viewport, but never enlarge past full size. */
export function fitView(viewport: Size, content: Size): View {
  if (viewport.width === 0 || viewport.height === 0) return { x: 0, y: 0, scale: 1 }
  const scale = Math.min(1, viewport.width / content.width, viewport.height / content.height)
  return { x: 0, y: 0, scale }
}
