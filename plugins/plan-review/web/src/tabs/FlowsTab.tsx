import { useMemo, useState } from 'react'

import { flowchartDiagram } from '../diagram'
import { DiagramView, Legend } from '../DiagramView'
import { type Overview, PanZoom } from '../PanZoom'
import type { Flow, Flowchart, Plan, SequenceFlow } from '../plan'
import { canvasMeasure } from '../measure'
import { sequenceLayout } from '../sequence'

const BOX_HEIGHT = 32

function SequenceView({ flow }: { flow: SequenceFlow }) {
  const laid = useMemo(() => sequenceLayout(flow, canvasMeasure()), [flow])
  const overview: Overview = {
    boxes: laid.participants.map((p) => ({
      x: p.x - p.width / 2,
      y: 8,
      width: p.width,
      height: BOX_HEIGHT,
    })),
    lines: laid.messages.map((m) => [
      { x: m.fromX, y: m.y },
      { x: m.toX, y: m.y },
    ]),
  }
  return (
    <div className="diagram">
      <Legend />
      <PanZoom width={laid.width} height={laid.height} overview={overview}>
        <svg
          className="sequence"
          width={laid.width}
          height={laid.height}
          role="img"
          aria-label={flow.title}
        >
          {laid.participants.map((p) => (
            <g key={p.id} className="participant" data-element-id={p.id} data-status={p.status}>
              <line className="hit" x1={p.x} y1={BOX_HEIGHT + 8} x2={p.x} y2={laid.height} />
              <line x1={p.x} y1={BOX_HEIGHT + 8} x2={p.x} y2={laid.height} />
              <rect x={p.x - p.width / 2} y={8} width={p.width} height={BOX_HEIGHT} rx={6} />
              <text x={p.x} y={8 + BOX_HEIGHT / 2 + 4} textAnchor="middle">
                {p.name}
              </text>
            </g>
          ))}
          {laid.messages.map((m) => (
            <g key={m.id} className="message" data-element-id={m.id} data-status={m.status}>
              {/* The arrow and the label above it are one target. */}
              <line className="hit" x1={m.fromX} y1={m.y} x2={m.toX} y2={m.y} />
              <rect
                className="hit-area"
                x={m.fromX === m.toX ? m.fromX - m.labelWidth / 2 : Math.min(m.fromX, m.toX)}
                y={m.y - 20}
                // A step to itself has no arrow length: its label is the target.
                width={m.fromX === m.toX ? m.labelWidth : Math.abs(m.toX - m.fromX)}
                height={20}
              />
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
      </PanZoom>
    </div>
  )
}

function FlowchartView({ flow }: { flow: Flowchart }) {
  const diagram = useMemo(() => flowchartDiagram(flow), [flow])
  return <DiagramView diagram={diagram} direction="DOWN" empty="This flowchart is empty." />
}

/** One flow at a time, so each diagram gets the whole space; the picker switches. */
const idsOf = (flow: Flow) =>
  flow.kind === 'sequence'
    ? [flow.id, ...flow.participants.map((p) => p.id), ...flow.steps.map((s) => s.id)]
    : [flow.id, ...flow.nodes.map((n) => n.id), ...flow.edges.map((e) => e.id)]

/** `focus`: an element to show, e.g. a test's target; its flow is shown first. */
export function FlowsTab({ plan, focus = null }: { plan: Plan; focus?: string | null }) {
  const [chosen, setChosen] = useState<string | null>(null)
  if (plan.flows.length === 0) return <p className="empty">No flows in this plan.</p>
  const flow =
    plan.flows.find((f) => f.id === chosen) ??
    plan.flows.find((f) => focus !== null && idsOf(f).includes(focus)) ??
    plan.flows[0]
  return (
    <section className="flow">
      <div className="flow-head">
        <h2 data-element-id={flow.id}>
          {flow.title} <span className="kind">{flow.kind}</span>
        </h2>
        {plan.flows.length > 1 && (
          <div className="flow-picker" role="group" aria-label="Choose a flow">
            {plan.flows.map((f) => (
              <button key={f.id} aria-pressed={f.id === flow.id} onClick={() => setChosen(f.id)}>
                {f.title}
              </button>
            ))}
          </div>
        )}
      </div>
      {flow.kind === 'sequence' ? (
        <SequenceView key={flow.id} flow={flow} />
      ) : (
        <FlowchartView key={flow.id} flow={flow} />
      )}
    </section>
  )
}
