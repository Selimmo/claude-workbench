import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

/**
 * The notices that stay at the top of the window while the page scrolls, on a solid background.
 * Its real height is published as --sticky-head-height, so whatever else sticks or scrolls under
 * it (the decisions list, scroll targets) can stay clear however many notices there are.
 */
export function StickyHead({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const head = ref.current
    if (!head || typeof ResizeObserver === 'undefined') return
    const root = document.documentElement
    const publish = () =>
      root.style.setProperty('--sticky-head-height', `${head.getBoundingClientRect().height}px`)
    publish()
    const observer = new ResizeObserver(publish)
    observer.observe(head)
    return () => {
      observer.disconnect()
      root.style.removeProperty('--sticky-head-height')
    }
  }, [])
  return (
    <div className="sticky-head" ref={ref}>
      {children}
    </div>
  )
}
