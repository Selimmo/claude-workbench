import { useEffect, useState } from 'react'

import { fetchGrill, fetchPlan } from './api'
import { connectUpdates } from './updatesSocket'

/** 'Grill · Plan' links in the top bar, once the run has both pages. */
export function PageSwitch({ current }: { current: 'grill' | 'plan' }) {
  const [both, setBoth] = useState(false)
  useEffect(() => {
    // Syncing with an external system (the server) is what effects are for.
    const check = () =>
      void Promise.all([fetchGrill(), fetchPlan()]).then(([grill, plan]) =>
        setBoth(grill !== null && plan.ok),
      )
    check()
    return connectUpdates(
      `ws://${location.host}/api/updates`,
      ({ type }) => {
        if (type === 'plan_changed' || type === 'grill_changed') check()
      },
      check,
    )
  }, [])
  if (!both) return null
  return (
    <nav className="page-switch" aria-label="Pages">
      <a href="/grill" aria-current={current === 'grill' ? 'page' : undefined}>
        Grill
      </a>
      {' · '}
      <a href="/" aria-current={current === 'plan' ? 'page' : undefined}>
        Plan
      </a>
    </nav>
  )
}
