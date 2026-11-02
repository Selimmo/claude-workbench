import example from '../../examples/plan.json'
import { architectureDiagram, classDiagram } from './diagram'
import type { Plan } from './plan'

const plan = example as Plan

test('class diagram: a node per class with member rows, an edge per relation', () => {
  const diagram = classDiagram(plan)

  const policy = diagram.nodes.find((n) => n.id === 'class:HintPolicy')
  expect(policy).toMatchObject({ title: 'HintPolicy', subtitle: 'class', status: 'added' })
  expect(policy?.rows).toEqual([
    { id: 'class:HintPolicy.max_hints', text: 'max_hints: int = 3', status: 'added' },
    {
      id: 'class:HintPolicy.next_level',
      text: 'next_level(given: int) -> HintLevel | None',
      status: 'added',
    },
  ])
  expect(diagram.edges).toContainEqual({
    id: 'rel:orch-policy',
    source: 'class:Orchestrator',
    target: 'class:HintPolicy',
    label: 'uses',
    status: 'added',
  })
})

test('architecture diagram: components with their kind, labelled edges, no rows', () => {
  const diagram = architectureDiagram(plan)

  expect(diagram.nodes[0]).toEqual({
    id: 'arch:web',
    title: 'Web client',
    subtitle: 'client',
    status: 'modified',
    rows: [],
  })
  expect(diagram.edges.find((e) => e.id === 'arch:agent-db')?.label).toBeNull()
  expect(diagram.edges.find((e) => e.id === 'arch:agent-ollama')?.label).toBe('HTTP')
})
