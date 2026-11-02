import { useEffect, useState } from 'react'

import type { Diagram } from './diagram'
import type { LaidDiagram, LaidEdge, Point } from './layout'
import { PanZoom } from './PanZoom'

const STATUSES = ['added', 'modified', 'removed', 'unchanged'] as const

function path(points: Point[]): string {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
}

function EdgeView({ edge }: { edge: LaidEdge }) {
  return (
    <g className="edge" data-element-id={edge.id} data-status={edge.status}>
      <path d={path(edge.points)} markerEnd="url(#arrow)" />
      {edge.label && edge.labelAt && (
        <text x={edge.labelAt.x} y={edge.labelAt.y + 12}>
          {edge.label}
        </text>
      )}
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

export function DiagramView({ diagram, empty }: { diagram: Diagram; empty: string }) {
  const [laid, setLaid] = useState<LaidDiagram | null>(null)

  useEffect(() => {
    let current = true
    // ELK is large; load it only when a diagram is first shown.
    void import('./layout')
      .then(({ layoutDiagram }) => layoutDiagram(diagram))
      .then((result) => current && setLaid(result))
    return () => {
      current = false
    }
  }, [diagram])

  if (diagram.nodes.length === 0) return <p className="empty">{empty}</p>
  if (laid === null) return <p className="status">Laying out…</p>
  return (
    <>
      <Legend />
      <PanZoom width={laid.width} height={laid.height}>
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
          </defs>
          {laid.edges.map((edge) => (
            <EdgeView key={edge.id} edge={edge} />
          ))}
        </svg>
        {laid.nodes.map((node) => (
          <div
            key={node.id}
            className="card"
            data-element-id={node.id}
            data-status={node.status}
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
                </li>
              ))}
            </ul>
          </div>
        ))}
      </PanZoom>
    </>
  )
}
