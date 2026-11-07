import example from '../../examples/plan.json'
import old from '../../tests/fixtures/plan-0.1.11.json'
import after56 from '../../examples/before-after/56/plan.json'
import before56 from '../../examples/before-after/56/plan-0.1.11.json'
import {
  architectureDiagram,
  classDetails,
  classDiagram,
  classSides,
  currentShape,
  flowchartDiagram,
  sideDiagram,
  sideOf,
} from './diagram'
import type { Plan } from './plan'

const plan = example as Plan
const oldPlan = old as Plan

test('class diagram: a node per class with member rows, an edge per relation', () => {
  const diagram = classDiagram(oldPlan)

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

test('flowchart diagram: a node per step, labelled edges', () => {
  const chart = plan.flows[1]
  if (chart.kind !== 'flowchart') throw new Error('example flow 2 is a flowchart')

  const diagram = flowchartDiagram(chart)

  expect(diagram.nodes[1]).toEqual({
    id: 'flow:level/check',
    title: 'hints_given < max_hints?',
    subtitle: null,
    status: 'added',
    rows: [],
  })
  expect(diagram.edges.map((e) => e.label)).toEqual([null, 'yes', 'no'])
})

const withClasses = (extra: Plan['classes']): Plan => ({
  ...plan,
  classes: [...plan.classes, ...extra],
})
const lone: Plan['classes'][number] = {
  id: 'class:Lone',
  name: 'Lone',
  kind: 'class',
  side: 'back',
  status: 'unchanged',
  members: [],
}

test('currentShape is true only when every class has a side', () => {
  expect(currentShape(plan)).toBe(true)
  expect(currentShape(oldPlan)).toBe(false)
  expect(currentShape({ ...plan, classes: [] })).toBe(false)
  expect(currentShape(before56 as Plan)).toBe(false)
})

test('classSides lists the sides that have classes, front first', () => {
  expect(classSides(plan)).toEqual(['front', 'back'])
  expect(classSides({ ...plan, classes: plan.classes.filter((c) => c.side === 'back') })).toEqual([
    'back',
  ])
})

test('sideDiagram draws one side: changed in full, linked unchanged faded, the rest left out', () => {
  const back = sideDiagram(withClasses([lone]), 'back')
  const ids = back.nodes.map((n) => n.id)

  expect(ids).not.toContain('class:HintButton')
  expect(ids).not.toContain('class:Lone')
  expect(back.nodes.find((n) => n.id === 'class:LLMClient')?.faded).toBe(true)
  expect(back.nodes.find((n) => n.id === 'class:Orchestrator')?.faded).toBeFalsy()
  expect(sideDiagram(plan, 'front').nodes.map((n) => n.id)).toEqual([
    'class:HintButton',
    'class:InterviewScreen',
  ])
})

test('an unchanged class whose member changed is changed, so it is drawn in full', () => {
  const banner: Plan['classes'][number] = {
    ...lone,
    id: 'class:Banner',
    name: 'Banner',
    members: [
      {
        id: 'class:Banner.css',
        name: 'css',
        kind: 'property',
        signature: '.b {}',
        status: 'modified',
      },
    ],
  }

  const node = sideDiagram(withClasses([banner]), 'back').nodes.find((n) => n.id === 'class:Banner')

  expect(node).toBeDefined()
  expect(node?.faded).toBeFalsy()
})

test('a class box is titled with its bases and lists member names, properties first', () => {
  const back = sideDiagram(plan, 'back')

  const level = back.nodes.find((n) => n.id === 'class:HintLevel')
  expect(level).toMatchObject({ title: 'HintLevel: Enum', subtitle: 'enum', details: true })
  const orch = back.nodes.find((n) => n.id === 'class:Orchestrator')
  expect(orch?.title).toBe('Orchestrator')
  expect(orch?.rows.map((r) => r.text)).toEqual([
    'hints_given',
    'give_hint()',
    'parse_command()',
    'on_event()',
  ])
  expect(orch?.rows.map((r) => r.marked)).toEqual([true, true, true, true])
  const llm = back.nodes.find((n) => n.id === 'class:LLMClient')
  expect(llm?.rows).toEqual([
    { id: 'class:LLMClient.stream', text: 'stream()', status: 'unchanged', marked: false },
  ])
})

test('a member with no name shows its signature instead', () => {
  const nameless = withClasses([
    {
      ...lone,
      status: 'added',
      members: [{ id: 'class:Lone.x', signature: 'x: int', status: 'added' }],
    },
  ])

  const node = sideDiagram(nameless, 'back').nodes.find((n) => n.id === 'class:Lone')

  expect(node?.rows[0].text).toBe('x: int')
})

test('sideDiagram keeps only relations with both ends drawn', () => {
  const back = sideDiagram(plan, 'back')

  expect(back.edges.map((e) => e.id)).toContain('rel:orch-llm')
  expect(back.edges.every((e) => e.label !== null)).toBe(true)
  expect(sideDiagram(plan, 'front').edges.map((e) => e.id)).toEqual(['rel:screen-button'])
  const dangling = {
    ...plan,
    relations: [...plan.relations, { ...plan.relations[0], id: 'rel:x', to: 'class:HintButton' }],
  }
  expect(sideDiagram(dangling, 'back').edges.map((e) => e.id)).not.toContain('rel:x')
})

test('the converted #56 plan splits into a front and a back diagram', () => {
  const converted = after56 as Plan

  expect(currentShape(converted)).toBe(true)
  expect(classSides(converted)).toEqual(['front', 'back'])
  const front = sideDiagram(converted, 'front').nodes
  const back = sideDiagram(converted, 'back').nodes
  expect(front.length).toBeGreaterThan(0)
  expect(back.length).toBeGreaterThan(0)
  const frontIds = new Set(front.map((n) => n.id))
  expect(back.filter((n) => frontIds.has(n.id))).toEqual([])
  for (const [side, nodes] of [
    ['front', front],
    ['back', back],
  ] as const)
    for (const n of nodes) expect(sideOf(converted, n.id)).toBe(side)
})

test('classDetails gives each member signature, status in words and note', () => {
  const details = classDetails(plan, 'class:Orchestrator')

  expect(details).toMatchObject({
    id: 'class:Orchestrator',
    title: 'Orchestrator',
    status: 'changed',
  })
  expect(details?.members.map((m) => [m.id, m.signature, m.status])).toEqual([
    ['class:Orchestrator.give_hint', 'give_hint() -> AsyncIterator[str]', 'new'],
    ['class:Orchestrator.hints_given', 'hints_given: int', 'new'],
    ['class:Orchestrator.parse_command', 'parse_command(text: str) -> Command | None', 'removed'],
    ['class:Orchestrator.on_event', 'on_event(event: ClientEvent) -> None', 'changed'],
  ])
  expect(details?.note).toBeTruthy()
  expect(details?.kind).toBe('class')
  expect(details?.members.find((m) => m.id === 'class:Orchestrator.on_event')?.note).toBe(
    'Handles RequestHint by asking the policy for the next level.',
  )
  expect(classDetails(plan, 'class:HintLevel')).toMatchObject({
    title: 'HintLevel: Enum',
    kind: 'enum',
  })
  expect(classDetails(plan, 'class:LLMClient')?.members[0].status).toBe('unchanged')
  expect(classDetails(plan, 'class:Gone')).toBeNull()
})

test('sideOf finds the side of a class or member id', () => {
  expect(sideOf(plan, 'class:HintButton')).toBe('front')
  expect(sideOf(plan, 'class:HintPolicy.max_hints')).toBe('back')
  expect(sideOf(plan, 'file:x')).toBeNull()
  const rel = plan.relations[0]
  expect(sideOf(plan, rel.id)).toBe(plan.classes.find((c) => c.id === rel.from)?.side)
  expect(sideOf(oldPlan, 'class:HintPolicy')).toBeNull()
})
