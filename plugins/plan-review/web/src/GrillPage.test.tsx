import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import { App } from './App'
import { FakeServer, message } from './test/fakeServer'
import { answered, grill, question } from './test/grillData'

function open(server: FakeServer) {
  server.plan = null
  server.install()
  window.history.pushState({}, '', '/grill')
  return render(<App />)
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.history.pushState({}, '', '/')
})

test('the grill page shows the round: explanations, choices with descriptions, recommendation first', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1'), question('q2')])
  open(server)

  expect(await screen.findByRole('heading', { name: '#42 Add hints' })).toBeInTheDocument()
  const first = screen.getByRole('group', { name: 'Question q1?' })
  expect(within(first).getByText('Why q1 matters.')).toBeInTheDocument()
  const choices = within(first).getAllByRole('radio')
  expect(choices.map((c) => c.getAttribute('aria-label'))).toEqual(['Choice a', 'Choice b'])
  expect(within(first).getByText('About b for q1')).toBeInTheDocument()
  expect(within(first).getByText('Recommended')).toBeInTheDocument()
  expect(within(first).getAllByText('Recommended')).toHaveLength(1)
  expect(screen.getByRole('group', { name: 'Question q2?' })).toBeInTheDocument()
})

test('picking a choice saves a draft and Submit waits for every open question', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1'), question('q2')])
  open(server)
  const submit = await screen.findByRole('button', { name: 'Submit answers' })
  expect(submit).toBeDisabled()

  fireEvent.click(
    within(screen.getByRole('group', { name: 'Question q1?' })).getByRole('radio', {
      name: 'Choice b',
    }),
  )

  await waitFor(() =>
    expect(server.calls).toContainEqual({
      method: 'PUT',
      url: '/api/grill/drafts/q1',
      body: { kind: 'choice', choice_id: 'b' },
    }),
  )
  expect(submit).toBeDisabled()

  fireEvent.click(
    within(screen.getByRole('group', { name: 'Question q2?' })).getByRole('radio', {
      name: 'Choice a',
    }),
  )
  await waitFor(() => expect(submit).toBeEnabled())
  fireEvent.click(submit)

  await waitFor(() =>
    expect(server.calls.filter((c) => c.url === '/api/grill/submit')).toHaveLength(1),
  )
})

test('an own answer, a note on a choice, and an ask back are each one response', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  const draftsPut = () => server.calls.filter((c) => c.method === 'PUT').map((c) => c.body)

  fireEvent.click(within(card).getByRole('radio', { name: 'Choice a' }))
  fireEvent.change(within(card).getByRole('textbox', { name: 'Note on your choice' }), {
    target: { value: 'for now' },
  })
  await waitFor(() =>
    expect(draftsPut().at(-1)).toEqual({ kind: 'choice', choice_id: 'a', text: 'for now' }),
  )

  fireEvent.change(within(card).getByRole('textbox', { name: 'Your own answer' }), {
    target: { value: 'Something else' },
  })
  await waitFor(() => expect(draftsPut().at(-1)).toEqual({ kind: 'own', text: 'Something else' }))
  expect(within(card).getByRole('radio', { name: 'Choice a' })).not.toBeChecked()

  fireEvent.change(within(card).getByRole('textbox', { name: 'Ask back' }), {
    target: { value: 'What does it cost?' },
  })
  await waitFor(() =>
    expect(draftsPut().at(-1)).toEqual({ kind: 'ask', text: 'What does it cost?' }),
  )
  expect(within(card).getByRole('textbox', { name: 'Your own answer' })).toHaveValue('')

  fireEvent.change(within(card).getByRole('textbox', { name: 'Ask back' }), {
    target: { value: '' },
  })
  await waitFor(() =>
    expect(server.calls.at(-1)).toMatchObject({ method: 'DELETE', url: '/api/grill/drafts/q1' }),
  )
})

