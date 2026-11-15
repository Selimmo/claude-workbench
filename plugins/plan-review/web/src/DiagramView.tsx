import { useEffect, useMemo, useState } from 'react'

import { type Diagram, LABEL_LINE_HEIGHT, ROOMY, type Spacing } from './diagram'
import { FLOW_LINE_HEIGHT, tagSize } from './flowShapes'
import type { LaidDiagram, LaidEdge, LaidNode, Point } from './layout'
import { type Measure, canvasMeasure } from './measure'
import { type Overview, PanZoom } from './PanZoom'

const STATUSES = ['added', 'modified', 'removed', 'unchanged'] as const

function path(points: Point[]): string {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
}

function EdgeView({
  edge,
  tagged,
  measure,
}: {
  edge: LaidEdge
  tagged: boolean
  measure: Measure
}) {
  const d = path(edge.points)
  const size = tagged && edge.label ? tagSize(edge.label, measure) : null
  return (
    <g
      className="edge"
      data-element-id={edge.id}
      data-status={edge.status}
      data-main={edge.main || undefined}
      data-flow={tagged || undefined}
    >
      {/* An invisible wide stroke: the arrow is easy to click, not just its 1.5px line. */}
      <path className="hit" d={d} />
      <path className="line" d={d} markerEnd={edge.main ? 'url(#arrow-main)' : 'url(#arrow)'} />
      {size && edge.label && edge.labelAt && (
        <g className="tag">
          <rect
            x={edge.labelAt.x}
            y={edge.labelAt.y}
            width={size.width}
            height={size.height}
            rx={size.height / 2}
          />
          <text
            x={edge.labelAt.x + size.width / 2}
            y={edge.labelAt.y + size.height / 2}
            textAnchor="middle"
            dominantBaseline="central"
          >
            {edge.label}
          </text>
        </g>
      )}
      {!size && edge.label && edge.labelAt && (
        <text x={edge.labelAt.x} y={edge.labelAt.y + 12}>
          {edge.labelLines.map((line, i) => (
            <tspan key={i} x={edge.labelAt?.x} dy={i === 0 ? 0 : LABEL_LINE_HEIGHT}>
              {line}
            </tspan>
          ))}
        </text>
      )}
    </g>
  )
}

const ACTION_RADIUS = 8

function FlowShape({ node }: { node: LaidNode }) {
  const cx = node.x + node.width / 2
  const cy = node.y + node.height / 2
  const lines = node.lines ?? [node.title]
  const pill = node.shape === 'start' || node.shape === 'end'
  return (
    <g
      className="flow-node"
      data-element-id={node.id}
      data-status={node.status}
      data-shape={node.shape}
    >
      {node.shape === 'decision' ? (
        <polygon
          className="shape"
          points={`${cx},${node.y} ${node.x + node.width},${cy} ${cx},${node.y + node.height} ${node.x},${cy}`}
        />
      ) : (
        <rect
          className="shape"
          x={node.x}
          y={node.y}
          width={node.width}
          height={node.height}
          rx={pill ? node.height / 2 : ACTION_RADIUS}
        />
      )}
      <text
        x={cx}
        y={cy - ((lines.length - 1) * FLOW_LINE_HEIGHT) / 2}
        textAnchor="middle"
        dominantBaseline="central"
      >
        {lines.map((line, i) => (
          <tspan key={i} x={cx} dy={i === 0 ? 0 : FLOW_LINE_HEIGHT}>
            {line}
          </tspan>
        ))}
      </text>
    </g>
  )
}

export function Legend() {
  return (
    <ul className="legend" aria-label="Legend">
      {STATUSES.map((status) => (
        <li key={status} data-status={status}>
          {status}
        </li>
      ))}
    </ul>
  )
}

interface Props {
  diagram: Diagram
  empty: string
  direction?: 'RIGHT' | 'DOWN'
  spacing?: Spacing
  /** `flow`: flowchart shapes, line text in tags and a main path; `cards`: class and architecture boxes. */
  look?: 'cards' | 'flow'
}

function overviewOf(laid: LaidDiagram): Overview {
  return { boxes: laid.nodes, lines: laid.edges.map((e) => e.points) }
}

export function DiagramView({
  diagram,
  empty,
  direction = 'RIGHT',
  spacing = ROOMY,
  look = 'cards',
}: Props) {
  const [laid, setLaid] = useState<LaidDiagram | null>(null)
  const measure = useMemo(() => canvasMeasure(), [])

  useEffect(() => {
    let current = true
    // ELK is large; load it only when a diagram is first shown.
    void import('./layout')
      .then(({ layoutDiagram }) => layoutDiagram(diagram, direction, measure, spacing))
      .then((result) => current && setLaid(result))
    return () => {
      current = false
    }
  }, [diagram, direction, spacing, measure])

  if (diagram.nodes.length === 0) return <p className="empty">{empty}</p>
  if (laid === null) return <p className="status">Laying out…</p>
  return (
    <div className="diagram">
      <Legend />
      <PanZoom width={laid.width} height={laid.height} overview={overviewOf(laid)}>
        <svg className="edges" width={laid.width} height={laid.height}>
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="10"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              orient="auto"
            >
              <path d="M0,0 L10,5 L0,10 z" />
            </marker>
            <marker
              id="arrow-main"
              className="main"
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
          {laid.edges.map((edge) => (
            <EdgeView key={edge.id} edge={edge} tagged={look === 'flow'} measure={measure} />
          ))}
          {look === 'flow' && laid.nodes.map((node) => <FlowShape key={node.id} node={node} />)}
        </svg>
        {look === 'cards' &&
          laid.nodes.map((node) => (
            <div
              key={node.id}
              className="card"
              data-element-id={node.id}
              data-status={node.status}
              data-faded={node.faded || undefined}
              data-details={node.details || undefined}
              style={{ left: node.x, top: node.y, width: node.width, height: node.height }}
            >
              <div className="card-head">
                <strong>{node.title}</strong>
                {node.subtitle && <span className="kind">{node.subtitle}</span>}
              </div>
              <ul>
                {node.rows.map((row) => (
                  <li key={row.id} data-element-id={row.id} data-status={row.status}>
                    <code>{row.text}</code>
                    {row.marked && <span className="mark" aria-hidden="true" />}
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </PanZoom>
    </div>
  )
}
