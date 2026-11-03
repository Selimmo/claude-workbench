import { act, fireEvent, render, screen } from '@testing-library/react'

import { App } from './App'
import { FakeServer, draft, thread } from './test/fakeServer'

function element(id: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-element-id="${CSS.escape(id)}"]`)
  if (!found) throw new Error(`no element ${id}`)
  return found
}

let server: FakeServer

beforeEach(() => {
  server = new FakeServer()
  server.install()
})

afterEach(() => vi.unstubAllGlobals())

async function open() {
  render(<App />)
  await screen.findByRole('tablist')
}

test('Approve is disabled while threads are unresolved, saying how many', async () => {
  server.threads = [thread('t-1', 'risk:1', 'Hmm'), thread('t-2', 'tab:files', 'Also')]
  await open()

  const approve = await screen.findByRole('button', { name: 'Approve plan' })
  expect(approve).toBeDisabled()
  expect(screen.getByText('Resolve 2 threads to approve')).toBeInTheDocument()
})

test('Approve is disabled while drafts are unsent, saying how many', async () => {
  server.drafts = [draft('d-1', 'risk:1', 'Hmm')]
  await open()

  const approve = await screen.findByRole('button', { name: 'Approve plan' })
  await vi.waitFor(() => expect(approve).toBeDisabled())
  expect(screen.getByText('Submit or discard 1 draft to approve')).toBeInTheDocument()
})

test('approving confirms it and makes the page read-only', async () => {
  server.threads = [{ ...thread('t-1', 'risk:1', 'Done'), resolved: true }]
  await open()

  fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }))

  expect(await screen.findByText(/Approved/)).toBeInTheDocument()
  expect(server.calls).toContainEqual({ method: 'POST', url: '/api/approve', body: null })
  expect(screen.queryByRole('button', { name: 'Comment on this tab' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve plan' })).not.toBeInTheDocument()
})

test('an already approved plan opens read-only', async () => {
  server.approved = true
  await open()

  expect(await screen.findByText(/Approved/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Comment on this tab' })).not.toBeInTheDocument()
})

test('a revised plan re-renders in place, keeps the tab and marks what changed', async () => {
  await open()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))

  const revised = structuredClone(server.plan) as { tests: { id: string; behaviour: string }[] }
  revised.tests[0].behaviour = 'With no hints given, the first hint is a NUDGE'
  server.plan = revised
  await act(async () => server.push({ type: 'plan_changed' }))

  expect(
    await screen.findByText('With no hints given, the first hint is a NUDGE'),
  ).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Tests' })).toHaveAttribute('aria-selected', 'true')
  expect(document.querySelector('[data-element-id="test:1"]')).toHaveAttribute(
    'data-revised',
    'true',
  )
  expect(screen.getByRole('status')).toHaveTextContent('Plan revised: 1 element changed')

  fireEvent.click(screen.getByRole('button', { name: 'Mark as seen' }))
  expect(document.querySelector('[data-revised]')).toBeNull()
})

test('in a read-only (approved) plan, clicking an element opens no composer', async () => {
  server.approved = true
  await open()
  await screen.findByText(/Approved/)

  fireEvent.click(element('header:title'))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('in a read-only (approved) plan, leftover drafts show no pins', async () => {
  server.approved = true
  server.drafts = [draft('d-1', 'header:title', 'Late thought')]
  await open()
  await screen.findByText(/Approved/)

  expect(screen.queryByRole('button', { name: 'Draft on header:title' })).not.toBeInTheDocument()
})
