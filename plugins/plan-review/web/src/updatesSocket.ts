// The page's push socket (/api/updates), which opens again when it drops.

const RECONNECT_MS = 1000

/**
 * Calls `onMessage` with each pushed message. If the socket drops (the viewer restarted, say),
 * opens a new one after a pause and calls `onReopened`, so the page can read what it missed.
 * Returns a function that closes the socket for good.
 */
export function connectUpdates(
  url: string,
  onMessage: (message: { type: string }) => void,
  onReopened: () => void,
): () => void {
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let current: WebSocket | undefined

  function open(reopening: boolean) {
    const socket = new WebSocket(url)
    current = socket
    socket.onopen = () => {
      if (reopening) onReopened()
    }
    socket.onmessage = (event: MessageEvent<string>) =>
      onMessage(JSON.parse(event.data) as { type: string })
    socket.onclose = () => {
      if (!stopped) timer = setTimeout(() => open(true), RECONNECT_MS)
    }
  }
  open(false)

  return () => {
    stopped = true
    clearTimeout(timer)
    current?.close()
  }
}
