import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'

import { App } from './App'
import example from '../../examples/plan.json'
import old from '../../tests/fixtures/plan-0.1.11.json'
import type { Member, Plan } from './plan'
import { FakeServer, draft, message, thread } from './test/fakeServer'

let server: FakeServer

beforeEach(() => {
  server = new FakeServer()
  server.install()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function openFront() {
  render(<App />)
  await screen.findByRole('tablist')
}

/** Most tests comment on the back end classes, so the Classes tab starts on that side. */
async function open() {
  await openFront()
  fireEvent.click(screen.getByRole('button', { name: 'Back end' }))
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
  ).toEqual(['YouWhy None?', 'AgentIt means no hints left.'])
})

test('a thread shows Agent for old and new replies, styled the same', async () => {
  const mixed = thread('t-1', 'class:HintPolicy.next_level', 'Why None?', 'It means none.')
  mixed.messages.push(message('owner', 'And?'), message('claude', 'Old reply.'))
  server.threads = [mixed]
  await open()

  fireEvent.click(await screen.findByRole('button', { name: /on class:HintPolicy.next_level/ }))

  const rows = within(screen.getByRole('dialog')).getAllByRole('listitem')
  expect(rows.map((m) => m.textContent)).toEqual([
    'YouWhy None?',
    'AgentIt means none.',
    'YouAnd?',
    'AgentOld reply.',
  ])
  expect(rows.map((m) => m.getAttribute('data-author'))).toEqual([
    'owner',
    'agent',
    'owner',
    'agent',
  ])
})

test('the composer and the review panel say the agent sees the comments on submit', async () => {
  await open()
  await screen.findByText('HintPolicy')

  fireEvent.click(element('rel:orch-policy'))
  const composer = screen.getByRole('dialog', { name: 'New comment on rel:orch-policy' })
  expect(within(composer).getByText(/The agent sees it when you submit the review/)).toBeVisible()
  write(composer, 'Keep it?')
  fireEvent.click(within(composer).getByRole('button', { name: 'Add to review' }))

  const review = await screen.findByRole('region', { name: 'Your review' })
  expect(
    within(review).getByText(/The agent sees these comments only when you submit/),
  ).toBeVisible()
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

  fireEvent.click(element('rel:orch-policy'))
  const composer = screen.getByRole('dialog', { name: 'New comment on rel:orch-policy' })
  write(composer, 'Keep it?')
  fireEvent.click(within(composer).getByRole('button', { name: 'Add to review' }))

  const review = await screen.findByRole('region', { name: 'Your review' })
  expect(await within(review).findByText('Keep it?')).toBeInTheDocument()
  expect(posted('/api/drafts')).toEqual([{ anchor: 'rel:orch-policy', text: 'Keep it?' }])
  expect(posted('/api/threads')).toEqual([])
})

test('on an old plan a click on a class box still opens a comment box', async () => {
  server.plan = old
  await openFront()
  await screen.findByText('HintPolicy')

  fireEvent.click(element('class:HintPolicy'))

  expect(screen.getByRole('dialog', { name: 'New comment on class:HintPolicy' })).toBeVisible()
})

test('a plan where only some classes have a side is drawn like an old plan', async () => {
  server.plan = {
    ...example,
    classes: example.classes.map((c) => {
      if (c.id !== 'class:HintPolicy') return c
      const { side: _side, ...rest } = c
      return rest
    }),
  }
  server.threads = [thread('t-2', 'class:Orchestrator.on_event', 'Why?', 'Because.')]
  await openFront()
  await screen.findByText('HintPolicy')

  expect(screen.queryByRole('group', { name: 'Choose a side' })).not.toBeInTheDocument()
  expect(element('class:HintPolicy.next_level')).toHaveTextContent('next_level(given: int)')
  expect(
    await screen.findByRole('button', { name: /on class:Orchestrator.on_event/ }),
  ).toBeInTheDocument()
  expect(screen.queryByText(/Comments on the other side/)).not.toBeInTheDocument()
})

async function openDetails() {
  await open()
  await screen.findByText('HintPolicy')
  fireEvent.click(element('class:Orchestrator'))
  return screen.getByRole('dialog', { name: 'Details of Orchestrator' })
}

/** The example plan with its first class's members changed by `edit`. */
function planWith(id: string, edit: (members: Member[]) => void) {
  const plan = structuredClone(example) as Plan
  const cls = plan.classes.find((c) => c.id === id)
  if (!cls) throw new Error(`no class ${id}`)
  edit(cls.members)
  return plan
}

