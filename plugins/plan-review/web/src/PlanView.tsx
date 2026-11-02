import { useMemo, useState } from 'react'

import { architectureDiagram, classDiagram } from './diagram'
import { CommentLayer } from './comments/CommentLayer'
import { DiagramView } from './DiagramView'
import type { Plan } from './plan'
import { FilesTab } from './tabs/FilesTab'
import { FlowsTab } from './tabs/FlowsTab'
import { RisksTab } from './tabs/RisksTab'
import { TestsTab } from './tabs/TestsTab'
import { ApprovalBar } from './ApprovalBar'
import { threadsFor } from './threadGroups'
import type { Live } from './useLive'
import { useMarkRevised } from './useMarkRevised'
import { type TabId, tabsFor } from './viewModels'

export function PlanView({ plan, live }: { plan: Plan; live: Live }) {
  const [active, setActive] = useState<TabId>('classes')
  const tabs = tabsFor(plan)
  const { threads, refreshThreads, revised, markSeen, approved, approvePlan } = live
  useMarkRevised(revised)
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
        <ApprovalBar
          approved={approved}
          unresolved={threadsFor(threads, plan, active).unresolved}
          onApprove={approvePlan}
        />
        {revised.size > 0 && (
          <div role="status" className="revised-banner">
            Plan revised: {revised.size} element{revised.size === 1 ? '' : 's'} changed
            <button onClick={markSeen}>Mark as seen</button>
          </div>
        )}
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
      <CommentLayer
        plan={plan}
        tab={active}
        threads={threads}
        refresh={refreshThreads}
        readOnly={approved}
      >
        <section role="tabpanel" id="panel" aria-labelledby={`tab-${active}`}>
          {active === 'classes' && (
            <DiagramView diagram={classes} empty="No classes in this plan." />
          )}
          {active === 'flows' && <FlowsTab plan={plan} />}
          {active === 'architecture' && (
            <DiagramView diagram={architecture} empty="No architecture in this plan." />
          )}
          {active === 'files' && <FilesTab plan={plan} />}
          {active === 'tests' && <TestsTab plan={plan} onShow={setActive} />}
          {active === 'risks' && <RisksTab plan={plan} />}
        </section>
      </CommentLayer>
    </>
  )
}
