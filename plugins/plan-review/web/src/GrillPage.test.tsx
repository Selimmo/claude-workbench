import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import { App } from './App'
import { PANEL_KEY } from './grill/panelState'
import { FakeServer, message } from './test/fakeServer'
import { answered, grill, question } from './test/grillData'

function open(server: FakeServer) {
  server.plan = null
  server.install()
  window.history.pushState({}, '', '/grill')
  return render(<App />)
}

// A stand-in for browser storage, swapped in whole so it works whichever storage the
// runtime provides (jsdom's own, or Node's). Each test overrides the method it breaks.
function blockedStorage(): Storage {
  return {
    length: 0,
    clear: () => {},
    getItem: () => null,
    key: () => null,
    removeItem: () => {},
    setItem: () => {},
  }
}

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.history.pushState({}, '', '/')
})

test('each question shows its choices plus Other as radios, with no text box until a pick', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1'), question('q2')])
  open(server)

  expect(await screen.findByRole('heading', { name: '#42 Add hints' })).toBeInTheDocument()
  const first = screen.getByRole('group', { name: 'Question q1?' })
  expect(within(first).getByText('Why q1 matters.')).toBeInTheDocument()
  const choices = within(first).getAllByRole('radio')
  expect(choices.map((c) => c.getAttribute('aria-label'))).toEqual([
    'Choice a',
    'Choice b',
    'Other',
  ])
  expect(choices.some((c) => (c as HTMLInputElement).checked)).toBe(false)
  expect(within(first).queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: 'Your own answer' })).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: 'Ask back' })).not.toBeInTheDocument()
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

test('picking a choice opens one optional box with its hint, and the note is saved with the pick', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  const draftsPut = () => server.calls.filter((c) => c.method === 'PUT').map((c) => c.body)

  fireEvent.click(within(card).getByRole('radio', { name: 'Choice b' }))

  const box = within(card).getByPlaceholderText('Add a few words to your choice (optional)')
  expect(within(card).getAllByRole('textbox')).toHaveLength(1)
  expect(box).not.toBeRequired()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled())
  fireEvent.change(box, { target: { value: 'for now' } })
  await waitFor(() =>
    expect(draftsPut().at(-1)).toEqual({ kind: 'choice', choice_id: 'b', text: 'for now' }),
  )
})

test('picking Other opens a required box and Submit waits until it is filled', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  const draftsPut = () => server.calls.filter((c) => c.method === 'PUT').map((c) => c.body)

  fireEvent.click(within(card).getByRole('radio', { name: 'Other' }))

  const box = within(card).getByPlaceholderText('Type your own option, a question, or a comment')
  expect(within(card).getAllByRole('textbox')).toHaveLength(1)
  expect(box).toBeRequired()
  expect(screen.getByRole('button', { name: 'Submit answers' })).toBeDisabled()
  fireEvent.change(box, { target: { value: 'Something else' } })
  await waitFor(() => expect(draftsPut().at(-1)).toEqual({ kind: 'other', text: 'Something else' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled())
})

test("switching options moves the typed text to the new option's box", async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  const draftsPut = () => server.calls.filter((c) => c.method === 'PUT').map((c) => c.body)
  fireEvent.click(within(card).getByRole('radio', { name: 'Choice a' }))
  fireEvent.change(within(card).getByRole('textbox'), { target: { value: 'my note' } })
  await waitFor(() => expect(draftsPut().at(-1)).toMatchObject({ text: 'my note' }))

  fireEvent.click(within(card).getByRole('radio', { name: 'Choice b' }))

  expect(within(card).getAllByRole('textbox')).toHaveLength(1)
  expect(within(card).getByRole('textbox')).toHaveValue('my note')
  expect(
    within(
      within(card).getByRole('radio', { name: 'Choice b' }).closest('.option') as HTMLElement,
    ).getByRole('textbox'),
  ).toBeInTheDocument()
  await waitFor(() =>
    expect(draftsPut().at(-1)).toEqual({ kind: 'choice', choice_id: 'b', text: 'my note' }),
  )
})

