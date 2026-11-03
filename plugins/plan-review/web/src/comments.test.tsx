import { act, fireEvent, render, screen, within } from '@testing-library/react'

import { App } from './App'
import { FakeServer, draft, thread } from './test/fakeServer'

let server: FakeServer

beforeEach(() => {
  server = new FakeServer()
  server.install()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function open() {
  render(<App />)
  await screen.findByRole('tablist')
}

function element(id: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-element-id="${CSS.escape(id)}"]`)
  if (!found) throw new Error(`no element ${id}`)
  return found
}

const posted = (url: string) =>
  server.calls.filter((c) => c.method !== 'GET' && c.url === url).map((c) => c.body)

function write(dialog: HTMLElement, text: string) {
  fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: text } })
}

const nextLevelThread = () => [
  thread('t-1', 'class:HintPolicy.next_level', 'Why None?', 'It means no hints left.'),
]

test('a thread shows as a pin on its element, counting its messages', async () => {
  server.threads = nextLevelThread()
  await open()

  expect(
    await screen.findByRole('button', { name: '2 messages on class:HintPolicy.next_level' }),
  ).toBeInTheDocument()
})

test("hovering a pin previews the thread's first message", async () => {
  server.threads = nextLevelThread()
  await open()
  const pin = await screen.findByRole('button', { name: /on class:HintPolicy.next_level/ })

  fireEvent.mouseEnter(pin)

  expect(screen.getByRole('tooltip')).toHaveTextContent('Why None?')
})

test('clicking a pin opens the whole thread', async () => {
  server.threads = nextLevelThread()
  await open()

  fireEvent.click(await screen.findByRole('button', { name: /on class:HintPolicy.next_level/ }))

  const card = screen.getByRole('dialog', { name: 'Thread on class:HintPolicy.next_level' })
  expect(
    within(card)
      .getAllByRole('listitem')
      .map((m) => m.textContent),
  ).toEqual(['YouWhy None?', 'ClaudeIt means no hints left.'])
})

test("a thread card's × closes it", async () => {
  server.threads = nextLevelThread()
  await open()
  fireEvent.click(await screen.findByRole('button', { name: /on class:HintPolicy.next_level/ }))

  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('clicking any element opens a composer whose comment is saved as a draft, not posted', async () => {
  await open()
  await screen.findByText('HintPolicy')

  fireEvent.click(element('class:Orchestrator.parse_command'))
  const composer = screen.getByRole('dialog', {
    name: 'New comment on class:Orchestrator.parse_command',
  })
  write(composer, 'Keep it?')
  fireEvent.click(within(composer).getByRole('button', { name: 'Add to review' }))

  const review = await screen.findByRole('region', { name: 'Your review' })
  expect(await within(review).findByText('Keep it?')).toBeInTheDocument()
  expect(posted('/api/drafts')).toEqual([
    { anchor: 'class:Orchestrator.parse_command', text: 'Keep it?' },
  ])
  expect(posted('/api/threads')).toEqual([])
})

test.each([
  ['a whole class card', 'classes', 'class:HintPolicy'],
  ['a relation arrow', 'classes', 'rel:orch-policy'],
  ['an architecture component', 'architecture', 'arch:agent'],
  ['an architecture connection', 'architecture', 'arch:agent-ollama'],
  ['a sequence participant', 'flows', 'flow:hint/orch'],
  ['a sequence step', 'flows', 'flow:hint/5'],
  ['a file', 'files', 'file:commands'],
  ['a test', 'tests', 'test:1'],
  ['a risk', 'risks', 'risk:1'],
  ['an open question', 'risks', 'risk:3'],
  ['a flowchart box', 'flows:Choosing the hint level', 'flow:level/check'],
  ['a flowchart arrow', 'flows:Choosing the hint level', 'flow:level/e2'],
])('%s is commentable by a click', async (_, where, id) => {
  const [tab, flow] = where.split(':')
  await open()
  const label = {
    classes: 'Classes',
    architecture: 'Architecture',
    flows: 'Flows',
    files: 'Files',
    tests: 'Tests',
    risks: 'Risks & open questions',
  }[tab]
  fireEvent.click(screen.getByRole('tab', { name: label }))
  if (flow) fireEvent.click(screen.getByRole('button', { name: flow }))
  await vi.waitFor(() => element(id))

  fireEvent.click(element(id))

  expect(screen.getByRole('dialog', { name: `New comment on ${id}` })).toBeInTheDocument()
})

test('the issue title is commentable', async () => {
  await open()

  fireEvent.click(screen.getByRole('heading', { name: /^#42 / }))

  expect(screen.queryByRole('dialog', { name: 'New comment on header:title' })).toBeInTheDocument()
})

test('the summary is commentable', async () => {
  await open()

  fireEvent.click(screen.getByText(/Add a Hint button to the client/))

  expect(
    screen.queryByRole('dialog', { name: 'New comment on header:summary' }),
  ).toBeInTheDocument()
})

test('a button inside an element does its own job instead of opening a composer', async () => {
  await open()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))

  fireEvent.click(within(element('test:1')).getByRole('button'))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Classes' })).toHaveAttribute('aria-selected', 'true')
})

test('dragging a diagram pans it and does not open a composer', async () => {
  await open()
  await screen.findByText('HintPolicy')
  const card = element('class:HintPolicy')

  fireEvent.pointerDown(card, { clientX: 100, clientY: 100, pointerId: 1 })
  fireEvent.pointerMove(card, { clientX: 160, clientY: 130, pointerId: 1 })
  fireEvent.pointerUp(card, { clientX: 160, clientY: 130, pointerId: 1 })
  fireEvent.click(card)

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(document.querySelector<HTMLElement>('.canvas')?.style.transform).toContain(
    'translate(60px, 30px)',
  )
})

const twoDrafts = () => [draft('d-1', 'risk:1', 'Too vague'), draft('d-2', 'test:1', 'Rename')]

test('pending drafts load with the page into "Your review"', async () => {
  server.drafts = twoDrafts()
  await open()

  const review = await screen.findByRole('region', { name: 'Your review' })
  expect(review).toHaveTextContent('Too vague')
  expect(review).toHaveTextContent('Rename')
})

test('a pending draft can be edited from the review panel', async () => {
  server.drafts = twoDrafts()
  await open()
  const review = await screen.findByRole('region', { name: 'Your review' })

  fireEvent.click(within(review).getAllByRole('button', { name: 'Edit' })[0])
  const editor = screen.getByRole('dialog', { name: 'Draft on risk:1' })
  write(editor, 'Too vague: name the failure')
  fireEvent.click(within(editor).getByRole('button', { name: 'Save draft' }))

  expect(await within(review).findByText('Too vague: name the failure')).toBeInTheDocument()
  expect(posted('/api/drafts/d-1')).toEqual([{ text: 'Too vague: name the failure' }])
})

test('a pending draft can be discarded from the review panel', async () => {
  server.drafts = twoDrafts()
  await open()
  const review = await screen.findByRole('region', { name: 'Your review' })

  fireEvent.click(within(review).getAllByRole('button', { name: 'Discard' })[1])

  await vi.waitFor(() => expect(within(review).queryByText('Rename')).not.toBeInTheDocument())
  expect(server.calls).toContainEqual({ method: 'DELETE', url: '/api/drafts/d-2', body: null })
})

test('a reply draft is marked as a reply in the review panel', async () => {
  server.threads = [thread('t-1', 'risk:1', 'Agree?')]
  server.drafts = [draft('d-1', 'risk:1', 'Yes', 't-1')]
  await open()

  const review = await screen.findByRole('region', { name: 'Your review' })
  expect(within(review).getByText('reply')).toBeInTheDocument()
})

test('editing a reply draft from the panel opens it as a draft reply', async () => {
  server.threads = [thread('t-1', 'risk:1', 'Agree?')]
  server.drafts = [draft('d-1', 'risk:1', 'Yes', 't-1')]
  await open()
  const review = await screen.findByRole('region', { name: 'Your review' })

  fireEvent.click(within(review).getByRole('button', { name: 'Edit' }))

  expect(screen.getByRole('dialog')).toHaveAccessibleName('Draft reply on risk:1')
})

test('a draft opened from its pin can be discarded there', async () => {
  server.drafts = [draft('d-1', 'class:HintPolicy', 'Split it?')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: 'Draft on class:HintPolicy' }))

  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Discard draft' }))

  await vi.waitFor(() =>
    expect(screen.queryByRole('region', { name: 'Your review' })).not.toBeInTheDocument(),
  )
  expect(server.calls).toContainEqual({ method: 'DELETE', url: '/api/drafts/d-1', body: null })
})

test('drafts on one element get pins side by side, not on top of each other', async () => {
  server.drafts = [draft('d-1', 'risk:1', 'One'), draft('d-2', 'risk:1', 'Two')]
  await open()
  fireEvent.click(screen.getByRole('tab', { name: 'Risks & open questions' }))
  await screen.findAllByRole('button', { name: 'Draft on risk:1' })

  const lefts = screen
    .getAllByRole('button', { name: 'Draft on risk:1' })
    .map((pin) => (pin.parentElement as HTMLElement).style.left)
  expect(new Set(lefts).size).toBe(2)
})

test('the submit button is disabled while the review is being sent', async () => {
  server.drafts = twoDrafts()
  let release = () => {}
  server.reviewHold = new Promise<void>((resolve) => (release = resolve))
  await open()
  const submit = await screen.findByRole('button', { name: 'Submit review (2)' })

  fireEvent.click(submit)

  await vi.waitFor(() => expect(submit).toBeDisabled())
  await act(async () => release())
})

test('a draft on an element shows as a draft pin that opens it for editing', async () => {
  server.drafts = [draft('d-1', 'class:HintPolicy', 'Split it?')]
  await open()

  fireEvent.click(await screen.findByRole('button', { name: 'Draft on class:HintPolicy' }))

  expect(screen.getByRole('dialog', { name: 'Draft on class:HintPolicy' })).toHaveTextContent(
    'Split it?',
  )
})

test('Submit review sends every draft at once, and they become threads', async () => {
  server.drafts = [draft('d-1', 'risk:1', 'Too vague'), draft('d-2', 'test:1', 'Rename')]
  await open()

  fireEvent.click(await screen.findByRole('button', { name: 'Submit review (2)' }))

  await vi.waitFor(() =>
    expect(screen.queryByRole('region', { name: 'Your review' })).not.toBeInTheDocument(),
  )
  expect(posted('/api/review')).toEqual([null])
  expect(server.threads.map((t) => t.anchor)).toEqual(['risk:1', 'test:1'])
})

async function replyInThread(text: string) {
  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:HintPolicy' }))
  const card = screen.getByRole('dialog')
  write(card, text)
  fireEvent.click(within(card).getByRole('button', { name: 'Add reply to review' }))
  return card
}

test('a reply in a thread is saved as a draft, not posted', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  await open()

  const card = await replyInThread('Never mind')

  await within(card).findByText('Never mind')
  expect(posted('/api/drafts')).toEqual([{ thread_id: 't-1', text: 'Never mind' }])
})

test('a draft reply shows in its thread marked as a draft', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  await open()

  const card = await replyInThread('Never mind')

  await within(card).findByText('Never mind')
  expect(within(card).getByText('Draft')).toBeInTheDocument()
})

test('a draft reply can be edited from its thread', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  server.drafts = [draft('d-1', 'class:HintPolicy', 'Never mind', 't-1')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:HintPolicy' }))

  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Edit' }))

  expect(screen.getByRole('dialog')).toHaveAccessibleName('Draft reply on class:HintPolicy')
})

test('a draft reply can be discarded from its thread', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  server.drafts = [draft('d-1', 'class:HintPolicy', 'Never mind', 't-1')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:HintPolicy' }))

  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Discard' }))

  await vi.waitFor(() =>
    expect(server.calls).toContainEqual({ method: 'DELETE', url: '/api/drafts/d-1', body: null }),
  )
})

test('resolving a thread takes effect at once', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:HintPolicy' }))

  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Resolve' }))

  expect(await screen.findByRole('button', { name: 'Reopen' })).toBeInTheDocument()
  expect(posted('/api/threads/t-1/resolve')).toEqual([null])
})

test('reopening a resolved thread takes effect at once', async () => {
  server.threads = [{ ...thread('t-1', 'class:HintPolicy', 'Rename?'), resolved: true }]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:HintPolicy' }))

  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Reopen' }))

  expect(await screen.findByRole('button', { name: 'Resolve' })).toBeInTheDocument()
  expect(posted('/api/threads/t-1/reopen')).toEqual([null])
})

test('the tab itself can be commented on', async () => {
  await open()

  fireEvent.click(screen.getByRole('button', { name: 'Comment on this tab' }))

  expect(screen.getByRole('dialog', { name: 'New comment on tab:classes' })).toBeInTheDocument()
})

test('threads on the tab itself are listed beside it', async () => {
  server.threads = [thread('t-1', 'tab:classes', 'Too many classes')]
  await open()

  const list = await screen.findByRole('region', { name: 'Comments on this tab' })
  expect(within(list).getByRole('button', { name: /Too many classes/ })).toBeInTheDocument()
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

test('drafts changed in another tab appear without a reload', async () => {
  await open()

  server.drafts = [draft('d-1', 'risk:1', 'From the other tab')]
  await act(async () => server.push({ type: 'drafts_changed' }))

  expect(await screen.findByText('From the other tab')).toBeInTheDocument()
})

test('submitting a review confirms it with a toast naming how many comments were sent', async () => {
  server.drafts = [draft('d-1', 'risk:1', 'Too vague'), draft('d-2', 'test:1', 'Rename')]
  await open()

  fireEvent.click(await screen.findByRole('button', { name: 'Submit review (2)' }))

  expect(await screen.findByRole('status', { name: 'Notification' })).toHaveTextContent(
    'Review sent (2 comments)',
  )
})

test('a failed submit says why in a toast', async () => {
  server.drafts = [draft('d-1', 'risk:1', 'Too vague')]
  server.reviewError = 'disk full'
  await open()

  fireEvent.click(await screen.findByRole('button', { name: 'Submit review (1)' }))

  expect(await screen.findByRole('alert', { name: 'Notification' })).toHaveTextContent(
    'Review not sent: disk full',
  )
})

test('a failed submit shows its error once, not also in the panel', async () => {
  server.drafts = [draft('d-1', 'risk:1', 'Too vague')]
  server.reviewError = 'disk full'
  await open()

  fireEvent.click(await screen.findByRole('button', { name: 'Submit review (1)' }))
  await screen.findByRole('alert', { name: 'Notification' })

  expect(screen.getAllByText(/disk full/)).toHaveLength(1)
})

test('the toast counts what the server sent, including drafts added in another tab', async () => {
  server.drafts = [draft('d-1', 'risk:1', 'One'), draft('d-2', 'risk:2', 'Two')]
  await open()
  await screen.findByRole('button', { name: 'Submit review (2)' })
  server.drafts = [...server.drafts, draft('d-3', 'risk:3', 'From the other tab')]

  fireEvent.click(screen.getByRole('button', { name: 'Submit review (2)' }))

  expect(await screen.findByRole('status', { name: 'Notification' })).toHaveTextContent(
    'Review sent (3 comments)',
  )
})

test('clicking another element while writing keeps the comment being written', async () => {
  await open()
  await screen.findByText('HintPolicy')
  fireEvent.click(element('class:HintPolicy'))
  write(screen.getByRole('dialog'), 'Half a thought')

  fireEvent.click(element('class:Orchestrator'))

  const composer = screen.getByRole('dialog')
  expect(composer).toHaveAccessibleName('New comment on class:HintPolicy')
  expect(within(composer).getByRole('textbox')).toHaveValue('Half a thought')
})

const working = { text: 'Answering questions', done: false, at: '2026-11-03T10:00:00Z' }

test("Claude's status line shows what it is doing, as still in progress", async () => {
  server.status = working
  await open()

  const line = await screen.findByRole('status', { name: 'Claude' })
  expect(line).toHaveTextContent('Answering questions')
  expect(line).toHaveAttribute('data-done', 'false')
})

test("Claude's status line follows the server's pushes, up to done", async () => {
  server.status = working
  await open()
  await screen.findByRole('status', { name: 'Claude' })

  server.status = { text: 'Replies posted', done: true, at: '2026-11-03T10:05:00Z' }
  await act(async () => server.push({ type: 'status_changed' }))

  expect(await screen.findByText('Replies posted')).toBeInTheDocument()
  expect(screen.getByRole('status', { name: 'Claude' })).toHaveAttribute('data-done', 'true')
})

test('no status line while Claude has not set one', async () => {
  await open()

  expect(screen.queryByRole('status', { name: 'Claude' })).not.toBeInTheDocument()
})

test('once a composer with text is cancelled, clicking an element comments again', async () => {
  await open()
  await screen.findByText('HintPolicy')
  fireEvent.click(element('class:HintPolicy'))
  write(screen.getByRole('dialog'), 'Never mind')
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))

  fireEvent.click(element('class:Orchestrator'))

  expect(screen.getByRole('dialog')).toHaveAccessibleName('New comment on class:Orchestrator')
})

test('arrows have a wide invisible click target', async () => {
  await open()
  await screen.findByText('HintPolicy')

  const edges = document.querySelectorAll('.edge')
  expect(edges.length).toBeGreaterThan(0)
  for (const edge of edges) expect(edge.querySelector(':scope > .hit')).not.toBeNull()
})

test('sequence steps and lifelines have wide invisible click targets', async () => {
  await open()
  fireEvent.click(screen.getByRole('tab', { name: 'Flows' }))

  const targets = document.querySelectorAll('.message, .participant')
  expect(targets.length).toBeGreaterThan(0)
  for (const target of targets) expect(target.querySelector(':scope > .hit')).not.toBeNull()
})

test('a step to itself can be clicked on its label', async () => {
  const plan = structuredClone(server.plan) as {
    flows: { steps?: { id: string; from: string; to: string; label: string; status: string }[] }[]
  }
  plan.flows[0].steps!.push({
    id: 'flow:hint/self',
    from: 'flow:hint/orch',
    to: 'flow:hint/orch',
    label: 'checks max_hints',
    status: 'added',
  })
  server.plan = plan
  await open()
  fireEvent.click(screen.getByRole('tab', { name: 'Flows' }))

  const step = element('flow:hint/self')
  const x = Number(step.querySelector('line:not(.hit)')!.getAttribute('x1'))
  const area = step.querySelector('.hit-area')!
  const width = Number(area.getAttribute('width'))
  // Centred on the participant's line, as wide as the label drawn there.
  expect(width).toBeGreaterThan(0)
  expect(Number(area.getAttribute('x'))).toBe(x - width / 2)
})

test('a press that barely moves is still a click that comments', async () => {
  await open()
  await screen.findByText('HintPolicy')
  const card = element('class:HintPolicy')

  fireEvent.pointerDown(card, { clientX: 100, clientY: 100, pointerId: 1, button: 0 })
  fireEvent.pointerMove(card, { clientX: 102, clientY: 101, pointerId: 1 })
  fireEvent.pointerUp(card, { clientX: 102, clientY: 101, pointerId: 1 })
  fireEvent.click(card)

  expect(screen.getByRole('dialog')).toHaveAccessibleName('New comment on class:HintPolicy')
})

test('a click that ends a text selection does not open a composer', async () => {
  await open()
  vi.spyOn(window, 'getSelection').mockReturnValue({ toString: () => 'HintPolicy' } as Selection)

  fireEvent.click(element('header:summary'))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('clicking another element while editing a draft keeps the edit', async () => {
  server.drafts = [draft('d-1', 'class:HintPolicy', 'Split it?')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: 'Draft on class:HintPolicy' }))
  write(screen.getByRole('dialog'), 'Split it into two?')

  fireEvent.click(element('class:Orchestrator'))

  const editor = screen.getByRole('dialog')
  expect(editor).toHaveAccessibleName('Draft on class:HintPolicy')
  expect(within(editor).getByRole('textbox')).toHaveValue('Split it into two?')
})

test('text typed back to what the composer opened with does not hold the next click', async () => {
  await open()
  await screen.findByText('HintPolicy')
  fireEvent.click(element('class:HintPolicy'))
  write(screen.getByRole('dialog'), 'Hmm')
  write(screen.getByRole('dialog'), '')

  fireEvent.click(element('class:Orchestrator'))

  expect(screen.getByRole('dialog')).toHaveAccessibleName('New comment on class:Orchestrator')
})

async function writingOnHintPolicy() {
  await screen.findByText('HintPolicy')
  fireEvent.click(element('class:HintPolicy'))
  write(screen.getByRole('dialog'), 'Half a thought')
}

function stillWriting() {
  const composer = screen.getByRole('dialog')
  expect(composer).toHaveAccessibleName('New comment on class:HintPolicy')
  expect(within(composer).getByRole('textbox')).toHaveValue('Half a thought')
}

test('opening a thread from its pin while writing keeps the comment being written', async () => {
  server.threads = [thread('t-1', 'class:Orchestrator', 'Rename?')]
  await open()
  await writingOnHintPolicy()

  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:Orchestrator' }))

  stillWriting()
})

test('"Comment on this tab" while writing keeps the comment being written', async () => {
  await open()
  await writingOnHintPolicy()

  fireEvent.click(screen.getByRole('button', { name: 'Comment on this tab' }))

  stillWriting()
})

test("a draft's Edit in the review panel while writing keeps the comment being written", async () => {
  server.drafts = [draft('d-1', 'risk:1', 'Too vague')]
  await open()
  await writingOnHintPolicy()
  const review = screen.getByRole('region', { name: 'Your review' })

  fireEvent.click(within(review).getByRole('button', { name: 'Edit' }))

  stillWriting()
})
