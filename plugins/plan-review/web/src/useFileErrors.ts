import { useCallback, useMemo, useState } from 'react'

/** The broken-file lines of each source (a file's fetch), gathered for one banner. */
export function useFileErrors() {
  const [bySource, setBySource] = useState<Record<string, string[]>>({})
  const report = useCallback(
    (source: string, lines: string[]) => setBySource((old) => ({ ...old, [source]: lines })),
    [],
  )
  const errors = useMemo(() => [...new Set(Object.values(bySource).flat())], [bySource])
  return { errors, report }
}
