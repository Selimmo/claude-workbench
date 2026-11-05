// The grill as the server returns it (see plan_review/grill.py and grill_drafts.py).

import type { Message } from './threads'

export interface Choice {
  id: string
  label: string
  description: string
}

export interface Answer {
  kind: 'choice' | 'own'
  choice_id: string | null
  /** The own answer, or a note on the picked choice. */
  text: string | null
}

export interface GrillQuestion {
  id: string
  title: string
  explanation: string
  /** The first choice is the recommendation. */
  choices: Choice[]
  /** The explanation or choices were revised after an ask back. */
  updated: boolean
  /** Asks back (owner) and replies (claude). */
  thread: Message[]
  /** Null while the question is open. */
  answer: Answer | null
}

export interface GrillRound {
  n: number
  questions: GrillQuestion[]
}

export interface GrillDecision {
  id: string
  topic: string
  decision: string
  choice: string
  why: string | null
  question_id: string | null
  replaces: string | null
}

export interface OwnerAction {
  kind: 'answers' | 'reopen' | 'confirm'
  text: string | null
  at: string
}

export interface Grill {
  /** The run's label, `#42` or its name. */
  label: string
  title: string
  rounds: GrillRound[]
  decisions: GrillDecision[]
  out_of_scope: string[]
  /** Claude says nothing is left to ask: the page offers Confirm. */
  done: boolean
  confirmed_at: string | null
  log: OwnerAction[]
  /** How many owner actions Claude has answered; fewer than log.length means it's Claude's turn. */
  handled: number
  /** How many asks back one question may have. */
  max_asks: number
}

/** The owner's unsent answer to one question. */
export interface AnswerDraft {
  kind: 'choice' | 'own' | 'ask'
  choice_id?: string | null
  text?: string | null
}
