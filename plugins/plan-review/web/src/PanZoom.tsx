import {
  type PointerEvent,
  type ReactNode,
  type WheelEvent,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'

import { type View, fitView } from './fit'

const MIN_SCALE = 0.2
const MAX_SCALE = 3

/** Drag to pan, wheel (or pinch) to zoom around the pointer. */
export function PanZoom({
  width,
  height,
  children,
}: {
  width: number
  height: number
  children: ReactNode
}) {
  const [view, setView] = useState<View>({ x: 0, y: 0, scale: 1 })
  const drag = useRef<{ x: number; y: number } | null>(null)
  const viewport = useRef<HTMLDivElement>(null)

  function fit() {
    const box = viewport.current
    setView(
      fitView({ width: box?.clientWidth ?? 0, height: box?.clientHeight ?? 0 }, { width, height }),
    )
  }

  useLayoutEffect(fit, [width, height])

  function onWheel(event: WheelEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const px = event.clientX - box.left
    const py = event.clientY - box.top
    setView((v) => {
      const scale = Math.min(
        MAX_SCALE,
        Math.max(MIN_SCALE, v.scale * Math.exp(-event.deltaY / 500)),
      )
      // Keep the point under the pointer still while zooming.
      return {
        scale,
        x: px - ((px - v.x) * scale) / v.scale,
        y: py - ((py - v.y) * scale) / v.scale,
      }
    })
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest('[data-element-id]')) return // leave clicks to elements
    drag.current = { x: event.clientX, y: event.clientY }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current
    if (!start) return
    drag.current = { x: event.clientX, y: event.clientY }
    setView((v) => ({ ...v, x: v.x + event.clientX - start.x, y: v.y + event.clientY - start.y }))
  }

  return (
    <div
      ref={viewport}
      className="viewport"
      style={{ height: Math.min(Math.max(height, 240), 640) }}
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={() => (drag.current = null)}
    >
      <div
        className="canvas"
        style={{
          width,
          height,
          transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
        }}
      >
        {children}
      </div>
      <button className="reset" onClick={fit}>
        Reset view
      </button>
    </div>
  )
}
