import { useEffect } from 'react'

/**
 * Tag the elements whose ids are in `ids` with data-<name>="true", also those that render
 * later (diagrams lay out async), and untag the rest. `onTagged` runs once per newly
 * tagged element, e.g. to scroll it into view.
 */
export function useMarkElements(
  name: 'revised' | 'focused',
  ids: Set<string>,
  onTagged?: (element: HTMLElement) => void,
) {
  useEffect(() => {
    const mark = () => {
      for (const el of document.querySelectorAll<HTMLElement>('[data-element-id]')) {
        const tagged = ids.has(el.dataset.elementId ?? '')
        if (tagged && el.dataset[name] !== 'true') {
          el.dataset[name] = 'true'
          onTagged?.(el)
        }
        if (!tagged && el.dataset[name] !== undefined) delete el.dataset[name]
      }
    }
    mark()
    const observer = new MutationObserver(mark)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [name, ids, onTagged])
}

/** Outline elements changed by revisions since the owner last marked them seen. */
export const useMarkRevised = (revised: Set<string>) => useMarkElements('revised', revised)
