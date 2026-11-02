// Sequence diagram geometry: participants as columns, steps as rows going down.

import type { SequenceFlow, Status } from './plan'

export const COLUMN_WIDTH = 200
export const HEAD_HEIGHT = 56
export const STEP_HEIGHT = 44

export interface LaidParticipant {
  id: string
  name: string
  status: Status
  x: number // centre of the column
}

export interface LaidMessage {
  id: string
  label: string
  status: Status
  fromX: number
  toX: number
  y: number
}

export interface LaidSequence {
  participants: LaidParticipant[]
  messages: LaidMessage[]
  width: number
  height: number
}

export function sequenceLayout(flow: SequenceFlow): LaidSequence {
  const columnOf = new Map(flow.participants.map((p, i) => [p.id, (i + 0.5) * COLUMN_WIDTH]))
  return {
    participants: flow.participants.map((p) => ({ ...p, x: columnOf.get(p.id) ?? 0 })),
    messages: flow.steps.map((step, i) => ({
      id: step.id,
      label: step.label,
      status: step.status,
      fromX: columnOf.get(step.from) ?? 0,
      toX: columnOf.get(step.to) ?? 0,
      y: HEAD_HEIGHT + (i + 0.5) * STEP_HEIGHT,
    })),
    width: flow.participants.length * COLUMN_WIDTH,
    height: HEAD_HEIGHT + flow.steps.length * STEP_HEIGHT,
  }
}