test("after three replies, Other's hint says it now counts as the answer", async () => {
  const server = new FakeServer()
  const said = (author: 'owner' | 'claude', text: string) => ({ author, text, at: '' })
  server.grill = grill([
    question('q1', {
      thread: ['1', '2', '3'].flatMap((n) => [
        said('owner', `other ${n}`),
        said('claude', `reply ${n}`),
      ]),
    }),
  ])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })

  const other = within(card).getByRole('radio', { name: 'Other' })
  expect(other).toBeEnabled()
  fireEvent.click(other)

  expect(within(card).getByRole('textbox')).toHaveAttribute(
    'placeholder',
    expect.stringMatching(/counts as your answer/),
  )
})

test('a question shows Agent for old and new replies, and its final hint says the agent', async () => {
  const server = new FakeServer()
  server.grill = grill([
    question('q1', {
      thread: [
        message('owner', 'one?'),
        message('claude', 'old reply 1'),
        message('owner', 'two?'),
        message('claude', 'old reply 2'),
        message('owner', 'three?'),
        message('agent', 'new reply'),
      ],
    }),
  ])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })

  const rows = within(card).getAllByRole('listitem')
  expect(rows.map((r) => r.textContent)).toEqual([
    'You: one?',
    'Agent: old reply 1',
    'You: two?',
    'Agent: old reply 2',
    'You: three?',
    'Agent: new reply',
  ])
  expect(rows.map((r) => r.getAttribute('data-author'))).toEqual([
    'owner',
    'agent',
    'owner',
    'agent',
    'owner',
    'agent',
  ])
  fireEvent.click(within(card).getByRole('radio', { name: 'Other' }))
  expect(within(card).getByRole('textbox')).toHaveAttribute(
    'placeholder',
    'The agent has replied enough: this text now counts as your answer',
  )
})

test("the agent's reply to an Other shows under the question, which is open to pick again", async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  fireEvent.click(within(card).getByRole('radio', { name: 'Other' }))
  fireEvent.change(within(card).getByRole('textbox'), { target: { value: 'Which one?' } })
  const submit = screen.getByRole('button', { name: 'Submit answers' })
  await waitFor(() => expect(submit).toBeEnabled())
  fireEvent.click(submit)
  await waitFor(() =>
    expect(server.calls.filter((c) => c.url === '/api/grill/submit')).toHaveLength(1),
  )
  await waitFor(() => expect(within(card).getByText('Which one?')).toBeInTheDocument())
  expect(within(card).queryByRole('textbox')).not.toBeInTheDocument()

  server.grill!.rounds[0].questions[0].thread.push(message('claude', 'The first.'))
  server.grill!.rounds[0].questions[0].updated = true
  server.grill!.handled = server.grill!.log.length
  act(() => server.push({ type: 'grill_changed' }))

  expect(await within(card).findByText('The first.')).toBeInTheDocument()
  expect(within(card).getByText('Which one?')).toBeInTheDocument()
  expect(within(card).getByText('updated')).toBeInTheDocument()
  for (const radio of within(card).getAllByRole('radio')) expect(radio).not.toBeChecked()
  expect(within(card).queryByRole('textbox')).not.toBeInTheDocument()
})

test('drafts come back after a reload', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1'), question('q2')])
  server.grillDrafts = {
    q1: { kind: 'choice', choice_id: 'b' },
    q2: { kind: 'other', text: 'Mine' },
  }
  open(server)

  const first = await screen.findByRole('group', { name: 'Question q1?' })
  await waitFor(() => expect(within(first).getByRole('radio', { name: 'Choice b' })).toBeChecked())
  const second = screen.getByRole('group', { name: 'Question q2?' })
  expect(within(second).getByRole('radio', { name: 'Other' })).toBeChecked()
  expect(within(second).getByRole('textbox')).toHaveValue('Mine')
  expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled()
})

test('an answered question is a row with a tick, the answer in bold and the note under it', async () => {
  const server = new FakeServer()
  server.grill = grill([
    question('q1', { answer: answered('choice', { choice_id: 'b', text: 'for now' }) }),
    question('q2', { answer: answered('own', { text: 'Old own answer' }) }),
  ])
  server.grill.log = [{ kind: 'answers', text: null, at: '' }]
  server.grill.handled = 1
  open(server)

  const row = await screen.findByRole('button', { name: /Question q1\?/ })
  expect(row).toHaveTextContent('✓')
  expect(within(row).getByText('Choice b').tagName).toBe('STRONG')
  const note = within(row).getByText('for now')
  expect(note).toHaveClass('answer-note')
  expect(note.tagName).not.toBe('STRONG')
  expect(
    within(screen.getByRole('button', { name: /Question q2\?/ })).getByText('Old own answer')
      .tagName,
  ).toBe('STRONG')
  expect(screen.queryByText('Why q1 matters.')).not.toBeInTheDocument()
  fireEvent.click(row)
  expect(screen.getByText('Why q1 matters.')).toBeInTheDocument()
  expect(screen.getByText(/About b for q1/)).toBeInTheDocument()
})

