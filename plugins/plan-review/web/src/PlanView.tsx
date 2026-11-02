import { useMemo, useState } from 'react'

import { architectureDiagram, classDiagram } from './diagram'
import { DiagramView } from './DiagramView'
import type { Plan } from './plan'
import { FilesTab } from './tabs/FilesTab'
import { RisksTab } from './tabs/RisksTab'
import { TestsTab } from './tabs/TestsTab'
import { type TabId, tabsFor } from './viewModels'

export function PlanView({ plan }: { plan: Plan }) {
  const [active, setActive] = useState<TabId>('classes')
  const tabs = tabsFor(plan)
  // Memoised so a diagram is laid out once per plan, not on every render.
  const classes = useMemo(() => classDiagram(plan), [plan])
  const architecture = useMemo(() => architectureDiagram(plan), [plan])

  return (
    <>
      <header>
        <h1>
          #{plan.issue.number} {plan.issue.title}
        </h1>
        <p>{plan.summary}</p>
      </header>
      <nav role="tablist" aria-label="Plan sections">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={tab.id === active}
            aria-controls="panel"
            onClick={() => setActive(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <section role="tabpanel" id="panel" aria-labelledby={`tab-${active}`}>
        {active === 'classes' && <DiagramView diagram={classes} empty="No classes in this plan." />}
        {active === 'flows' && <p className="empty">Flow diagrams are not built yet.</p>}
        {active === 'architecture' && (
          <DiagramView diagram={architecture} empty="No architecture in this plan." />
        )}
        {active === 'files' && <FilesTab plan={plan} />}
        {active === 'tests' && <TestsTab plan={plan} onShow={setActive} />}
        {active === 'risks' && <RisksTab plan={plan} />}
      </section>
    </>
  )
}
