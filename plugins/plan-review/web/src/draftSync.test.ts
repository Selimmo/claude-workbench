import { DraftSync } from './draftSync'
import type { AnswerDraft } from './grill'

const text = (t: string): AnswerDraft => ({ kind: 'other', text: t })

// A fake `send` whose promises the test settles by hand.
function fakeSend() {
  const sent: { id: string; draft: AnswerDraft; ok: () => void; fail: (e: Error) => void }[] = []
  const send = (id: string, draft: AnswerDraft) =>
    new Promise<void>((resolve, reject) => {
      sent.push({ id, draft, ok: resolve, fail: reject })
    })
  return { sent, send }
}

test('a reload with no typing takes the server’s answers', () => {
  const sync = new DraftSync(fakeSend().send)
  const server = { q1: text('new') }
  const page = { q1: text('old'), q2: text('gone') }

  expect(sync.merge(server, page, sync.mark())).toEqual(server)
})

test('a question typed in after the mark keeps the page’s text', async () => {
  const { sent, send } = fakeSend()
  const sync = new DraftSync(send)
  const mark = sync.mark()
  const saved = sync.save('q1', text('mine'))
  sent[0]?.ok()
  await saved

  const server = { q1: text('older'), q2: text('theirs') }
  expect(sync.merge(server, { q1: text('mine') }, mark)).toEqual({
    q1: text('mine'),
    q2: text('theirs'),
  })
  expect(sync.merge(server, {}, mark)).toStrictEqual({ q2: text('theirs') })
})

test('a save still on its way at the mark keeps the page’s text even if it finishes first', async () => {
  const { sent, send } = fakeSend()
  const sync = new DraftSync(send)
  const saved = sync.save('q1', text('mine'))
  const mark = sync.mark()
  sent[0]?.ok()
  await saved

  const server = { q1: text('older') }
  expect(sync.merge(server, { q1: text('mine') }, mark)).toEqual({ q1: text('mine') })
  expect(sync.merge(server, { q1: text('mine') }, sync.mark())).toEqual(server)
})

test('saves for one question go one at a time, newest text last', async () => {
  const { sent, send } = fakeSend()
  const sync = new DraftSync(send)

  void sync.save('q1', text('a'))
  void sync.save('q1', text('ab'))
  void sync.save('q1', text('abc'))
  void sync.save('q2', text('other'))
  expect(sent.map((s) => [s.id, s.draft])).toEqual([
    ['q1', text('a')],
    ['q2', text('other')],
  ])

  sent[0]?.ok()
  await vi.waitFor(() => expect(sent).toHaveLength(3))
  expect(sent[2]?.id).toBe('q1')
  expect(sent[2]?.draft).toEqual(text('abc'))
})

test('a refused save fails, drops the waiting text and settles the question', async () => {
  const { sent, send } = fakeSend()
  const sync = new DraftSync(send)

  const first = sync.save('q1', text('a'))
  const second = sync.save('q1', text('ab'))
  sent[0]?.fail(new Error('refused'))

  await expect(first).rejects.toThrow('refused')
  await expect(second).rejects.toThrow('refused')
  expect(sent).toHaveLength(1)
  const server = { q1: text('server') }
  expect(sync.merge(server, { q1: text('ab') }, sync.mark())).toEqual(server)

  const next = sync.save('q1', text('x'))
  sent[1]?.ok()
  await next
  await new Promise((r) => setTimeout(r, 0))
  expect(sent.map((s) => s.draft)).toEqual([text('a'), text('x')])
})

test('settled waits until the waiting text has been sent', async () => {
  const { sent, send } = fakeSend()
  const sync = new DraftSync(send)
  let done = false
  void sync.save('q1', text('a'))
  void sync.save('q1', text('ab'))
  const settled = sync.settled().then(() => (done = true))

  sent[0]?.ok()
  await vi.waitFor(() => expect(sent).toHaveLength(2))
  await new Promise((r) => setTimeout(r, 0))
  expect(done).toBe(false)
  sent[1]?.ok()
  await settled
  expect(done).toBe(true)
})

test('settled resolves after a refused save and when nothing is saving', async () => {
  const { sent, send } = fakeSend()
  const sync = new DraftSync(send)
  await sync.settled()

  const saved = sync.save('q1', text('a'))
  const settled = sync.settled()
  sent[0]?.fail(new Error('refused'))

  await expect(saved).rejects.toThrow('refused')
  await settled
})

test('settled keeps waiting for saves that start while it waits', async () => {
  const { sent, send } = fakeSend()
  const sync = new DraftSync(send)
  let done = false
  void sync.save('q1', text('a'))
  const settled = sync.settled().then(() => (done = true))
  void sync.save('q2', text('b'))

  sent[0]?.ok()
  await new Promise((r) => setTimeout(r, 0))
  expect(done).toBe(false)
  sent[1]?.ok()
  await settled
  expect(done).toBe(true)
})