test("an asked-back question shows Claude's reply beside it and is updated in place", async () => {
  const server = new FakeServer()
  const said = (author: 'owner' | 'claude', text: string) => ({ author, text, at: '' })
  server.grill = grill([
    question('q1', {
      updated: true,
      thread: [said('owner', 'Which?'), said('claude', 'The first.')],
    }),
    question('q2', {
      thread: [
        said('owner', '1'),
        said('claude', 'a'),
        said('owner', '2'),
        said('claude', 'b'),
        said('owner', '3'),
        said('claude', 'c'),
      ],
    }),
  ])
  open(server)
  const first = await screen.findByRole('group', { name: 'Question q1?' })

  expect(within(first).getByText('Which?')).toBeInTheDocument()
  expect(within(first).getByText('The first.')).toBeInTheDocument()
  expect(within(first).getByText('updated')).toBeInTheDocument()
  expect(within(first).getByRole('textbox', { name: 'Ask back' })).toBeEnabled()

  const spent = screen.getByRole('group', { name: 'Question q2?' })
  expect(within(spent).getByRole('textbox', { name: 'Ask back' })).toBeDisabled()
  expect(
    within(spent).getByText('3 questions asked; pick a choice or write your own answer'),
  ).toBeInTheDocument()
})

test('drafts come back after a reload', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1'), question('q2')])
  server.grillDrafts = {
    q1: { kind: 'choice', choice_id: 'b' },
    q2: { kind: 'own', text: 'Mine' },
  }
  open(server)

  const first = await screen.findByRole('group', { name: 'Question q1?' })
  await waitFor(() => expect(within(first).getByRole('radio', { name: 'Choice b' })).toBeChecked())
  const second = screen.getByRole('group', { name: 'Question q2?' })
  expect(within(second).getByRole('textbox', { name: 'Your own answer' })).toHaveValue('Mine')
  expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled()
})

test('the next round appears without a reload and answered rounds collapse', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1', { answer: answered('choice', { choice_id: 'b' }) })])
  server.grill.log = [{ kind: 'answers', text: null, at: '' }]
  server.grill.handled = 1
  open(server)

  const line = await screen.findByRole('button', { name: 'Question q1? → Choice b' })
  expect(screen.queryByText('Why q1 matters.')).not.toBeInTheDocument()
  fireEvent.click(line)
  expect(screen.getByText('Why q1 matters.')).toBeInTheDocument()

  server.grill = {
    ...server.grill,
    rounds: [...server.grill.rounds, { n: 2, questions: [question('q2')] }],
  }
  act(() => server.push({ type: 'grill_changed' }))

  expect(await screen.findByRole('group', { name: 'Question q2?' })).toBeInTheDocument()
})

test('settled decisions are listed with their question and replaced ones struck through', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  server.grill.decisions = [
    {
      id: 'd1',
      topic: 'Scoring',
      decision: 'A hint costs 2 points',
      choice: 'Points',
      why: null,
      question_id: 'q1',
      replaces: null,
    },
    {
      id: 'd2',
      topic: 'Scoring',
      decision: 'A hint costs 3 points',
      choice: 'More points',
      why: null,
      question_id: null,
      replaces: 'd1',
    },
  ]
  server.grill.out_of_scope = ['Translating hints']
  open(server)

  const panel = await screen.findByRole('complementary', { name: 'Decisions' })
  const old = within(panel).getByText('A hint costs 2 points').closest('li')
  expect(old).toHaveAttribute('data-replaced', 'true')
  expect(old).toHaveTextContent('Scoring')
  expect(old).toHaveTextContent('Points')
  expect(old).toHaveTextContent('Question q1?')
  expect(within(panel).getByText('A hint costs 3 points').closest('li')).toHaveAttribute(
    'data-replaced',
    'false',
  )
  expect(within(panel).getByRole('heading', { name: 'Out of scope' })).toBeInTheDocument()
  expect(within(panel).getByText('Translating hints')).toBeInTheDocument()
})

test('the panel has no Out of scope heading when nothing was left out', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)

  const panel = await screen.findByRole('complementary', { name: 'Decisions' })
  expect(within(panel).queryByRole('heading', { name: 'Out of scope' })).not.toBeInTheDocument()
})

