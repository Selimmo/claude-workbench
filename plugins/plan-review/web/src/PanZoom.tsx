import {
  type MouseEvent,
  type PointerEvent,
  type ReactNode,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'

import {
  type Point,
  type Size,
  type View,
  centerOn,
  fitAll,
  fill,
  showsAll,
  visibleArea,
  zoomAt,
} from './fit'

const MAX_SCALE = 3
/** A press that moves less than this is a click (e.g. to comment), not a drag. */
const DRAG_THRESHOLD = 4
/** Clicks on these do their own job, so they never start a drag. */
const CONTROLS = 'button, a, input, textarea, select, .minimap'

function capture(element: Element, pointerId: number) {
  // Keeps a drag going when the pointer leaves the element. Throws if the pointer is no
  // longer active (and doesn't exist in jsdom); the drag then still works while inside.
  try {
    element.setPointerCapture(pointerId)
  } catch {
    // nothing to do
  }
}

/** A simplified picture of the content, drawn in the minimap. */
export interface Overview {
  boxes: (Point & Size)[]
  lines: Point[][]
}

interface Props {
  width: number
  height: number
  overview: Overview
  children: ReactNode
}

/**
 * Fills its container. Starts by fitting the whole diagram; drag to pan, wheel (or pinch)
 * to zoom around the pointer. While part of the diagram is off screen, a minimap shows the
 * whole of it with the visible area outlined, and clicking or dragging there moves the view.
 */
export function PanZoom({ width, height, overview, children }: Props) {
  const viewport = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  const [view, setView] = useState<View>({ x: 0, y: 0, scale: 1 })
  // Once the owner pans or zooms, a resize no longer re-fits and throws their place away.
  const [touched, setTouched] = useState(false)
  const press = useRef<{ start: Point; last: Point; dragging: boolean } | null>(null)
  const swallowClick = useRef(false)
  const content = { width, height }
  const minScale = Math.min(0.2, fitAll(size, content).scale)

  useLayoutEffect(() => {
    const box = viewport.current
    if (!box) return
    const measure = () => setSize({ width: box.clientWidth, height: box.clientHeight })
    measure()
    if (typeof ResizeObserver !== 'function') return // jsdom
    const observer = new ResizeObserver(measure)
    observer.observe(box)
    return () => observer.disconnect()
  }, [])

  // A new diagram (or a re-laid-out one) starts from the whole picture again.
  // oxlint-disable-next-line react/set-state-in-effect
  useLayoutEffect(() => setTouched(false), [width, height])

  useLayoutEffect(() => {
    // Measuring the DOM, then positioning from it, is what layout effects are for.
    // oxlint-disable-next-line react/set-state-in-effect
    if (!touched) setView(fitAll(size, { width, height }))
  }, [touched, size, width, height])

  useEffect(() => {
    // React's onWheel is passive, so it cannot stop the browser zooming the whole page
    // on a pinch; a native listener can.
    const box = viewport.current
    if (!box) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const rect = box.getBoundingClientRect()
      const at = { x: event.clientX - rect.left, y: event.clientY - rect.top }
      setTouched(true)
      setView((v) => {
        const wanted = v.scale * Math.exp(-event.deltaY / 500)
        return zoomAt(v, at, Math.min(MAX_SCALE, Math.max(minScale, wanted)))
      })
    }
    box.addEventListener('wheel', onWheel, { passive: false })
    return () => box.removeEventListener('wheel', onWheel)
  }, [minScale])

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    swallowClick.current = false
    if (event.button !== 0 || (event.target as Element).closest(CONTROLS)) return
    const at = { x: event.clientX, y: event.clientY }
    press.current = { start: at, last: at, dragging: false }
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const current = press.current
    if (!current) return
    const at = { x: event.clientX, y: event.clientY }
    if (!current.dragging) {
      const distance = Math.hypot(at.x - current.start.x, at.y - current.start.y)
      if (distance < DRAG_THRESHOLD) return
      current.dragging = true
      capture(event.currentTarget, event.pointerId)
      setTouched(true)
    }
    const { last } = current
    current.last = at
    setView((v) => ({ ...v, x: v.x + at.x - last.x, y: v.y + at.y - last.y }))
  }

  function onPointerUp() {
    swallowClick.current = press.current?.dragging ?? false
    press.current = null
  }

  function onClickCapture(event: MouseEvent) {
    // The click that ends a drag must not also comment on what is under the pointer.
    if (!swallowClick.current) return
    swallowClick.current = false
    event.stopPropagation()
    event.preventDefault()
  }

  function show(next: View, keep: boolean) {
    setTouched(keep)
    setView(next)
  }

  const middle = { x: size.width / 2, y: size.height / 2 }
  return (
    <div
      ref={viewport}
      className="viewport"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => (press.current = null)}
      onClickCapture={onClickCapture}
    >
      <div
        className="canvas"
        style={{
          width,
          height,
          transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
          // Lets click targets (e.g. around arrows) keep their on-screen size at any zoom.
          ['--zoom' as string]: view.scale,
        }}
      >
        {children}
      </div>
      <div className="view-controls" role="toolbar" aria-label="View">
        <button title="Show the whole diagram" onClick={() => show(fitAll(size, content), false)}>
          Fit all
        </button>
        <button
          title="Fill the window's height (or width) and pan along the rest"
          onClick={() => show(fill(size, content), true)}
        >
          Fill
        </button>
        <button onClick={() => show(zoomAt(view, middle, 1), true)}>100%</button>
        <span className="zoom-level">{Math.round(view.scale * 100)}%</span>
      </div>
      {size.width > 0 && !showsAll(view, size, content) && (
        <Minimap
          content={content}
          overview={overview}
          visible={visibleArea(view, size)}
          onCenter={(point) => show(centerOn(view, size, point), true)}
        />
      )}
    </div>
  )
}

const MINIMAP_WIDTH = 220
const MINIMAP_HEIGHT = 150

function Minimap({
  content,
  overview,
  visible,
  onCenter,
}: {
  content: Size
  overview: Overview
  visible: Point & Size
  onCenter: (point: Point) => void
}) {
  const scale = Math.min(MINIMAP_WIDTH / content.width, MINIMAP_HEIGHT / content.height)
  const width = content.width * scale
  const height = content.height * scale

  function center(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    onCenter({ x: (event.clientX - rect.left) / scale, y: (event.clientY - rect.top) / scale })
  }

  return (
    <div
      className="minimap"
      role="img"
      aria-label="Overview of the whole diagram"
      style={{ width, height }}
      onPointerDown={(event) => {
        capture(event.currentTarget, event.pointerId)
        center(event)
      }}
      onPointerMove={(event) => event.buttons === 1 && center(event)}
    >
      <svg width={width} height={height} viewBox={`0 0 ${content.width} ${content.height}`}>
        {overview.lines.map((points, i) => (
          <polyline key={i} points={points.map((p) => `${p.x},${p.y}`).join(' ')} />
        ))}
        {overview.boxes.map((b, i) => (
          <rect key={i} x={b.x} y={b.y} width={b.width} height={b.height} />
        ))}
        <rect
          className="minimap-view"
          x={visible.x}
          y={visible.y}
          width={visible.width}
          height={visible.height}
        />
      </svg>
    </div>
  )
}
