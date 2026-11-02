import { act, fireEvent, render, screen, within } from '@testing-library/react'

import { App } from './App'
import { FakeServer, thread } from './test/fakeServer'

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

function element(id: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-element-id="${CSS.escape(id)}"]`)
  if (!found) throw new Error(`no element ${id}`)
  return found
}

test('a thread shows as a pin; hovering previews it; clicking opens the whole thread', async () => {
  server.threads = [
    thread('t-1', 'class:HintPolicy.next_level', 'Why None?', 'It means no hints left.'),
  ]
  await open()

  const pin = await screen.findByRole('button', {
    name: '2 messages on class:HintPolicy.next_level',
  })
  fireEvent.mouseEnter(pin)
  expect(screen.getByRole('tooltip')).toHaveTextContent('Why None?')

  fireEvent.click(pin)
  const card = screen.getByRole('dialog', { name: 'Thread on class:HintPolicy.next_level' })
  expect(
    within(card)
      .getAllByRole('listitem')
      .map((m) => m.textContent),
  ).toEqual(['YouWhy None?', 'ClaudeIt means no hints left.'])
  fireEvent.click(within(card).getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('in comment mode, clicking an element opens a composer that posts a thread on it', async () => {
  await open()
  await screen.findByText('HintPolicy')

  fireEvent.click(screen.getByRole('button', { name: 'Add comment' }))
  fireEvent.click(element('class:Orchestrator.parse_command'))
  const composer = screen.getByRole('dialog', {
    name: 'New comment on class:Orchestrator.parse_command',
  })
  fireEvent.change(within(composer).getByRole('textbox'), { target: { value: 'Keep it?' } })
  fireEvent.click(within(composer).getByRole('button', { name: 'Post' }))

  expect(
    await screen.findByRole('button', { name: '1 message on class:Orchestrator.parse_command' }),
  ).toBeInTheDocument()
  expect(server.calls).toContainEqual({
    method: 'POST',
    url: '/api/threads',
    body: { anchor: 'class:Orchestrator.parse_command', text: 'Keep it?' },
  })
})

test('a thread card can reply, resolve and reopen', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:HintPolicy' }))
  const card = screen.getByRole('dialog')

  fireEvent.change(within(card).getByRole('textbox'), { target: { value: 'Never mind' } })
  fireEvent.click(within(card).getByRole('button', { name: 'Reply' }))
  await within(card).findByText('Never mind')
  fireEvent.click(within(card).getByRole('button', { name: 'Resolve' }))
  await within(card).findByRole('button', { name: 'Reopen' })

  expect(server.calls.map((c) => `${c.method} ${c.url}`)).toEqual(
    expect.arrayContaining(['POST /api/threads/t-1/replies', 'POST /api/threads/t-1/resolve']),
  )
})

test('the tab itself can be commented on, and its threads are listed', async () => {
  await open()

  fireEvent.click(screen.getByRole('button', { name: 'Comment on this tab' }))
  const composer = screen.getByRole('dialog', { name: 'New comment on tab:classes' })
  fireEvent.change(within(composer).getByRole('textbox'), { target: { value: 'Too many classes' } })
  fireEvent.click(within(composer).getByRole('button', { name: 'Post' }))

  expect(await screen.findByRole('button', { name: /Too many classes/ })).toBeInTheDocument()
})

test('orphaned threads are listed on every tab', async () => {
  server.threads = [{ ...thread('t-1', 'class:Gone', 'Where did it go?'), orphaned: true }]
  await open()

  const panel = await screen.findByRole('region', { name: 'Orphaned comments' })
  expect(panel).toHaveTextContent('class:Gone')
  fireEvent.click(screen.getByRole('tab', { name: 'Files' }))
  expect(screen.getByRole('region', { name: 'Orphaned comments' })).toBeInTheDocument()
})

test("Claude's reply, pushed by the server, appears without a reload", async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  await open()
  await screen.findByRole('button', { name: '1 message on class:HintPolicy' })

  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?', 'Yes: HintRules.')]
  await act(async () => server.push({ type: 'threads_changed' }))

  expect(
    await screen.findByRole('button', { name: '2 messages on class:HintPolicy' }),
  ).toBeInTheDocument()
})

test('rows in the table tabs can be commented on too', async () => {
  await open()
  fireEvent.click(screen.getByRole('tab', { name: 'Files' }))

  fireEvent.click(screen.getByRole('button', { name: 'Add comment' }))
  fireEvent.click(element('file:commands'))

  expect(screen.getByRole('dialog', { name: 'New comment on file:commands' })).toBeInTheDocument()
})