const memberLines = (details: HTMLElement) => [...details.querySelectorAll('li.member-line')]

test('clicking a class opens its details beside it, closed by Esc', async () => {
  const details = await openDetails()

  expect(details).toHaveTextContent('Asks the HintPolicy')
  expect(details.querySelector('p.details-note')).toHaveTextContent('Asks the HintPolicy')

  fireEvent.keyDown(details, { key: 'Escape' })

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('the popup puts members in a green, orange and red box, with no tag on each line', async () => {
  const details = await openDetails()

  const boxes = within(details).getAllByRole('list')
  expect(boxes.map((b) => b.getAttribute('aria-label'))).toEqual([
    'New members, 2',
    'Changed members, 1',
    'Removed members, 1',
  ])
  expect(boxes.map((b) => b.getAttribute('data-status'))).toEqual(['added', 'modified', 'removed'])
  expect(within(boxes[0]).getAllByRole('listitem')).toHaveLength(2)
  for (const line of memberLines(details)) {
    expect(line.textContent).not.toMatch(/\b(new|changed|removed)\b/i)
    expect(line.querySelector('.badge')).toBeNull()
  }
  // Orchestrator has no unchanged members, so there is nothing to fold away.
  expect(within(details).queryByRole('button', { name: /Show \d+ unchanged/ })).toBeNull()
})

test("a removed member's name is crossed out and can still be commented on", async () => {
  const details = await openDetails()
  const removed = within(details).getByRole('list', { name: 'Removed members, 1' })

  expect(removed.querySelector('s')).toHaveTextContent('parse_command')
  fireEvent.click(within(removed).getByRole('button', { name: 'parse_command' }))
  expect(removed).toHaveTextContent('parse_command(text: str) -> Command | None')
  expect(
    within(removed).getByRole('button', { name: 'Comment on class:Orchestrator.parse_command' }),
  ).toBeInTheDocument()
})

test('unchanged members are folded behind Show N unchanged', async () => {
  server.plan = planWith('class:Orchestrator', (members) => {
    for (const name of ['alpha', 'beta'])
      members.push({
        id: `class:Orchestrator.${name}`,
        name,
        kind: 'property',
        signature: `${name}: int`,
        status: 'unchanged',
      })
  })
  const details = await openDetails()

  expect(details).not.toHaveTextContent('alpha')
  fireEvent.click(within(details).getByRole('button', { name: 'Show 2 unchanged' }))

  const list = within(details).getByRole('list', { name: 'Unchanged members, 2' })
  expect(list).not.toHaveAttribute('data-status')
  expect(list).toHaveTextContent('alpha')
  expect(list).toHaveTextContent('beta')
  expect(within(details).queryByRole('button', { name: /Show 2 unchanged/ })).toBeNull()
})

test('a class whose members are all unchanged shows only the Show N unchanged button', async () => {
  await open()
  await screen.findByText('HintPolicy')

  fireEvent.click(element('class:LLMClient'))

  const details = screen.getByRole('dialog', { name: 'Details of LLMClient: Protocol' })
  expect(within(details).getByRole('button', { name: 'Show 1 unchanged' })).toBeInTheDocument()
  expect(details).not.toHaveTextContent('stream')
})

test('clicking a method line shows its full signature, one at a time', async () => {
  const details = await openDetails()
  const giveHint = within(details).getByRole('button', { name: 'give_hint' })
  const onEvent = within(details).getByRole('button', { name: 'on_event' })
  const signature = (text: string) => screen.queryByText(text)

  expect(giveHint).toHaveAttribute('aria-expanded', 'false')
  expect(signature('give_hint() -> AsyncIterator[str]')).toBeNull()

  fireEvent.click(giveHint)
  expect(giveHint).toHaveAttribute('aria-expanded', 'true')
  expect(signature('give_hint() -> AsyncIterator[str]')?.tagName).toBe('CODE')
  expect(signature('give_hint() -> AsyncIterator[str]')).toHaveClass('member-signature')

  fireEvent.click(onEvent)
  expect(signature('on_event(event: ClientEvent) -> None')).toBeInTheDocument()
  expect(signature('give_hint() -> AsyncIterator[str]')).toBeNull()
  expect(giveHint).toHaveAttribute('aria-expanded', 'false')

  fireEvent.click(onEvent)
  expect(signature('on_event(event: ClientEvent) -> None')).toBeNull()
})

test('a field line shows its type and has nothing to open', async () => {
  const details = await openDetails()

  const line = within(details).getByText('hints_given').closest('li') as HTMLElement
  expect(line).toHaveTextContent('hints_given: int')
  expect(line.querySelector('code.member-type')).toHaveTextContent(': int')
  expect(line.querySelector('[aria-expanded]')).toBeNull()
})

test("the description is the line's main text, under the name", async () => {
  const details = await openDetails()

  const line = within(details).getByRole('button', { name: 'on_event' }).closest('li')
  expect(line?.querySelector('p.member-note')).toHaveTextContent('Handles RequestHint by asking')
  expect(line).not.toHaveTextContent('ClientEvent')
})

test('the details popup takes focus, so Esc closes it from the page', async () => {
  const details = await openDetails()

  expect(details).toContainElement(document.activeElement as HTMLElement)
})

test("a second box's details popup also takes focus", async () => {
  await openDetails()
  ;(document.activeElement as HTMLElement).blur() // a real click on a plain box moves focus to the page
  fireEvent.click(element('class:HintPolicy'))

  const details = screen.getByRole('dialog', { name: 'Details of HintPolicy' })
  expect(details).toContainElement(document.activeElement as HTMLElement)
})

test('the popup title shows the name coloured by status, the parents in grey, and no status tag', async () => {
  await open()
  await screen.findByText('HintPolicy')

  fireEvent.click(element('class:HintLevel'))

  const details = screen.getByRole('dialog', { name: 'Details of HintLevel: Enum' })
  const heading = within(details).getByRole('heading', { level: 2 })
  expect(heading).toHaveAttribute('data-status', 'added')
  expect(heading.querySelector('strong')).toHaveTextContent('HintLevel')
  expect(heading.querySelector('.bases')).toHaveTextContent('Enum')
  const top = details.querySelector('.card-top') as HTMLElement
  expect(within(top).getByText('enum')).toBeInTheDocument()
  expect(top.textContent).not.toMatch(/added|new/i)
})

test('each comment icon is a focusable button that comments on its class or member', async () => {
  const details = await openDetails()

  const classIcon = within(details).getByRole('button', { name: 'Comment on class:Orchestrator' })
  const icon = within(details).getByRole('button', {
    name: 'Comment on class:Orchestrator.on_event',
  })
  for (const button of [classIcon, icon]) {
    expect(button.textContent).toBe('')
    expect(button).not.toHaveAttribute('hidden')
    expect(button).not.toHaveAttribute('tabindex', '-1')
  }
  fireEvent.click(icon)
  const composer = screen.getByRole('dialog', {
    name: 'New comment on class:Orchestrator.on_event',
  })
  write(composer, 'Why?')
  fireEvent.click(within(composer).getByRole('button', { name: 'Add to review' }))

  await vi.waitFor(() =>
    expect(posted('/api/drafts')).toEqual([
      { anchor: 'class:Orchestrator.on_event', text: 'Why?' },
    ]),
  )
})

test('an approved plan opens the popup without comment icons', async () => {
  server.approved = true
  const details = await openDetails()

  expect(within(details).queryByRole('button', { name: /^Comment/ })).not.toBeInTheDocument()
  expect(details).toHaveTextContent('give_hint')
})

test('an existing thread on a member still opens from its pin after the redesign', async () => {
  server.threads = [thread('t-9', 'class:Orchestrator.on_event', 'Why?', 'Because.')]
  await open()

  fireEvent.click(await screen.findByRole('button', { name: /on class:Orchestrator.on_event/ }))

  expect(
    screen.getByRole('dialog', { name: 'Thread on class:Orchestrator.on_event' }),
  ).toBeInTheDocument()
})

test('the popup, the thread card and the new-comment box keep the top line outside the scrolling part', async () => {
  const classes = (card: HTMLElement) => [...card.children].map((c) => c.className)
  server.threads = nextLevelThread()
  const details = await openDetails()

  expect(classes(details)).toEqual(['card-top', 'card-body'])
  const popupTop = details.querySelector('.card-top') as HTMLElement
  const body = details.querySelector('.card-body') as HTMLElement
  expect(within(popupTop).getByRole('button', { name: 'Close' })).toBeInTheDocument()
  expect(
    within(popupTop).getByRole('button', { name: 'Comment on class:Orchestrator' }),
  ).toBeInTheDocument()
  expect(within(body).getByRole('list', { name: 'New members, 2' })).toBeInTheDocument()

  fireEvent.click(await screen.findByRole('button', { name: /on class:HintPolicy.next_level/ }))
  const card = screen.getByRole('dialog', { name: 'Thread on class:HintPolicy.next_level' })
  expect(classes(card)).toEqual(['card-top', 'card-body'])
  expect(
    within(card.querySelector('.card-body') as HTMLElement).getByText('Why None?'),
  ).toBeVisible()
  fireEvent.click(within(card).getByRole('button', { name: 'Close' }))

  fireEvent.click(element('rel:orch-policy'))
  const composer = screen.getByRole('dialog', { name: 'New comment on rel:orch-policy' })
  expect(classes(composer)).toEqual(['card-top', 'card-body'])
  expect(
    within(composer.querySelector('.card-body') as HTMLElement).getByRole('textbox'),
  ).toBeInTheDocument()
})

test("a comment on the other side's class is listed beside the diagram", async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Why a policy?')]
  await openFront()

  const list = await screen.findByRole('region', { name: 'Comments on the other side' })
  expect(screen.queryByRole('button', { name: /messages? on class:HintPolicy/ })).toBeNull()
  fireEvent.click(within(list).getByRole('button', { name: /Why a policy/ }))

  expect(screen.getByRole('dialog', { name: 'Thread on class:HintPolicy' })).toBeVisible()
})

test.each([
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
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?', 'Yes.')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '2 messages on class:HintPolicy' }))

  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Resolve' }))

  expect(await screen.findByRole('button', { name: 'Reopen' })).toBeInTheDocument()
  expect(posted('/api/threads/t-1/resolve')).toEqual([null])
})

test('reopening a resolved thread takes effect at once', async () => {
  server.threads = [{ ...thread('t-1', 'class:HintPolicy', 'Rename?', 'Yes.'), resolved: true }]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '2 messages on class:HintPolicy' }))

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