test('the next round appears without a reload and answered rounds collapse', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1', { answer: answered('choice', { choice_id: 'b' }) })])
  server.grill.log = [{ kind: 'answers', text: null, at: '' }]
  server.grill.handled = 1
  open(server)
  await screen.findByRole('button', { name: /Question q1\?/ })

  server.grill = {
    ...server.grill,
    rounds: [...server.grill.rounds, { n: 2, questions: [question('q2')] }],
  }
  act(() => server.push({ type: 'grill_changed' }))

  expect(await screen.findByRole('group', { name: 'Question q2?' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Question q1\?/ })).toBeInTheDocument()
})

test('every round has a Round N heading, open or answered', async () => {
  const server = new FakeServer()
  server.grill = grill(
    [question('q1', { answer: answered('choice', { choice_id: 'a' }) })],
    [question('q2', { answer: answered('choice', { choice_id: 'b' }) }), question('q3')],
  )
  open(server)

  const one = await screen.findByRole('heading', { name: 'Round 1' })
  const two = screen.getByRole('heading', { name: 'Round 2' })
  const answeredRow = screen.getByRole('button', { name: /Question q2\?/ })
  const card = screen.getByRole('group', { name: 'Question q3?' })
  const before = (a: Element, b: Element) =>
    Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)
  expect(before(one, two)).toBe(true)
  expect(before(two, answeredRow)).toBe(true)
  expect(before(two, card)).toBe(true)
})

function withDecisions(server: FakeServer) {
  server.grill = grill([question('q1')])
  server.grill.decisions = [
    {
      id: 'd1',
      topic: 'Scoring',
      decision: 'A hint costs 2 points',
      choice: 'Points',
      why: 'It keeps hints rare',
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
    {
      id: 'd3',
      topic: 'Content',
      decision: 'Hints are written',
      choice: 'By authors',
      why: null,
      question_id: null,
      replaces: null,
    },
  ]
  server.grill.out_of_scope = ['Translating hints']
}

test('decisions are grouped by topic with their why, and replaced ones sit behind Show replaced', async () => {
  localStorage.clear()
  const server = new FakeServer()
  withDecisions(server)
  open(server)

  const panel = await screen.findByRole('complementary', { name: 'Decisions' })
  expect(
    within(panel)
      .getAllByRole('heading', { level: 3 })
      .map((h) => h.textContent),
  ).toEqual(['Scoring', 'Content', 'Out of scope'])
  const current = within(panel).getByText('A hint costs 3 points')
  expect(current.tagName).toBe('STRONG')
  expect(current.closest('li')).toHaveTextContent('More points')
  expect(within(panel).getByText('Hints are written').closest('li')).toHaveTextContent('By authors')
  expect(panel).not.toHaveTextContent('(from')
  expect(within(panel).queryByText('A hint costs 2 points')).not.toBeInTheDocument()
  expect(within(panel).getByText('Translating hints')).toBeInTheDocument()

  fireEvent.click(within(panel).getByRole('button', { name: 'Show replaced (1)' }))

  const old = within(panel).getByText('A hint costs 2 points').closest('li')
  expect(old).toHaveAttribute('data-replaced', 'true')
  expect(old).toHaveTextContent('Points')
  expect(old).toHaveTextContent('It keeps hints rare')
  expect(current.closest('li')).toHaveAttribute('data-replaced', 'false')
  expect(within(panel).queryByRole('button', { name: /Show replaced/ })).not.toBeInTheDocument()
})

test('with nothing replaced there is no Show replaced link', async () => {
  localStorage.clear()
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)

  const panel = await screen.findByRole('complementary', { name: 'Decisions' })
  expect(within(panel).queryByRole('button', { name: /Show replaced/ })).not.toBeInTheDocument()
  expect(within(panel).queryByRole('heading', { name: 'Out of scope' })).not.toBeInTheDocument()
})