test('drafts the server pushes show without a reload', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })

  server.grillDrafts = { q1: { kind: 'own', text: 'From another tab' } }
  act(() => server.push({ type: 'grill_drafts_changed' }))

  await waitFor(() =>
    expect(within(card).getByRole('textbox', { name: 'Your own answer' })).toHaveValue(
      'From another tab',
    ),
  )
})

test('clearing the note on a choice sends the pick without a note', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  fireEvent.click(within(card).getByRole('radio', { name: 'Choice a' }))
  const note = within(card).getByRole('textbox', { name: 'Note on your choice' })
  fireEvent.change(note, { target: { value: 'for now' } })

  fireEvent.change(note, { target: { value: '' } })

  await waitFor(() => {
    const puts = server.calls.filter((c) => c.method === 'PUT')
    expect(puts.at(-1)?.body).toEqual({ kind: 'choice', choice_id: 'a' })
  })
})

test('after a submit, the box of an asked-back question is empty again', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  fireEvent.change(within(card).getByRole('textbox', { name: 'Ask back' }), {
    target: { value: 'What does it cost?' },
  })
  const submit = screen.getByRole('button', { name: 'Submit answers' })
  await waitFor(() => expect(submit).toBeEnabled())

  fireEvent.click(submit)

  await waitFor(() =>
    expect(server.calls.filter((c) => c.url === '/api/grill/submit')).toHaveLength(1),
  )
  await waitFor(() =>
    expect(within(card).getByRole('textbox', { name: 'Ask back' })).toHaveValue(''),
  )
})

function doneGrill() {
  const server = new FakeServer()
  server.grill = grill([question('q1', { answer: answered('choice', { choice_id: 'a' }) })])
  server.grill.done = true
  server.grill.log = [{ kind: 'answers', text: null, at: '' }]
  server.grill.handled = 1
  return server
}

test('confirming makes the page read-only; Not yet sends a comment', async () => {
  const server = doneGrill()
  open(server)
  await screen.findByRole('button', { name: 'Confirm' })
  expect(screen.queryByRole('button', { name: 'Submit answers' })).not.toBeInTheDocument()

  fireEvent.change(screen.getByRole('textbox', { name: 'What is missing?' }), {
    target: { value: 'Also ask about caching' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Not yet' }))
  await waitFor(() =>
    expect(server.calls).toContainEqual({
      method: 'POST',
      url: '/api/grill/reopen',
      body: { text: 'Also ask about caching' },
    }),
  )

  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument(),
  ) // reopened: grilling goes on
  server.grill = doneGrill().grill
  act(() => server.push({ type: 'grill_changed' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }))

  expect(await screen.findByText('Confirmed')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})

test('confirming tells Claude: the banner waits for its answer', async () => {
  const server = doneGrill()
  open(server)

  fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }))

  const banner = await screen.findByRole('status', { name: 'Claude' })
  expect(banner).toHaveAttribute('data-state', 'waiting')
})

async function refusedGrill(): Promise<void> {
  const server = doneGrill()
  server.grillRefusal = 'waiting for Claude to handle your last action'
  open(server)
  await screen.findByRole('button', { name: 'Confirm' })
}

async function expectRefusal(): Promise<void> {
  expect(await screen.findByText('waiting for Claude to handle your last action')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
}

test('a refused Confirm says why and leaves the page as it was', async () => {
  await refusedGrill()

  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

  await expectRefusal()
})

test('a refused Not yet says why and leaves the page as it was', async () => {
  await refusedGrill()
  fireEvent.change(screen.getByRole('textbox', { name: 'What is missing?' }), {
    target: { value: 'Also ask about caching' },
  })

  fireEvent.click(screen.getByRole('button', { name: 'Not yet' }))

  await expectRefusal()
})

test('a plan appearing shows a Plan ready link and never switches pages', async () => {
  const server = doneGrill()
  server.grill!.confirmed_at = '2026-11-05T11:00:00Z'
  server.grill!.log.push({ kind: 'confirm', text: null, at: '' })
  server.grill!.handled = 1
  server.plan = null
  open(server)
  await screen.findByText('Confirmed')
  expect(screen.queryByRole('link', { name: 'Plan ready → open the plan' })).not.toBeInTheDocument()

  server.plan = (await import('../../examples/plan.json')).default
  act(() => server.push({ type: 'plan_changed' }))

  const link = await screen.findByRole('link', { name: 'Plan ready → open the plan' })
  expect(link).toHaveAttribute('href', '/')
  expect(window.location.pathname).toBe('/grill')
})

test('with a plan present, the top bar marks Grill as the current page', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  server.install()
  window.history.pushState({}, '', '/grill')
  render(<App />)

  const nav = await screen.findByRole('navigation', { name: 'Pages' })

  expect(within(nav).getByRole('link', { name: 'Grill' })).toHaveAttribute('aria-current', 'page')
  expect(within(nav).getByRole('link', { name: 'Plan' })).not.toHaveAttribute('aria-current')
})

