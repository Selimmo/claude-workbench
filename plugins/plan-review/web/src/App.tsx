import { useEffect, useState } from 'react'

import { fetchPlan, type PlanResult } from './api'
import { PlanView } from './PlanView'
import { ThemeSwitch } from './ThemeSwitch'

export function App() {
  return (
    <>
      <div className="top-bar">
        <ThemeSwitch />
      </div>
      <Content />
    </>
  )
}

function Content() {
  const [result, setResult] = useState<PlanResult | null>(null)

  useEffect(() => {
    void fetchPlan().then(setResult)
  }, [])

  if (result === null) return <p className="status">Loading plan…</p>
  if (!result.ok)
    return (
      <div role="alert" className="status error">
        <h1>The plan can't be shown</h1>
        <ul>
          {result.errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      </div>
    )
  return <PlanView plan={result.plan} />
}
