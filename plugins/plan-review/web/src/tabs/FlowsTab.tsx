import { useMemo } from 'react'

import { flowchartDiagram } from '../diagram'
import { DiagramView } from '../DiagramView'
import type { Flowchart, Plan, SequenceFlow } from '../plan'
import { sequenceLayout } from '../sequence'

const BOX_WIDTH = 150
const BOX_HEIGHT = 32

function SequenceView({ flow }: { flow: SequenceFlow }) {
  const laid = sequenceLayout(flow)
  return (
    <svg
      className="sequence"
      width={laid.width}
      height={laid.height}
      role="img"
      aria-label={flow.title}
    >
      {laid.participants.map((p) => (
        <g key={p.id} className="participant" data-element-id={p.id} data-status={p.status}>
          <line x1={p.x} y1={BOX_HEIGHT + 8} x2={p.x} y2={laid.height} />
          <rect x={p.x - BOX_WIDTH / 2} y={8} width={BOX_WIDTH} height={BOX_HEIGHT} rx={6} />
          <text x={p.x} y={8 + BOX_HEIGHT / 2 + 4} textAnchor="middle">
            {p.name}
          </text>
        </g>
      ))}
      {laid.messages.map((m) => (
        <g key={m.id} className="message" data-element-id={m.id} data-status={m.status}>
          <line x1={m.fromX} y1={m.y} x2={m.toX} y2={m.y} markerEnd="url(#seq-arrow)" />
          <text x={(m.fromX + m.toX) / 2} y={m.y - 6} textAnchor="middle">
            {m.label}
          </text>
        </g>
      ))}
      <defs>
        <marker
          id="seq-arrow"
          viewBox="0 0 10 10"
          refX="10"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto"
        >
          <path d="M0,0 L10,5 L0,10 z" />
        </marker>
      </defs>
    </svg>
  )
}

function FlowchartView({ flow }: { flow: Flowchart }) {
  const diagram = useMemo(() => flowchartDiagram(flow), [flow])
  return <DiagramView diagram={diagram} direction="DOWN" empty="This flowchart is empty." />
}

export function FlowsTab({ plan }: { plan: Plan }) {
  if (plan.flows.length === 0) return <p className="empty">No flows in this plan.</p>
  return plan.flows.map((flow) => (
    <section key={flow.id} className="flow">
      <h2 data-element-id={flow.id}>
        {flow.title} <span className="kind">{flow.kind}</span>
      </h2>
      {flow.kind === 'sequence' ? (
        <div className="sequence-scroll">
          <SequenceView flow={flow} />
        </div>
      ) : (
        <FlowchartView flow={flow} />
      )}
    </section>
  ))
}