test("the agent's reply, pushed by the server, appears without a reload", async () => {
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
  expect(screen.getByText('Too vague')).toBeInTheDocument() // kept, to submit again
  expect(screen.getByRole('button', { name: 'Submit review (1)' })).toBeEnabled()
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
  fireEvent.click(element('rel:orch-policy'))
  write(screen.getByRole('dialog'), 'Half a thought')

  fireEvent.click(element('rel:orch-llm'))

  const composer = screen.getByRole('dialog')
  expect(composer).toHaveAccessibleName('New comment on rel:orch-policy')
  expect(within(composer).getByRole('textbox')).toHaveValue('Half a thought')
})

const working = { text: 'Answering questions', done: false, at: '2026-11-03T10:00:00Z' }

test("the agent's status line shows what it is doing, as still in progress", async () => {
  server.status = working
  await open()

  const line = await screen.findByRole('status', { name: 'Agent' })
  expect(line).toHaveTextContent('Answering questions')
  expect(line).toHaveAttribute('data-done', 'false')
})

test("the agent's status line follows the server's pushes, up to done", async () => {
  server.status = working
  await open()
  await screen.findByRole('status', { name: 'Agent' })

  server.status = { text: 'Replies posted', done: true, at: '2026-11-03T10:05:00Z' }
  await act(async () => server.push({ type: 'status_changed' }))

  expect(await screen.findByText('Replies posted')).toBeInTheDocument()
  expect(screen.getByRole('status', { name: 'Agent' })).toHaveAttribute('data-done', 'true')
})

