import { useCallback, useEffect, useState } from 'react'

import { fetchThreads } from './api'
import type { Thread } from './threads'

/** Comment threads, refetched whenever the server says they changed (e.g. Claude replied). */
export function useThreads(): { threads: Thread[]; refresh: () => Promise<void> } {
  const [threads, setThreads] = useState<Thread[]>([])
  const refresh = useCallback(async () => setThreads(await fetchThreads()), [])

  useEffect(() => {
    // Syncing with an external system (the server) is what effects are for.
    // oxlint-disable-next-line react/set-state-in-effect
    void refresh()
    const socket = new WebSocket(`ws://${location.host}/api/updates`)
    socket.onmessage = (event: MessageEvent<string>) => {
      const { type } = JSON.parse(event.data) as { type: string }
      if (type === 'threads_changed') void refresh()
    }
    return () => socket.close()
  }, [refresh])

  return { threads, refresh }
}
