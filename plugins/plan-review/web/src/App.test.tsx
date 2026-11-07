import { act, fireEvent, render, screen, within } from '@testing-library/react'

import example from '../../examples/plan.json'
import promptExample from '../../examples/prompt-plan.json'
import old from '../../tests/fixtures/plan-0.1.11.json'
import { App } from './App'
import { LABEL_LINE_HEIGHT } from './diagram'
import { FakeServer } from './test/fakeServer'
import { grill, question } from './test/grillData'

function serve(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView // jsdom has none
})

test('shows loading, then the issue and its summary', async () => {
  new FakeServer().install()
  render(<App />)

  expect(screen.getByText('Loading plan…')).toBeInTheDocument()
  expect(
    await screen.findByRole('heading', {
      name: '#42 Let candidates request a hint during an interview',
    }),
  ).toBeInTheDocument()
  expect(screen.getByText(/Add a Hint button to the client/)).toBeInTheDocument()
})

test('an invalid plan shows its errors', async () => {
  serve(422, { errors: ['.claude/work/42/plan.json: summary: Field required'] })
  render(<App />)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    '.claude/work/42/plan.json: summary: Field required',
  )
})

async function loaded() {
  new FakeServer().install()
  render(<App />)
  await screen.findByRole('tablist')
}

test('tabs start on Classes; Files shows files grouped by kind, coloured by change', async () => {
  await loaded()

  expect(screen.getByRole('tab', { name: 'Classes' })).toHaveAttribute('aria-selected', 'true')
  fireEvent.click(screen.getByRole('tab', { name: 'Files' }))

  const panel = screen.getByRole('tabpanel')
  expect(
    within(panel)
      .getAllByRole('heading')
      .map((h) => h.textContent),
  ).toEqual(['Code', 'Tests', 'Config', 'Docs'])
  const removed = within(panel).getByText('backend/src/app/core/commands.py').closest('li')
  expect(removed).toHaveAttribute('data-status', 'removed')
  expect(removed).toHaveTextContent('Free-text commands replaced by events')
})

test('each file says in words how it changes, not by colour alone', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Files' }))

  const removed = screen.getByText('backend/src/app/core/commands.py').closest('li')!
  expect(within(removed).getByText('removed')).toHaveClass('change')
})

test('Tests lists the plan order; a target link switches to its tab', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))

  const rows = within(screen.getByRole('tabpanel')).getAllByRole('listitem')
  expect(rows.map((r) => within(r).getByText(/^test_/).textContent)).toEqual([
    'test_first_hint_is_a_nudge',
    'test_levels_escalate_then_stop',
    'test_max_hints_caps_the_sequence',
    'test_request_hint_event_streams_a_hint',
    'test_no_hints_left_is_said_without_calling_the_llm',
  ])
  fireEvent.click(within(rows[4]).getByRole('button', { name: 'flow:level/refuse' }))

  expect(screen.getByRole('tab', { name: 'Flows' })).toHaveAttribute('aria-selected', 'true')
})

test("a test's target link shows its flow and highlights the element", async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))

  fireEvent.click(screen.getByRole('button', { name: 'flow:level/refuse' }))

  await vi.waitFor(() =>
    expect(element('flow:level/refuse')).toHaveAttribute('data-focused', 'true'),
  )
  expect(screen.getByRole('button', { name: 'Choosing the hint level' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test("a test's target in a class diagram is highlighted once the diagram is laid out", async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))

  fireEvent.click(screen.getAllByRole('button', { name: 'class:HintPolicy.max_hints' })[0])

  await vi.waitFor(() =>
    expect(element('class:HintPolicy.max_hints')).toHaveAttribute('data-focused', 'true'),
  )
  expect(document.querySelectorAll('[data-focused]')).toHaveLength(1)
})

test("Risks shows risks and open questions in separate sections, in the architect's order", async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Risks & open questions' }))

  const [risks, questions] = within(screen.getByRole('tabpanel')).getAllByRole('list')
  const riskRows = within(risks).getAllByRole('listitem')
  expect(riskRows[0]).toHaveAttribute('data-severity', 'high')
  expect(riskRows[0]).toHaveTextContent('Level-specific prompt')
  expect(within(questions).getByRole('listitem')).toHaveTextContent(
    'Should hints count against the candidate',
  )
})

test('an unreachable server is reported, not left loading', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  render(<App />)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    "Can't reach the plan-review server. Is `plan-review serve` still running?",
  )
})