test('no status line while the agent has not set one', async () => {
  await open()

  expect(screen.queryByRole('status', { name: 'Agent' })).not.toBeInTheDocument()
})

test('once a composer with text is cancelled, clicking an element comments again', async () => {
  await open()
  await screen.findByText('HintPolicy')
  fireEvent.click(element('rel:orch-policy'))
  write(screen.getByRole('dialog'), 'Never mind')
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))

  fireEvent.click(element('rel:orch-llm'))

  expect(screen.getByRole('dialog')).toHaveAccessibleName('New comment on rel:orch-llm')
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
  const card = element('rel:orch-policy')

  fireEvent.pointerDown(card, { clientX: 100, clientY: 100, pointerId: 1, button: 0 })
  fireEvent.pointerMove(card, { clientX: 102, clientY: 101, pointerId: 1 })
  fireEvent.pointerUp(card, { clientX: 102, clientY: 101, pointerId: 1 })
  fireEvent.click(card)

  expect(screen.getByRole('dialog')).toHaveAccessibleName('New comment on rel:orch-policy')
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

  fireEvent.click(element('rel:orch-llm'))

  const editor = screen.getByRole('dialog')
  expect(editor).toHaveAccessibleName('Draft on class:HintPolicy')
  expect(within(editor).getByRole('textbox')).toHaveValue('Split it into two?')
})

