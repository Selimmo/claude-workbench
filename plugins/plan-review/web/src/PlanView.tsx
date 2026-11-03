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
import { HEADER_ANCHORS, threadsFor } from './threadGroups'
import type { Live } from './useLive'
import { useMarkElements, useMarkRevised } from './useMarkRevised'
import { type TabId, tabOf, tabsFor } from './viewModels'

/** Rows in a list scroll into view; diagram elements are already in the fitted view. */
const scrollToRow = (element: HTMLElement) =>
  element.closest('.viewport') ? undefined : element.scrollIntoView?.({ block: 'center' })

/** Diagram tabs fill the space below the tabs; the others scroll like a document. */
const DIAGRAM_TABS: TabId[] = ['classes', 'flows', 'architecture']

export function PlanView({ plan, live }: { plan: Plan; live: Live }) {
  const [active, setActive] = useState<TabId>('classes')
  const [fullSummary, setFullSummary] = useState(false)
  const tabs = tabsFor(plan)
  const { threads, drafts, status, refreshReview, revised, markSeen, approved, approvePlan } = live
  useMarkRevised(revised)
  // The element a test's target link points at: shown and outlined until the tab changes.
  const [focus, setFocus] = useState<string | null>(null)
  const focused = useMemo(() => new Set(focus ? [focus] : []), [focus])
  useMarkElements('focused', focused, scrollToRow)
  function show(target: string) {
    const tab = tabOf(plan, target)
    if (tab === null) return
    setActive(tab)
    setFocus(target)
  }
  // Memoised so a diagram is laid out once per plan, not on every render.
  const classes = useMemo(() => classDiagram(plan), [plan])
  const architecture = useMemo(() => architectureDiagram(plan), [plan])

  const header = (
    <header>
      <div className="header-row">
        <h1 data-element-id={HEADER_ANCHORS.title}>
          #{plan.issue.number} {plan.issue.title}
        </h1>
        <ApprovalBar
          approved={approved}
          unresolved={threadsFor(threads, plan, active).unresolved}
          drafts={drafts.length}
          onApprove={approvePlan}
        />
      </div>
      <div className="summary">
        {/* Clamped to two lines by default so the diagrams keep the height. */}
        <p data-element-id={HEADER_ANCHORS.summary} data-clamped={!fullSummary}>
          {plan.summary}
        </p>
        <button className="link" onClick={() => setFullSummary((full) => !full)}>
          {fullSummary ? 'Less' : 'More'}
        </button>
      </div>
      {status && (
        <p role="status" aria-label="Claude" className="claude-status" data-done={status.done}>
          <span className="claude-status-mark" aria-hidden="true" />
          Claude: <span>{status.text}</span>
        </p>
      )}
      {revised.size > 0 && (
        <div role="status" className="revised-banner">
          Plan revised: {revised.size} element{revised.size === 1 ? '' : 's'} changed
          <button onClick={markSeen}>Mark as seen</button>
        </div>
      )}
    </header>
  )
  const tabList = (
    <nav role="tablist" aria-label="Plan sections">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          id={`tab-${tab.id}`}
          aria-selected={tab.id === active}
          aria-controls="panel"
          onClick={() => {
            setActive(tab.id)
            setFocus(null)
          }}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )

  return (
    <CommentLayer
      plan={plan}
      tab={active}
      threads={threads}
      drafts={drafts}
      refresh={refreshReview}
      readOnly={approved}
      header={header}
      tabs={tabList}
    >
      <section
        role="tabpanel"
        id="panel"
        aria-labelledby={`tab-${active}`}
        data-fill={DIAGRAM_TABS.includes(active)}
      >
        {active === 'classes' && <DiagramView diagram={classes} empty="No classes in this plan." />}
        {active === 'flows' && <FlowsTab plan={plan} focus={focus} />}
        {active === 'architecture' && (
          <DiagramView diagram={architecture} empty="No architecture in this plan." />
        )}
        {active === 'files' && <FilesTab plan={plan} />}
        {active === 'tests' && <TestsTab plan={plan} onShow={show} />}
        {active === 'risks' && <RisksTab plan={plan} />}
      </section>
    </CommentLayer>
  )
}
