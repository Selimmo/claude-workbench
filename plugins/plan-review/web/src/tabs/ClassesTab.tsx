import { useMemo } from 'react'

import { classDiagram, classSides, currentShape, sideDiagram } from '../diagram'
import { DiagramView } from '../DiagramView'
import type { Plan, Side } from '../plan'

const LABELS: Record<Side, string> = { front: 'Front end', back: 'Back end' }

interface Props {
  plan: Plan
  /** The side shown; ignored for a plan written before sides existed. */
  side: Side | undefined
  onSide: (side: Side) => void
}

/** One side's classes at a time. A plan without sides is drawn whole, as it always was. */
export function ClassesTab({ plan, side, onSide }: Props) {
  const sides = classSides(plan)
  const diagram = useMemo(() => (side ? sideDiagram(plan, side) : classDiagram(plan)), [plan, side])
  return (
    <section className="classes">
      {currentShape(plan) && sides.length > 1 && (
        <div className="side-picker flow-picker" role="group" aria-label="Choose a side">
          {sides.map((s) => (
            <button key={s} aria-pressed={s === side} onClick={() => onSide(s)}>
              {LABELS[s]}
            </button>
          ))}
        </div>
      )}
      <DiagramView diagram={diagram} empty="No classes in this plan." />
    </section>
  )
}