test('text typed back to what the composer opened with does not hold the next click', async () => {
  await open()
  await screen.findByText('HintPolicy')
  fireEvent.click(element('rel:orch-policy'))
  write(screen.getByRole('dialog'), 'Hmm')
  write(screen.getByRole('dialog'), '')

  fireEvent.click(element('rel:orch-llm'))

  expect(screen.getByRole('dialog')).toHaveAccessibleName('New comment on rel:orch-llm')
})

async function writingOnAnArrow() {
  await screen.findByText('HintPolicy')
  fireEvent.click(element('rel:orch-policy'))
  write(screen.getByRole('dialog'), 'Half a thought')
}

function stillWriting() {
  const composer = screen.getByRole('dialog')
  expect(composer).toHaveAccessibleName('New comment on rel:orch-policy')
  expect(within(composer).getByRole('textbox')).toHaveValue('Half a thought')
}

test('opening a thread from its pin while writing keeps the comment being written', async () => {
  server.threads = [thread('t-1', 'class:Orchestrator', 'Rename?')]
  await open()
  await writingOnAnArrow()

  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:Orchestrator' }))

  stillWriting()
})

test('"Comment on this tab" while writing keeps the comment being written', async () => {
  await open()
  await writingOnAnArrow()

  fireEvent.click(screen.getByRole('button', { name: 'Comment on this tab' }))

  stillWriting()
})

test("a draft's Edit in the review panel while writing keeps the comment being written", async () => {
  server.drafts = [draft('d-1', 'risk:1', 'Too vague')]
  await open()
  await writingOnAnArrow()
  const review = screen.getByRole('region', { name: 'Your review' })

  fireEvent.click(within(review).getByRole('button', { name: 'Edit' }))

  stillWriting()
})

const BAD_JSON = 'Invalid JSON: key must be a string at line 1 column 2'
const brokenLine = (file: string) => `.plan-review/work/42/${file}: ${BAD_JSON}`

test('a broken comments.json shows a banner naming it, and the plan stays', async () => {
  await open()
  expect(screen.queryByRole('alert', { name: 'Broken files' })).not.toBeInTheDocument()
  cleanup()
  server.brokenFiles['/api/threads'] = [brokenLine('comments.json')]

  await open()

  expect(
    screen.getByRole('heading', { name: '#42 Let candidates request a hint during an interview' }),
  ).toBeInTheDocument()
  const banner = await screen.findByRole('alert', { name: 'Broken files' })
  expect(banner).toHaveTextContent(brokenLine('comments.json'))
})

test('adding a comment while drafts.json is broken shows the same named message', async () => {
  server.brokenFiles['/api/drafts'] = [brokenLine('drafts.json')]
  await open()
  await screen.findByText('HintPolicy')
  expect(await screen.findByRole('alert', { name: 'Broken files' })).toHaveTextContent(
    brokenLine('drafts.json'),
  )

  fireEvent.click(element('rel:orch-policy'))
  const composer = screen.getByRole('dialog', {
    name: 'New comment on rel:orch-policy',
  })
  write(composer, 'Keep it?')
  fireEvent.click(within(composer).getByRole('button', { name: 'Add to review' }))

  expect(await within(composer).findByText(brokenLine('drafts.json'))).toBeInTheDocument()
})

test('a broken status.json or last_event.json shows in the banner beside the plan', async () => {
  server.brokenFiles['/api/status'] = [brokenLine('status.json')]
  server.brokenFiles['/api/last-event'] = [brokenLine('last_event.json')]
  await open()

  const banner = await screen.findByRole('alert', { name: 'Broken files' })
  await vi.waitFor(() => {
    expect(banner).toHaveTextContent(brokenLine('status.json'))
    expect(banner).toHaveTextContent(brokenLine('last_event.json'))
  })
  expect(screen.queryByRole('status', { name: 'Agent' })).not.toBeInTheDocument()
})

test('one broken file named by two routes is listed once', async () => {
  server.brokenFiles['/api/status'] = [brokenLine('status.json')]
  server.brokenFiles['/api/last-event'] = [brokenLine('status.json')]
  await open()

  const banner = await screen.findByRole('alert', { name: 'Broken files' })

  await vi.waitFor(() => expect(within(banner).getAllByRole('listitem')).toHaveLength(1))
})

