// Pure helpers for the grill page: what is open, what may be submitted, how answers read.

import type { AnswerDraft, Grill, GrillQuestion, GrillRound } from './grill'

export const openQuestions = (grill: Grill): GrillQuestion[] =>
  grill.rounds.flatMap((round) => round.questions.filter((q) => q.answer === null))

export const roundIsOpen = (round: GrillRound): boolean =>
  round.questions.some((q) => q.answer === null)

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

export const asksLeft = (question: GrillQuestion, max: number): number =>
  max - question.thread.filter((m) => m.author === 'owner').length

/** `title → answer`, the one line an answered question collapses to. */
export function answerLine(question: GrillQuestion): string {
  const { answer } = question
  if (!answer) return question.title
  if (answer.kind === 'own') return `${question.title} → ${answer.text ?? ''}`
  const label = question.choices.find((c) => c.id === answer.choice_id)?.label ?? ''
  return `${question.title} → ${label}${answer.text ? ` (${answer.text})` : ''}`
}
