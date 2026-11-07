import example from '../../examples/plan.json'
import type { Plan } from './plan'
import type { Thread } from './threads'
import { threadsFor } from './threadGroups'

const plan = example as Plan

const thread = (id: string, anchor: string, orphaned = false): Thread => ({
  id,
  anchor,
  messages: [{ author: 'owner', text: id, at: '2026-11-02T10:00:00Z' }],
  resolved: false,
  orphaned,
})

const threads = [
  thread('member', 'class:HintPolicy.next_level'),
  thread('edge', 'rel:orch-policy'),
  thread('step', 'flow:hint/2'),
  thread('tab', 'tab:classes'),
  thread('other-tab', 'tab:files'),
  thread('gone', 'class:Gone', true),
]

test('on a tab: threads pinned to its elements, threads on the tab itself, and all orphans', () => {
  const groups = threadsFor(threads, plan, 'classes')

  expect(groups.pinned.map((t) => t.id)).toEqual(['member', 'edge'])
  expect(groups.onTab.map((t) => t.id)).toEqual(['tab'])
  expect(groups.orphaned.map((t) => t.id)).toEqual(['gone'])
})

test('another tab gets its own pins and tab threads, and the same orphans', () => {
  const groups = threadsFor(threads, plan, 'flows')

  expect(groups.pinned.map((t) => t.id)).toEqual(['step'])
  expect(groups.onTab).toEqual([])
  expect(groups.orphaned.map((t) => t.id)).toEqual(['gone'])
})

test('unresolved count covers every thread, wherever it is', () => {
  const resolved = { ...thread('done', 'risk:1'), resolved: true }

  expect(threadsFor([...threads, resolved], plan, 'risks').unresolved).toBe(threads.length)
})

test('threads on the plan header are pinned on every tab', () => {
  const header = [thread('title', 'header:title'), thread('summary', 'header:summary')]

  for (const tab of ['classes', 'files'] as const)
    expect(threadsFor(header, plan, tab).pinned.map((t) => t.id)).toEqual(['title', 'summary'])
})

test("threads on the other side's classes are listed, not pinned", () => {
  const sided = [
    thread('here', 'class:HintButton'),
    thread('there', 'class:HintPolicy.next_level'),
    thread('edge', 'rel:orch-policy'),
  ]

  const front = threadsFor(sided, plan, 'classes', 'front')

  expect(front.pinned.map((t) => t.id)).toEqual(['here'])
  expect(front.otherSide.map((t) => t.id)).toEqual(['there', 'edge'])
  const none = threadsFor(sided, plan, 'classes')
  expect(none.pinned.map((t) => t.id)).toEqual(['here', 'there', 'edge'])
  expect(none.otherSide).toEqual([])
})

test('the other side is only a matter for the classes tab', () => {
  const there = [thread('there', 'class:HintPolicy.next_level')]

  for (const tab of ['files', 'tests'] as const)
    expect(threadsFor(there, plan, tab, 'front').otherSide).toEqual([])
})
