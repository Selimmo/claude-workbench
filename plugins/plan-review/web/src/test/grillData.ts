// Builders for grill states in page and model tests.

import type { Answer, Grill, GrillQuestion } from '../grill'

export function question(id: string, extra: Partial<GrillQuestion> = {}): GrillQuestion {
  return {
    id,
    title: `Question ${id}?`,
    explanation: `Why ${id} matters.`,
    choices: [
      { id: 'a', label: 'Choice a', description: `About a for ${id}` },
      { id: 'b', label: 'Choice b', description: `About b for ${id}` },
    ],
    updated: false,
    thread: [],
    answer: null,
    ...extra,
  }
}

export function grill(...rounds: GrillQuestion[][]): Grill {
  return {
    label: '#42',
    title: 'Add hints',
    rounds: rounds.map((questions, i) => ({ n: i + 1, questions })),
    decisions: [],
    out_of_scope: [],
    done: false,
    confirmed_at: null,
    log: [],
    handled: 0,
    max_asks: 3,
  }
}

export const answered = (kind: Answer['kind'], extra: Partial<Answer> = {}): Answer => ({
  kind,
  choice_id: null,
  text: null,
  ...extra,
})
