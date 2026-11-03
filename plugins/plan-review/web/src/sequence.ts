// Sequence diagram geometry: participants as columns, steps as rows going down.
// Boxes are as wide as their names, and columns are pushed apart until every box and
// every step label fits, so no text overlaps or spills.

import { type Measure, estimate } from './measure'
import type { SequenceFlow, Status } from './plan'

export const COLUMN_WIDTH = 200 // the least distance between neighbouring columns
export const HEAD_HEIGHT = 56
export const STEP_HEIGHT = 44
export const BOX_MIN_WIDTH = 150
export const BOX_PADDING = 16 // either side of a participant's name
export const BOX_GAP = 24 // between neighbouring participant boxes
export const LABEL_PADDING = 12 // either side of a step label, inside its arrow's span

export interface LaidParticipant {
  id: string
  name: string
  status: Status
  x: number // centre of the column
  width: number // of the name's box
}

export interface LaidMessage {
  id: string
  label: string
  status: Status
  fromX: number
  toX: number
  y: number
  labelWidth: number
}

export interface LaidSequence {
  participants: LaidParticipant[]
  messages: LaidMessage[]
  width: number
  height: number
}

type SequenceMeasure = (text: string, kind: 'participant' | 'label') => number

export function sequenceLayout(
  flow: SequenceFlow,
  measure: SequenceMeasure = estimate as Measure,
): LaidSequence {
  const index = new Map(flow.participants.map((p, i) => [p.id, i]))
  const widths = flow.participants.map((p) =>
    Math.max(BOX_MIN_WIDTH, measure(p.name, 'participant') + 2 * BOX_PADDING),
  )
  // gaps[i]: distance between the centres of column i and column i + 1.
  const gaps = widths
    .slice(1)
    .map((w, i) => Math.max(COLUMN_WIDTH, widths[i] / 2 + w / 2 + BOX_GAP))
  // Short spans first, so a long arrow only widens what its shorter neighbours left.
  const spans = flow.steps
    .map((s) => ({ a: index.get(s.from) ?? 0, b: index.get(s.to) ?? 0, label: s.label }))
    .map(({ a, b, label }) => ({ from: Math.min(a, b), to: Math.max(a, b), label }))
    .sort((x, y) => x.to - x.from - (y.to - y.from))
  // Room a step to itself needs beyond the first or last column (its label is centred).
  let before = 0
  let after = 0
  for (const { from, to, label } of spans) {
    const need = measure(label, 'label') + 2 * LABEL_PADDING
    if (from === to) {
      if (from === 0) before = Math.max(before, need / 2)
      if (to === gaps.length) after = Math.max(after, need / 2)
      // A step to itself: its label is centred on the column, so both sides need half.
      if (from > 0) gaps[from - 1] = Math.max(gaps[from - 1], need / 2 + widths[from - 1] / 2)
      if (to < gaps.length) gaps[to] = Math.max(gaps[to], need / 2 + widths[to + 1] / 2)
      continue
    }
    const have = gaps.slice(from, to).reduce((sum, g) => sum + g, 0)
    if (have < need) gaps[to - 1] += need - have
  }

  const edge = (w: number) => Math.max(COLUMN_WIDTH / 2, w / 2 + BOX_GAP)
  const xs = [Math.max(edge(widths[0] ?? 0), before)]
  for (const gap of gaps) xs.push(xs[xs.length - 1] + gap)
  const columnOf = (id: string) => xs[index.get(id) ?? 0] ?? 0
  const last = xs.length - 1
  return {
    participants: flow.participants.map((p, i) => ({ ...p, x: xs[i], width: widths[i] })),
    messages: flow.steps.map((step, i) => ({
      id: step.id,
      label: step.label,
      status: step.status,
      fromX: columnOf(step.from),
      toX: columnOf(step.to),
      y: HEAD_HEIGHT + (i + 0.5) * STEP_HEIGHT,
      labelWidth: measure(step.label, 'label'),
    })),
    width: last < 0 ? 0 : xs[last] + Math.max(edge(widths[last]), after),
    height: HEAD_HEIGHT + flow.steps.length * STEP_HEIGHT,
  }
}