test('the decisions list collapses and stays collapsed after a reload', async () => {
  localStorage.clear()
  const server = new FakeServer()
  withDecisions(server)
  const view = open(server)
  const toggle = await screen.findByRole('button', { name: 'Decisions' })
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByText('Hints are written')).toBeInTheDocument()

  fireEvent.click(toggle)

  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByText('Hints are written')).not.toBeInTheDocument()
  expect(localStorage.getItem(PANEL_KEY)).toBe('closed')

  view.unmount()
  const reloaded = open(server)
  const again = await screen.findByRole('button', { name: 'Decisions' })
  expect(again).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByText('Hints are written')).not.toBeInTheDocument()

  fireEvent.click(again)

  expect(localStorage.getItem(PANEL_KEY)).toBeNull()
  reloaded.unmount()
  open(server)
  expect(await screen.findByRole('button', { name: 'Decisions' })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
})

test('when browser storage cannot be written, the list still collapses', async () => {
  const setItem = vi.fn(() => {
    throw new Error('blocked')
  })
  vi.stubGlobal('localStorage', { ...blockedStorage(), setItem })
  const server = new FakeServer()
  withDecisions(server)
  open(server)
  const toggle = await screen.findByRole('button', { name: 'Decisions' })

  fireEvent.click(toggle)

  expect(setItem).toHaveBeenCalled()
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
})

test('when browser storage throws, the decisions list renders open', async () => {
  vi.stubGlobal('localStorage', {
    ...blockedStorage(),
    getItem: () => {
      throw new Error('blocked')
    },
  })
  const server = new FakeServer()
  withDecisions(server)
  open(server)

  expect(await screen.findByRole('button', { name: 'Decisions' })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
})

test('drafts the server pushes show without a reload', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })

  server.grillDrafts = { q1: { kind: 'other', text: 'From another tab' } }
  act(() => server.push({ type: 'grill_drafts_changed' }))

  await waitFor(() => expect(within(card).getByRole('textbox')).toHaveValue('From another tab'))
})

test('clearing the note on a choice sends the pick without a note', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  fireEvent.click(within(card).getByRole('radio', { name: 'Choice a' }))
  const note = within(card).getByRole('textbox')
  fireEvent.change(note, { target: { value: 'for now' } })

  fireEvent.change(note, { target: { value: '' } })

  await waitFor(() => {
    const puts = server.calls.filter((c) => c.method === 'PUT')
    expect(puts.at(-1)?.body).toEqual({ kind: 'choice', choice_id: 'a' })
  })
})

function doneGrill() {
  const server = new FakeServer()
  server.grill = grill([question('q1', { answer: answered('choice', { choice_id: 'a' }) })])
  server.grill.done = true
  server.grill.log = [{ kind: 'answers', text: null, at: '' }]
  server.grill.handled = 1
  return server
}

test('the final step asks Yes or No, and Yes confirms at once', async () => {
  const server = doneGrill()
  open(server)

  expect(await screen.findByText('Is this the shared understanding?')).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Not yet' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Submit answers' })).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Yes' }))

  expect(await screen.findByText('Confirmed')).toBeInTheDocument()
  expect(server.calls.filter((c) => c.url === '/api/grill/confirm')).toHaveLength(1)
  expect(screen.queryByRole('button', { name: 'Yes' })).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})

test('No opens a required box with its hint, and Send reopens the grill', async () => {
  const server = doneGrill()
  open(server)
  fireEvent.click(await screen.findByRole('button', { name: 'No' }))

  const box = screen.getByPlaceholderText("What's missing or wrong?")
  expect(box).toBeRequired()
  const send = screen.getByRole('button', { name: 'Send' })
  expect(send).toBeDisabled()
  fireEvent.change(box, { target: { value: 'Also ask about caching' } })
  fireEvent.click(send)

  await waitFor(() =>
    expect(server.calls).toContainEqual({
      method: 'POST',
      url: '/api/grill/reopen',
      body: { text: 'Also ask about caching' },
    }),
  )
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Yes' })).not.toBeInTheDocument())
})