test('a banner line goes away once the file is fixed and the server pushes a change', async () => {
  server.brokenFiles['/api/threads'] = [brokenLine('comments.json')]
  await open()
  await screen.findByRole('alert', { name: 'Broken files' })

  delete server.brokenFiles['/api/threads']
  await act(async () => server.push({ type: 'threads_changed' }))

  await vi.waitFor(() =>
    expect(screen.queryByRole('alert', { name: 'Broken files' })).not.toBeInTheDocument(),
  )
})

test('the Resolve button appears only after the agent replied', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  await open()
  fireEvent.click(await screen.findByRole('button', { name: '1 message on class:HintPolicy' }))
  expect(within(screen.getByRole('dialog')).queryByRole('button', { name: 'Resolve' })).toBeNull()
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }))

  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?', 'Yes.')]
  server.push({ type: 'threads_changed' })
  fireEvent.click(await screen.findByRole('button', { name: '2 messages on class:HintPolicy' }))
  expect(within(screen.getByRole('dialog')).getByRole('button', { name: 'Resolve' })).toBeVisible()
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }))

  server.threads = [
    { ...thread('t-1', 'class:HintPolicy', 'Rename?', 'Yes.', 'Hm'), resolved: true },
  ]
  server.push({ type: 'threads_changed' })
  fireEvent.click(await screen.findByRole('button', { name: '3 messages on class:HintPolicy' }))
  expect(within(screen.getByRole('dialog')).getByRole('button', { name: 'Reopen' })).toBeVisible()
})

test('the page reloads what it missed after a reconnect', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?')]
  await open()
  await screen.findByRole('button', { name: '1 message on class:HintPolicy' })
  const fetched = (url: string) => server.calls.filter((c) => c.url === url).length
  const plans = fetched('/api/plan')
  const lists = fetched('/api/threads')

  server.threads = [thread('t-1', 'class:HintPolicy', 'Rename?', 'Yes.')]
  server.dropSockets()

  expect(
    await screen.findByRole(
      'button',
      { name: '2 messages on class:HintPolicy' },
      { timeout: 3000 },
    ),
  ).toBeInTheDocument()
  expect(fetched('/api/plan')).toBeGreaterThan(plans)
  expect(fetched('/api/threads')).toBeGreaterThan(lists)
})

test('backticks show as code in a thread message, a draft reply, the review panel and the thread list', async () => {
  server.threads = [
    thread('t-1', 'class:HintPolicy.next_level', 'Why `None`?', 'It means `no hints`.'),
  ]
  server.drafts = [
    draft('d-1', 'class:HintPolicy.next_level', 'Rename `next_level`', 't-1'),
    draft('d-2', 'risk:1', 'Too `vague`'),
  ]
  await open()

  const panel = await screen.findByRole('region', { name: 'Your review' })
  expect(within(panel).getByText('next_level', { selector: 'code.inline-code' })).toBeVisible()
  expect(within(panel).getByText('vague', { selector: 'code.inline-code' })).toBeVisible()
  fireEvent.click(await screen.findByRole('button', { name: /on class:HintPolicy.next_level/ }))
  const card = screen.getByRole('dialog', { name: 'Thread on class:HintPolicy.next_level' })
  for (const code of ['None', 'no hints', 'next_level'])
    expect(within(card).getByText(code, { selector: 'code.inline-code' })).toBeVisible()
  expect(card.textContent).not.toContain('`')
  expect(panel.textContent).not.toContain('`')
})

test('backticks show as code in the thread list beside the diagram', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy', 'Why `None`?')]
  await openFront()

  const list = await screen.findByRole('region', { name: 'Comments on the other side' })
  expect(within(list).getByText('None', { selector: 'code.inline-code' })).toBeVisible()
  expect(list.textContent).not.toContain('`')
})

test('backticks show as code in the hover preview of a pin', async () => {
  server.threads = [thread('t-1', 'class:HintPolicy.next_level', 'Is `None` ok?')]
  await open()

  fireEvent.mouseEnter(
    await screen.findByRole('button', { name: /on class:HintPolicy.next_level/ }),
  )

  const tip = screen.getByRole('tooltip')
  expect(within(tip).getByText('None', { selector: 'code.inline-code' })).toBeVisible()
  expect(tip.textContent).not.toContain('`')
})
