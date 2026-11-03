import { fireEvent, render, screen, within } from '@testing-library/react'

import { App } from './App'
import { FakeServer } from './test/fakeServer'

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
  serve(422, { errors: ['summary: Field required'] })
  render(<App />)

  expect(await screen.findByRole('alert')).toHaveTextContent('summary: Field required')
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

  await screen.findByText('HintPolicy')
  expect(element('class:Orchestrator')).toHaveAttribute('data-status', 'modified')
  expect(element('class:Orchestrator.parse_command')).toHaveAttribute('data-status', 'removed')
  expect(element('class:Orchestrator.give_hint')).toHaveTextContent(
    'give_hint() -> AsyncIterator[str]',
  )
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
