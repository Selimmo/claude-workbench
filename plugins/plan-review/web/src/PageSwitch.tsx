import { useEffect, useState } from 'react'

import { fetchGrill, fetchPlan } from './api'

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
    const socket = new WebSocket(`ws://${location.host}/api/updates`)
    socket.onmessage = (event: MessageEvent<string>) => {
      const { type } = JSON.parse(event.data) as { type: string }
      if (type === 'plan_changed' || type === 'grill_changed') check()
    }
    return () => socket.close()
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