test('the grill page shows the Claude banner and Resend', async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'], shouldAdvanceTime: true })
  try {
    const server = new FakeServer()
    server.grill = grill([question('q1')])
    open(server)
    const later = (ms: number) => act(async () => void (await vi.advanceTimersByTimeAsync(ms)))
    fireEvent.click(await screen.findByRole('radio', { name: 'Choice a' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Submit answers' }))

    const banner = await screen.findByRole('status', { name: 'Claude' })
    expect(banner).toHaveAttribute('data-state', 'waiting')

    await later(121_000)
    expect(banner).toHaveAttribute('data-state', 'no-response')
    fireEvent.click(screen.getByRole('button', { name: 'Resend' }))
    await waitFor(() => expect(server.calls.some((c) => c.url === '/api/resend')).toBe(true))

    server.status = { text: 'Answers received', done: false, at: '2026-11-05T10:00:00Z' }
    server.lastEvent = { ...server.lastEvent!, answered: true }
    await act(async () => server.push({ type: 'status_changed' }))
    expect(await screen.findByText('Answers received')).toBeInTheDocument()
  } finally {
    vi.useRealTimers()
  }
})

test('a round with some questions answered still shows those answers beside the open ones', async () => {
  const server = new FakeServer()
  server.grill = grill([
    question('q1', { thread: [message('owner', 'Why?')] }),
    question('q2', { answer: answered('choice', { choice_id: 'b' }) }),
  ])
  open(server)

  expect(await screen.findByRole('group', { name: 'Question q1?' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Question q2? → Choice b' })).toBeInTheDocument()
  expect(screen.queryByRole('group', { name: 'Question q2?' })).not.toBeInTheDocument()
})

test('a refused draft or submit says why and does not keep the draft', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  server.grillRefusal = "it is Claude's turn"

  fireEvent.click(within(card).getByRole('radio', { name: 'Choice a' }))

  expect(await screen.findByText("it is Claude's turn")).toBeInTheDocument()
  await waitFor(() =>
    expect(within(card).getByRole('radio', { name: 'Choice a' })).not.toBeChecked(),
  )
  expect(screen.getByRole('button', { name: 'Submit answers' })).toBeDisabled()
})

test('a grill.json that does not parse shows its errors instead of loading forever', async () => {
  const server = new FakeServer()
  server.grillErrors = ['grill.json: rounds: Field required']
  open(server)

  expect(await screen.findByText('grill.json: rounds: Field required')).toBeInTheDocument()
  expect(screen.queryByText('Loading the grill…')).not.toBeInTheDocument()
})

test('a refused submit says why', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  fireEvent.click(await screen.findByRole('radio', { name: 'Choice a' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled())
  server.grillRefusal = 'waiting for Claude'

  fireEvent.click(screen.getByRole('button', { name: 'Submit answers' }))

  expect(await screen.findByText('waiting for Claude')).toBeInTheDocument()
})

test('the Grill and Plan switch appears when the plan shows up, without a reload', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  await screen.findByRole('group', { name: 'Question q1?' })
  expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument()

  server.plan = (await import('../../examples/plan.json')).default
  act(() => server.push({ type: 'plan_changed' }))

  expect(await screen.findByRole('navigation', { name: 'Pages' })).toBeInTheDocument()
})