test('after a No is sent, the next final step starts fresh at Yes or No', async () => {
  const server = doneGrill()
  open(server)
  fireEvent.click(await screen.findByRole('button', { name: 'No' }))
  fireEvent.change(screen.getByPlaceholderText("What's missing or wrong?"), {
    target: { value: 'X' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Yes' })).not.toBeInTheDocument())

  server.grill!.done = true
  await act(async () => server.push({ type: 'grill_changed' }))

  expect(await screen.findByRole('button', { name: 'Yes' })).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  expect(screen.getByPlaceholderText("What's missing or wrong?")).toHaveValue('')
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
})

test('a refusal shown earlier is gone from a later final step', async () => {
  const server = doneGrill()
  server.grillRefusal = 'waiting for the agent to handle your last action'
  open(server)
  fireEvent.click(await screen.findByRole('button', { name: 'Yes' }))
  await expectRefusal()

  server.grillRefusal = null
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  fireEvent.change(screen.getByPlaceholderText("What's missing or wrong?"), {
    target: { value: 'X' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Yes' })).not.toBeInTheDocument())
  server.grill!.done = true
  await act(async () => server.push({ type: 'grill_changed' }))

  expect(await screen.findByRole('button', { name: 'Yes' })).toBeInTheDocument()
  expect(screen.queryByText('waiting for the agent to handle your last action')).toBeNull()
})

test('confirming tells the agent: the banner waits for its answer', async () => {
  const server = doneGrill()
  open(server)

  fireEvent.click(await screen.findByRole('button', { name: 'Yes' }))

  const banner = await screen.findByRole('status', { name: 'Agent' })
  expect(banner).toHaveAttribute('data-state', 'waiting')
})

async function refusedGrill(): Promise<void> {
  const server = doneGrill()
  server.grillRefusal = 'waiting for the agent to handle your last action'
  open(server)
  await screen.findByRole('button', { name: 'Yes' })
}

async function expectRefusal(): Promise<void> {
  expect(await screen.findByText('waiting for the agent to handle your last action')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Yes' })).toBeInTheDocument()
}

test('a refused Yes says why and leaves the page as it was', async () => {
  await refusedGrill()

  fireEvent.click(screen.getByRole('button', { name: 'Yes' }))

  await expectRefusal()
})

test('a refused No says why and leaves the page as it was', async () => {
  await refusedGrill()
  fireEvent.click(screen.getByRole('button', { name: 'No' }))
  fireEvent.change(screen.getByPlaceholderText("What's missing or wrong?"), {
    target: { value: 'Also ask about caching' },
  })

  fireEvent.click(screen.getByRole('button', { name: 'Send' }))

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

test('the grill page shows the Agent banner and Resend', async () => {
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

    const banner = await screen.findByRole('status', { name: 'Agent' })
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
    question('q1'),
    question('q2', { answer: answered('choice', { choice_id: 'b' }) }),
  ])
  open(server)

  expect(await screen.findByRole('group', { name: 'Question q1?' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Question q2\?/ })).toBeInTheDocument()
  expect(screen.queryByRole('group', { name: 'Question q2?' })).not.toBeInTheDocument()
})

test('a refused draft or submit says why and does not keep the draft', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  server.grillRefusal = "it is the agent's turn"

  fireEvent.click(within(card).getByRole('radio', { name: 'Choice a' }))

  expect(await screen.findByText("it is the agent's turn")).toBeInTheDocument()
  await waitFor(() =>
    expect(within(card).getByRole('radio', { name: 'Choice a' })).not.toBeChecked(),
  )
  expect(screen.getByRole('button', { name: 'Submit answers' })).toBeDisabled()
})

test('a grill.json that does not parse shows its errors instead of loading forever', async () => {
  const server = new FakeServer()
  const line =
    '.plan-review/work/42/grill.json: Invalid JSON: key must be a string at line 1 column 2'
  server.grillErrors = [line]
  open(server)

  expect(await screen.findByText(line)).toBeInTheDocument()
  expect(screen.queryByText('Loading the grill…')).not.toBeInTheDocument()
})

test('a refused submit says why', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  fireEvent.click(await screen.findByRole('radio', { name: 'Choice a' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled())
  server.grillRefusal = 'waiting for the agent'

  fireEvent.click(screen.getByRole('button', { name: 'Submit answers' }))

  expect(await screen.findByText('waiting for the agent')).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: 'Choice a' })).toBeChecked() // kept, to submit again
  expect(screen.getByRole('button', { name: 'Submit answers' })).toBeEnabled()
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

const BAD_JSON = 'Invalid JSON: key must be a string at line 1 column 2'

test('a broken grill_drafts.json keeps the questions and decisions visible under a banner naming it', async () => {
  const line = `.plan-review/work/42/grill_drafts.json: ${BAD_JSON}`
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  server.brokenFiles['/api/grill/drafts'] = [line]
  open(server)

  expect(await screen.findByRole('group', { name: 'Question q1?' })).toBeInTheDocument()
  expect(await screen.findByRole('alert', { name: 'Broken files' })).toHaveTextContent(line)
})

test('the broken-files alert and the Agent banner share one sticky header', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  server.brokenFiles['/api/grill/drafts'] = [`.plan-review/work/42/grill_drafts.json: ${BAD_JSON}`]
  server.lastEvent = { type: 'grill', sent_at: new Date().toISOString(), answered: false }
  open(server)

  const alert = await screen.findByRole('alert', { name: 'Broken files' })
  const banner = await screen.findByRole('status')
  expect(alert.parentElement).toHaveClass('sticky-head')
  expect(banner.parentElement).toBe(alert.parentElement)
})

test('picking a choice while grill_drafts.json is broken shows the same named message', async () => {
  const line = `.plan-review/work/42/grill_drafts.json: ${BAD_JSON}`
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  server.brokenFiles['/api/grill/drafts'] = [line]
  server.brokenFiles['/api/grill/drafts/q1'] = [line]
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })

  fireEvent.click(within(card).getByRole('radio', { name: 'Choice a' }))

  await waitFor(() => expect(document.querySelector('p.error')).toHaveTextContent(line))
})

test("an invalid plan.json shows in the grill page's banner, a missing one does not", async () => {
  const line = `.plan-review/work/42/plan.json: summary: Field required`
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server) // plan is null: 404, the normal case while grilling
  await screen.findByRole('group', { name: 'Question q1?' })
  await vi.waitFor(() => expect(server.calls.some((c) => c.url === '/api/plan')).toBe(true))
  expect(screen.queryByRole('alert', { name: 'Broken files' })).not.toBeInTheDocument()

  server.brokenFiles['/api/plan'] = [line]
  act(() => server.push({ type: 'plan_changed' }))

  expect(await screen.findByRole('alert', { name: 'Broken files' })).toHaveTextContent(line)
})

test('a plan fetch that cannot reach the server is not listed as a broken file', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  await screen.findByRole('group', { name: 'Question q1?' })

  server.down.add('/api/plan')
  act(() => server.push({ type: 'plan_changed' }))
  await vi.waitFor(() =>
    expect(server.calls.filter((c) => c.url === '/api/plan').length).toBeGreaterThan(1),
  )
  await act(() => new Promise((resolve) => setTimeout(resolve, 20)))

  expect(screen.queryByRole('alert', { name: 'Broken files' })).not.toBeInTheDocument()
})

test('a 422 without errors is not shown as an empty broken-file line', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  server.rawBroken['/api/grill/drafts'] = { detail: [{ msg: 'bad' }] }
  open(server)
  await screen.findByRole('group', { name: 'Question q1?' })
  await vi.waitFor(() => expect(server.calls.some((c) => c.url === '/api/grill/drafts')).toBe(true))

  expect(screen.queryByRole('alert', { name: 'Broken files' })).not.toBeInTheDocument()
})

