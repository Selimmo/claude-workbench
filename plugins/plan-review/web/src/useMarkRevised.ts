import { useEffect } from 'react'

/** Tag revised elements with data-revised, also those that render later (diagrams lay out async). */
export function useMarkRevised(revised: Set<string>) {
  useEffect(() => {
    const mark = () => {
      for (const el of document.querySelectorAll<HTMLElement>('[data-element-id]')) {
        const isRevised = revised.has(el.dataset.elementId ?? '')
        if (isRevised && el.dataset.revised !== 'true') el.dataset.revised = 'true'
        if (!isRevised && el.dataset.revised !== undefined) delete el.dataset.revised
      }
    }
    mark()
    const observer = new MutationObserver(mark)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [revised])
}
