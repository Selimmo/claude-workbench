import { NO_RESPONSE_AFTER_MS, bannerState } from './banner'
import type { ClaudeStatus, LastEvent } from './threads'

const SENT = Date.parse('2026-11-04T10:00:00Z')
const working: ClaudeStatus = {
  text: 'Answering questions',
  done: false,
  at: '2026-11-04T09:00:00Z',
}
const event = (answered: boolean): LastEvent => ({
  type: 'review_submitted',
  sent_at: '2026-11-04T10:00:00Z',
  answered,
})

test('banner waits for Claude right after an event, even if an older status exists', () => {
  expect(bannerState(working, event(false), SENT + 1000)).toEqual({ kind: 'waiting' })
})

test('banner says no response after 120 s', () => {
  expect(NO_RESPONSE_AFTER_MS).toBe(120_000)
  expect(bannerState(null, event(false), SENT + 119_999)).toEqual({ kind: 'waiting' })
  expect(bannerState(null, event(false), SENT + 120_000)).toEqual({ kind: 'no-response' })
})

test('banner shows the status once Claude answered', () => {
  expect(bannerState(working, event(true), SENT + 500_000)).toEqual({
    kind: 'status',
    status: working,
  })
  expect(bannerState(working, null, SENT)).toEqual({ kind: 'status', status: working })
  expect(bannerState(null, null, SENT)).toEqual({ kind: 'none' })
  expect(bannerState(null, event(true), SENT)).toEqual({ kind: 'none' })
})