test('every text box on the grill page has a hint inside it', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1'), question('q2')])
  open(server)
  const first = await screen.findByRole('group', { name: 'Question q1?' })
  fireEvent.click(within(first).getByRole('radio', { name: 'Choice a' }))
  fireEvent.click(
    within(screen.getByRole('group', { name: 'Question q2?' })).getByRole('radio', {
      name: 'Other',
    }),
  )

  const boxes = screen.getAllByRole('textbox')
  expect(boxes).toHaveLength(2)
  for (const box of boxes) expect(box.getAttribute('placeholder')).toBeTruthy()
})

test('the No box has a hint too', async () => {
  const server = doneGrill()
  open(server)
  fireEvent.click(await screen.findByRole('button', { name: 'No' }))

  for (const box of screen.getAllByRole('textbox'))
    expect(box.getAttribute('placeholder')).toBeTruthy()
  expect(screen.getAllByRole('textbox')).toHaveLength(1)
})

test('a choice whose id is "other" is a real choice, apart from the Other radio', async () => {
  const server = new FakeServer()
  server.grill = grill([
    question('q1', {
      choices: [
        { id: 'mine', label: 'Mine', description: 'd1' },
        { id: 'other', label: 'Something else', description: 'd2' },
      ],
    }),
  ])
  open(server)
  const card = await screen.findByRole('group', { name: 'Question q1?' })
  const draftsPut = () => server.calls.filter((c) => c.method === 'PUT').map((c) => c.body)

  fireEvent.click(within(card).getByRole('radio', { name: 'Something else' }))
  await waitFor(() => expect(draftsPut().at(-1)).toEqual({ kind: 'choice', choice_id: 'other' }))
  expect(within(card).getByRole('radio', { name: 'Something else' })).toBeChecked()
  expect(within(card).getByRole('radio', { name: 'Other' })).not.toBeChecked()

  fireEvent.click(within(card).getByRole('radio', { name: 'Other' }))
  expect(within(card).getByRole('radio', { name: 'Other' })).toBeChecked()
  expect(within(card).getByRole('radio', { name: 'Something else' })).not.toBeChecked()
  expect(within(card).getAllByRole('textbox')).toHaveLength(1)
})

