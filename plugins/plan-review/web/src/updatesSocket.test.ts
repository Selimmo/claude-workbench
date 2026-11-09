import { connectUpdates } from './updatesSocket'

class Socket {
  static all: Socket[] = []
  onmessage: ((event: { data: string }) => void) | null = null
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  closed = false
  readonly url: string
  constructor(url: string) {
    this.url = url
    Socket.all.push(this)
  }
  close() {
    this.closed = true
  }
  drop() {
    this.onclose?.()
  }
}

beforeEach(() => {
  Socket.all = []
  vi.useFakeTimers()
  vi.stubGlobal('WebSocket', Socket)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('a dropped updates socket reconnects', () => {
  const onReopened = vi.fn()
  const onMessage = vi.fn()
  connectUpdates('ws://x/api/updates', onMessage, onReopened)
  expect(Socket.all).toHaveLength(1)

  Socket.all[0]!.onopen?.()
  expect(onReopened).not.toHaveBeenCalled() // the first open is not a reopening
  Socket.all[0]!.drop()
  vi.advanceTimersByTime(1000)

  expect(Socket.all).toHaveLength(2)
  expect(onReopened).not.toHaveBeenCalled() // not until the new socket is open
  Socket.all[1]!.onopen?.()
  expect(onReopened).toHaveBeenCalledTimes(1)
  Socket.all[1]!.onmessage?.({ data: '{"type":"plan_changed"}' })
  expect(onMessage).toHaveBeenCalledWith({ type: 'plan_changed' })
})

test('a socket closed on purpose stays closed', () => {
  const stop = connectUpdates('ws://x/api/updates', vi.fn(), vi.fn())

  stop()
  Socket.all[0]!.drop()
  vi.advanceTimersByTime(60_000)

  expect(Socket.all).toHaveLength(1)
  expect(Socket.all[0]!.closed).toBe(true)
})

test('stopping during the pause after a drop opens no new socket', () => {
  const stop = connectUpdates('ws://x/api/updates', vi.fn(), vi.fn())
  Socket.all[0]!.drop()
  vi.advanceTimersByTime(500) // within the pause

  stop()
  vi.advanceTimersByTime(60_000)

  expect(Socket.all).toHaveLength(1)
})
