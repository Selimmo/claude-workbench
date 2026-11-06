// Pure helpers for the grill page: what is open, what may be submitted, how answers read.

import type { AnswerDraft, Grill, GrillDecision, GrillQuestion } from './grill'

export const openQuestions = (grill: Grill): GrillQuestion[] =>
  grill.rounds.flatMap((round) => round.questions.filter((q) => q.answer === null))

/** Whether the draft is a response to the question. A pick whose choice was revised away isn't. */
export function responded(question: GrillQuestion, draft?: AnswerDraft): boolean {
  if (!draft) return false
  if (draft.kind === 'choice') return question.choices.some((c) => c.id === draft.choice_id)
  return (draft.text ?? '').trim() !== ''
}

/** Every open question has a response, and it's the owner's turn (Claude has handled the log). */
export function canSubmit(grill: Grill, drafts: Record<string, AnswerDraft>): boolean {
  const open = openQuestions(grill)
  const ownersTurn = grill.handled === grill.log.length && !grill.done
  return ownersTurn && open.length > 0 && open.every((q) => responded(q, drafts[q.id]))
}

export type Pick = { kind: 'other' } | { kind: 'choice'; choice_id: string }

/** The draft after picking an option (a choice, or Other): the typed text moves along. */
export function pick(draft: AnswerDraft | undefined, option: Pick): AnswerDraft {
  const text = draft?.text ? { text: draft.text } : {}
  return { ...option, ...text }
}

const repliesTo = (question: GrillQuestion): number =>
  question.thread.filter((m) => m.author === 'claude').length

/** Claude has replied the limit: it must settle the question, so Other now counts as the answer. */
export const otherIsFinal = (question: GrillQuestion, max: number): boolean =>
  repliesTo(question) >= max

/** What an answered question shows: the answer, and the note under it if there is one. */
export function answerParts(question: GrillQuestion): { answer: string; note: string | null } {
  const { answer } = question
  if (!answer) return { answer: '', note: null }
  if (answer.kind !== 'choice') return { answer: answer.text ?? '', note: null }
  const label = question.choices.find((c) => c.id === answer.choice_id)?.label ?? ''
  return { answer: label, note: answer.text || null }
}

export interface TopicDecisions {
  topic: string
  decisions: (GrillDecision & { replaced: boolean })[]
}

const replacedIds = (grill: Grill): Set<string> =>
  new Set(grill.decisions.flatMap((d) => (d.replaces ? [d.replaces] : [])))

export const replacedCount = (grill: Grill): number => replacedIds(grill).size

/** Decisions grouped by topic in first-seen order; replaced ones only with `withReplaced`. */
export function decisionsByTopic(grill: Grill, withReplaced: boolean): TopicDecisions[] {
  const replaced = replacedIds(grill)
  const topics = new Map<string, TopicDecisions>()
  for (const d of grill.decisions) {
    // Topics keep the order of their first decision, even a replaced one that is hidden.
    const group = topics.get(d.topic) ?? { topic: d.topic, decisions: [] }
    topics.set(d.topic, group)
    if (!replaced.has(d.id) || withReplaced)
      group.decisions.push({ ...d, replaced: replaced.has(d.id) })
  }
  return [...topics.values()].filter((group) => group.decisions.length > 0)
}