test("an answered row, opened, also shows the thread of the owner's messages and the agent's replies", async () => {
  const server = new FakeServer()
  server.grill = grill([
    question('q1', {
      answer: answered('own', { text: 'Final' }),
      thread: [message('owner', 'What about X?'), message('claude', 'X is fine.')],
    }),
  ])
  server.grill.log = [{ kind: 'answers', text: null, at: '' }]
  server.grill.handled = 1
  open(server)

  const row = await screen.findByRole('button', { name: /Question q1\?/ })
  expect(screen.queryByText('X is fine.')).not.toBeInTheDocument()
  fireEvent.click(row)
  expect(screen.getByText('What about X?')).toBeInTheDocument()
  expect(screen.getByText('X is fine.')).toBeInTheDocument()
})

test('the grill page reads what it missed after the viewer reconnects', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  await screen.findByRole('group', { name: 'Question q1?' })
  const reads = () => server.calls.filter((c) => c.url === '/api/grill').length
  const before = reads()

  server.grill!.rounds[0].questions[0].thread.push(message('claude', 'Said while away.'))
  server.dropSockets() // no push: only a reconnect can bring the new text

  expect(await screen.findByText('Said while away.', {}, { timeout: 3000 })).toBeInTheDocument()
  expect(reads()).toBeGreaterThan(before)
})

test('the Grill and Plan switch appears after a reconnect that missed the plan', async () => {
  const server = new FakeServer()
  server.grill = grill([question('q1')])
  open(server)
  await screen.findByRole('group', { name: 'Question q1?' })
  expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument()

  server.plan = (await import('../../examples/plan.json')).default
  server.dropSockets()

  expect(
    await screen.findByRole('navigation', { name: 'Pages' }, { timeout: 3000 }),
  ).toBeInTheDocument()
})

test('backticks show as code on the grill page', async () => {
  localStorage.clear()
  const server = new FakeServer()
  const tick = (name: string) => `see \`${name}\` here`
  const done = question('q1', {
    title: tick('t1'),
    explanation: tick('e1'),
    choices: [
      { id: 'a', label: tick('ans1'), description: tick('cd1') },
      { id: 'b', label: 'Other choice', description: '' },
    ],
    answer: answered('choice', { choice_id: 'a', text: tick('note1') }),
  })
  const open_ = question('q2', {
    title: tick('t2'),
    explanation: tick('e2'),
    choices: [{ id: 'a', label: tick('l2'), description: tick('d2') }],
    thread: [message('owner', tick('m2'))],
  })
  server.grill = grill([done], [open_])
  server.grill.decisions = [
    {
      id: 'd1',
      topic: tick('topic'),
      decision: tick('dec'),
      choice: tick('ch'),
      why: tick('why'),
      question_id: null,
      replaces: null,
    },
  ]
  server.grill.out_of_scope = [tick('oos')]
  server.grill.log = [{ kind: 'answers', text: null, at: '' }]
  server.grill.handled = 1
  open(server)

  fireEvent.click(await screen.findByRole('button', { name: /t1/ }))

  const chips = [...document.querySelectorAll('code.inline-code')].map((c) => c.textContent)
  for (const name of ['t1', 'ans1', 'note1', 'e1', 'cd1', 't2', 'e2', 'l2', 'd2', 'm2']) {
    expect(chips, name).toContain(name)
  }
  for (const name of ['topic', 'dec', 'ch', 'why', 'oos']) expect(chips, name).toContain(name)
  expect(document.querySelector('main')?.textContent ?? document.body.textContent).not.toContain(
    '`',
  )
})
