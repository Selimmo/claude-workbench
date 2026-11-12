// The grill as the server returns it (see plan_review/grill/state.py and grill/drafts.py).

import type { Message } from './threads'

export interface Choice {
  id: string
  label: string
  description: string
}

export interface Answer {
  kind: 'choice' | 'own' | 'other'
  choice_id: string | null
  /** A note on the picked choice, or the Other text (or an old `own` answer). */
  text: string | null
}

export interface GrillQuestion {
  id: string
  title: string
  explanation: string
  /** The first choice is the recommendation. */
  choices: Choice[]
  /** The explanation or choices were revised in a reply. */
  updated: boolean
  /** The owner's Other answers and the agent's replies. */
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
  /** The agent says nothing is left to ask: the page asks Yes or No. */
  done: boolean
  confirmed_at: string | null
  log: OwnerAction[]
  /** How many owner actions the agent has answered; fewer than log.length means it's the agent's turn. */
  handled: number
  /** How many replies the agent may give to Others on one question; then it must settle. */
  max_replies: number
}

/** The owner's unsent answer to one question. */
export interface AnswerDraft {
  kind: 'choice' | 'other'
  choice_id?: string | null
  text?: string | null
}
