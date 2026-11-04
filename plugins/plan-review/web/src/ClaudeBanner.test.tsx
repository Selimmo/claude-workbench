import { act, fireEvent, render, screen } from '@testing-library/react'

import { App } from './App'
import { FakeServer, draft } from './test/fakeServer'

let server: FakeServer

beforeEach(() => {
  // Only the clock is faked; promises and Testing Library's polling keep running.
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'], shouldAdvanceTime: true })
  server = new FakeServer()
  server.install()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

async function open() {
  render(<App />)
  await screen.findByRole('tablist')
}

const banner = () => screen.getByRole('status', { name: 'Claude' })
const later = (ms: number) => act(async () => void (await vi.advanceTimersByTimeAsync(ms)))
const working = { text: 'Answering questions', done: false, at: '2026-11-04T10:00:30Z' }

async function submitReview() {
  server.drafts = [draft('d-1', 'risk:1', 'Too vague')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: 'Submit review (1)' }))
  return screen.findByRole('status', { name: 'Claude' })
}

test('submitting a review shows that the page is waiting for Claude', async () => {
  const waiting = await submitReview()

  expect(waiting).toHaveTextContent('waiting')
  expect(waiting).toHaveAttribute('data-state', 'waiting')
})

test('with no status for 120 s the banner turns red with Resend', async () => {
  await submitReview()

  await later(119_000)
  expect(banner()).toHaveAttribute('data-state', 'waiting')
  await later(2_000)

  expect(banner()).toHaveTextContent('No response from Claude yet')
  expect(banner()).toHaveAttribute('data-state', 'no-response')
  expect(screen.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
})

test('a status within 120 s means no red banner', async () => {
  await submitReview()
  await later(30_000)

  server.status = working
  server.lastEvent = { ...server.lastEvent!, answered: true }
  await act(async () => server.push({ type: 'status_changed' }))
  await later(200_000)

  expect(await screen.findByText('Answering questions')).toBeInTheDocument()
  expect(banner()).toHaveAttribute('data-state', 'status')
  expect(screen.queryByRole('button', { name: 'Resend' })).not.toBeInTheDocument()
})

test('Resend asks the server to send again and waits again', async () => {
  await submitReview()
  await later(121_000)

  fireEvent.click(screen.getByRole('button', { name: 'Resend' }))

  await vi.waitFor(() => expect(banner()).toHaveAttribute('data-state', 'waiting'))
  expect(server.calls.filter((c) => c.method === 'POST' && c.url === '/api/resend')).toHaveLength(1)
})

test('Resend is disabled while the request is in flight, so a double click sends once', async () => {
  await submitReview()
  await later(121_000)
  let release!: () => void
  server.resendHold = new Promise<void>((resolve) => (release = resolve))

  fireEvent.click(screen.getByRole('button', { name: 'Resend' }))
  fireEvent.click(screen.getByRole('button', { name: 'Resend' }))

  expect(screen.getByRole('button', { name: 'Resend' })).toBeDisabled()
  await act(async () => release())
  await vi.waitFor(() => expect(banner()).toHaveAttribute('data-state', 'waiting'))
  expect(server.calls.filter((c) => c.method === 'POST' && c.url === '/api/resend')).toHaveLength(1)
})

test('Resend after Claude answered shows the status and sends nothing', async () => {
  await submitReview()
  await later(121_000)
  server.status = working // set by Claude, but the page has not been pushed about it yet
  server.lastEvent = { ...server.lastEvent!, answered: true }
  const sentAt = server.lastEvent.sent_at

  fireEvent.click(screen.getByRole('button', { name: 'Resend' }))

  expect(await screen.findByText('Answering questions')).toBeInTheDocument()
  expect(banner()).toHaveAttribute('data-state', 'status')
  expect(server.lastEvent.sent_at).toBe(sentAt)
})

test('a Resend the server refuses leaves the page working', async () => {
  await submitReview()
  await later(121_000)
  server.lastEvent = null // the server now answers 409: nothing was sent

  fireEvent.click(screen.getByRole('button', { name: 'Resend' }))

  await vi.waitFor(() => expect(screen.queryByRole('status', { name: 'Claude' })).toBeNull())
  expect(screen.getByRole('tablist')).toBeInTheDocument()
})

test('a server without the last-event route shows no banner', async () => {
  const handle = vi.mocked(fetch).getMockImplementation()!
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      String(input) === '/api/last-event'
        ? Promise.reject(new TypeError('network'))
        : handle(input, init),
    ),
  )

  await open()

  expect(screen.queryByRole('status', { name: 'Claude' })).toBeNull()
})

test('a reload long after the event shows red at once', async () => {
  server.lastEvent = {
    type: 'approved',
    sent_at: new Date(Date.now() - 600_000).toISOString(),
    answered: false,
  }
  await open()

  expect(await screen.findByText('No response from Claude yet')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
})

test('an approved read-only page still shows the banner and Resend', async () => {
  await open()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }))
  await screen.findByText(/Approved/)
  expect(await screen.findByRole('status', { name: 'Claude' })).toHaveAttribute(
    'data-state',
    'waiting',
  )

  await later(121_000)

  expect(banner()).toHaveAttribute('data-state', 'no-response')
  expect(screen.getByRole('button', { name: 'Resend' })).toBeInTheDocument()
})

test('red is reserved for no response', async () => {
  server.status = working
  await open()
  expect(await screen.findByRole('status', { name: 'Claude' })).toHaveAttribute(
    'data-state',
    'status',
  )

  server.status = { text: 'Done', done: true, at: '2026-11-04T10:05:00Z' }
  await act(async () => server.push({ type: 'status_changed' }))

  await screen.findByText('Done')
  expect(banner()).toHaveAttribute('data-state', 'status')
  expect(banner()).toHaveAttribute('data-done', 'true')
})