function element(id: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-element-id="${CSS.escape(id)}"]`)
  if (!found) throw new Error(`no element ${id}`)
  return found
}

test('Classes draws a card per class with members coloured by their own status', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('button', { name: 'Back end' }))

  await screen.findByText('HintPolicy')
  expect(element('class:Orchestrator')).toHaveAttribute('data-status', 'modified')
  expect(element('class:Orchestrator.parse_command')).toHaveAttribute('data-status', 'removed')
  expect(element('class:Orchestrator.give_hint')).toHaveTextContent('give_hint()')
  expect(element('rel:orch-policy')).toHaveAttribute('data-status', 'added')
  expect(screen.getByRole('list', { name: 'Legend' })).toHaveTextContent(
    'addedmodifiedremovedunchanged',
  )
})

test('Architecture draws its components and labelled connections', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Architecture' }))

  await screen.findByText('Ollama')
  expect(element('arch:agent-ollama')).toHaveTextContent('HTTP')
})

test('Flows draws one flow at a time, picked by title: sequences as messages, flowcharts as boxes', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Flows' }))

  expect(element('flow:hint')).toHaveTextContent('Candidate requests a hint')
  expect(element('flow:hint/orch')).toHaveTextContent('Orchestrator')
  expect(element('flow:hint/5')).toHaveAttribute('data-status', 'removed')
  expect(element('flow:hint/5')).toHaveTextContent("chat '/hint'")
  fireEvent.click(screen.getByRole('button', { name: /hint level/i }))
  await screen.findByText('hints_given < max_hints?')
  expect(element('flow:level/e2')).toHaveTextContent('yes')
})

test('the summary starts clamped to two lines; More shows all of it', async () => {
  await loaded()
  const summary = element('header:summary')
  expect(summary).toHaveAttribute('data-clamped', 'true')

  fireEvent.click(screen.getByRole('button', { name: 'More' }))

  expect(summary).toHaveAttribute('data-clamped', 'false')
  expect(screen.getByRole('button', { name: 'Less' })).toBeInTheDocument()
})

async function withTestTargeting(target: string) {
  const server = new FakeServer()
  const plan = structuredClone(server.plan) as { tests: { target: string }[] }
  plan.tests[0].target = target
  server.plan = plan
  server.install()
  render(<App />)
  await screen.findByRole('tablist')
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))
}

test("a test's target in a list is scrolled into view", async () => {
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  await withTestTargeting('file:commands')

  fireEvent.click(screen.getByRole('button', { name: 'file:commands' }))

  await vi.waitFor(() => expect(scroll).toHaveBeenCalled())
  expect(scroll.mock.contexts[0]).toBe(element('file:commands'))
})

test("a test's target in a diagram is not scrolled: the fitted view already shows it", async () => {
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  await withTestTargeting('class:HintPolicy')

  fireEvent.click(screen.getAllByRole('button', { name: 'class:HintPolicy' })[0])
  await vi.waitFor(() =>
    expect(element('class:HintPolicy')).toHaveAttribute('data-focused', 'true'),
  )

  expect(scroll).not.toHaveBeenCalled()
})

test('changing tab clears the highlight of a test target', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))
  fireEvent.click(screen.getAllByRole('button', { name: 'class:HintPolicy.max_hints' })[0])
  await vi.waitFor(() =>
    expect(element('class:HintPolicy.max_hints')).toHaveAttribute('data-focused', 'true'),
  )

  fireEvent.click(screen.getByRole('tab', { name: 'Files' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Classes' }))

  await screen.findByText('HintPolicy')
  expect(document.querySelector('[data-focused]')).toBeNull()
})

async function loadedPrompt() {
  const server = new FakeServer()
  server.plan = promptExample
  server.install()
  render(<App />)
  await screen.findByRole('tablist')
}

test('a prompt plan opens on its acceptance criteria, each one commentable', async () => {
  await loadedPrompt()

  expect(screen.getAllByRole('tab')[0]).toHaveTextContent('Acceptance criteria')
  expect(screen.getByRole('tab', { name: 'Acceptance criteria' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  const rows = within(screen.getByRole('tabpanel')).getAllByRole('listitem')
  expect(rows.map((row) => row.textContent)).toEqual(promptExample.acceptance_criteria)
  expect(rows.map((row) => row.getAttribute('data-element-id'))).toEqual([
    'criterion:1',
    'criterion:2',
    'criterion:3',
    'criterion:4',
  ])
  fireEvent.click(rows[1])
  expect(screen.getByRole('dialog')).toHaveAccessibleName('New comment on criterion:2')
})

test('an issue plan still starts on Classes, with no criteria tab', async () => {
  await loaded()

  expect(screen.queryByRole('tab', { name: 'Acceptance criteria' })).toBeNull()
  expect(screen.getByRole('tab', { name: 'Classes' })).toHaveAttribute('aria-selected', 'true')
})

test('the header shows the issue label, and the branch once there is one', async () => {
  await loadedPrompt()

  const heading = screen.getByRole('heading', { level: 1 })
  expect(heading).toHaveTextContent('add-dark-mode-2026-11-05 Add a dark mode to the settings page')
  expect(heading.textContent).not.toContain('#')
  expect(screen.getByText('add-dark-mode-2026-11-05', { selector: '.branch' })).toBeInTheDocument()
})

test('with no branch yet, the header has no branch element', async () => {
  await loaded()

  expect(document.querySelector('.branch')).toBeNull()
})

test('the top bar switches between Grill and Plan once both exist', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  server.install()
  render(<App />)
  await screen.findByRole('tablist')

  const nav = await screen.findByRole('navigation', { name: 'Pages' })
  expect(within(nav).getByRole('link', { name: 'Grill' })).toHaveAttribute('href', '/grill')
  expect(within(nav).getByRole('link', { name: 'Plan' })).toHaveAttribute('aria-current', 'page')
})

test('without a grill the plan page has no page switch', async () => {
  await loaded()

  expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument()
})

test('the Classes tab shows a Front end / Back end switch and draws one side', async () => {
  await loaded()
  const sides = screen.getByRole('group', { name: 'Choose a side' })

  expect(within(sides).getByRole('button', { name: 'Front end' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await screen.findByText('HintButton')
  expect(screen.queryByText('HintPolicy')).not.toBeInTheDocument()

  fireEvent.click(within(sides).getByRole('button', { name: 'Back end' }))

  await screen.findByText('HintPolicy')
  expect(screen.queryByText('HintButton')).not.toBeInTheDocument()
})

test('a revision that leaves the chosen side empty shows the side that is left', async () => {
  const server = new FakeServer()
  server.install()
  render(<App />)
  await screen.findByRole('tablist')
  fireEvent.click(screen.getByRole('button', { name: 'Back end' }))
  await screen.findByText('HintPolicy')
  const front = example.classes.filter((c) => c.side === 'front')
  const ids = new Set(front.map((c) => c.id))

  server.plan = {
    ...example,
    classes: front,
    relations: example.relations.filter((r) => ids.has(r.from) && ids.has(r.to)),
  }
  await act(async () => server.push({ type: 'plan_changed' }))

  expect(await screen.findByText('HintButton')).toBeInTheDocument()
})

test('a plan with only one side has no switch', async () => {
  const server = new FakeServer()
  const back = example.classes.filter((c) => c.side === 'back')
  const ids = new Set(back.map((c) => c.id))
  server.plan = {
    ...example,
    classes: back,
    relations: example.relations.filter((r) => ids.has(r.from) && ids.has(r.to)),
  }
  server.install()
  render(<App />)

  await screen.findByText('HintPolicy')

  expect(screen.queryByRole('group', { name: 'Choose a side' })).not.toBeInTheDocument()
})

test('an old plan is drawn as today: one diagram with signatures, no switch', async () => {
  const server = new FakeServer()
  server.plan = old
  server.install()
  render(<App />)

  await screen.findByText('HintPolicy')

  expect(screen.queryByRole('group', { name: 'Choose a side' })).not.toBeInTheDocument()
  expect(element('class:Orchestrator.give_hint')).toHaveTextContent(
    'give_hint() -> AsyncIterator[str]',
  )
  expect(screen.getByText('LLMClient')).toBeInTheDocument()
})

test('cards show faded neighbours and marks on changed names', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('button', { name: 'Back end' }))
  await screen.findByText('HintPolicy')

  expect(element('class:LLMClient')).toHaveAttribute('data-faded', 'true')
  expect(element('class:Orchestrator')).not.toHaveAttribute('data-faded')
  expect(element('class:Orchestrator.give_hint').querySelector('.mark')).not.toBeNull()
  expect(element('class:LLMClient.stream').querySelector('.mark')).toBeNull()
})

test('a long architecture label is drawn on several lines', async () => {
  const server = new FakeServer()
  const long = 'a very long label that has to be wrapped over several lines'
  server.plan = {
    ...example,
    architecture: {
      ...example.architecture,
      edges: example.architecture.edges.map((e, i) => (i === 0 ? { ...e, label: long } : e)),
    },
  }
  server.install()
  render(<App />)
  await screen.findByRole('tablist')

  fireEvent.click(screen.getByRole('tab', { name: 'Architecture' }))

  await vi.waitFor(() =>
    expect(
      element(example.architecture.edges[0].id).querySelectorAll('tspan').length,
    ).toBeGreaterThan(1),
  )
  const lines = element(example.architecture.edges[0].id).querySelectorAll('tspan')
  expect(lines[0]).toHaveAttribute('dy', '0')
  expect(lines[1]).toHaveAttribute('dy', String(LABEL_LINE_HEIGHT))
  const x = lines[0].parentElement?.getAttribute('x')
  expect(x).not.toBeNull()
  expect(lines[1]).toHaveAttribute('x', x as string)
})

test('a test target on the other side flips the switch and outlines it', async () => {
  await loaded()
  fireEvent.click(screen.getByRole('tab', { name: 'Tests' }))

  fireEvent.click(screen.getAllByRole('button', { name: 'class:HintPolicy.max_hints' })[0])

  expect(screen.getByRole('button', { name: 'Back end' })).toHaveAttribute('aria-pressed', 'true')
  await vi.waitFor(() =>
    expect(element('class:HintPolicy.max_hints')).toHaveAttribute('data-focused', 'true'),
  )
})
