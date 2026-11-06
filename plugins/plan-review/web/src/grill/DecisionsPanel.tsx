import { useState } from 'react'

import type { Grill } from '../grill'
import { decisionsByTopic, replacedCount } from '../grillModel'
import { storeOpen, storedOpen } from './panelState'

/** What is settled so far, by topic, and what was left out of scope. Can be collapsed. */
export function DecisionsPanel({ grill }: { grill: Grill }) {
  const [open, setOpen] = useState(storedOpen)
  const [withReplaced, setWithReplaced] = useState(false)
  const replaced = replacedCount(grill)
  const toggle = () => {
    setOpen(!open)
    storeOpen(!open)
  }
  return (
    <aside className="decisions-panel" aria-label="Decisions">
      <h2>
        <button className="panel-toggle" aria-expanded={open} onClick={toggle}>
          Decisions
        </button>
      </h2>
      {open && (
        <>
          {decisionsByTopic(grill, withReplaced).map((group) => (
            <section key={group.topic}>
              <h3>{group.topic}</h3>
              <ul>
                {group.decisions.map((d) => (
                  <li key={d.id} data-replaced={d.replaced}>
                    <strong>{d.decision}</strong>
                    <span className="decision-choice">{d.choice}</span>
                    {d.why && <span className="decision-why">{d.why}</span>}
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {replaced > 0 && !withReplaced && (
            <button className="link" onClick={() => setWithReplaced(true)}>
              Show replaced ({replaced})
            </button>
          )}
          {grill.out_of_scope.length > 0 && (
            <section>
              <h3>Out of scope</h3>
              <ul>
                {grill.out_of_scope.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </aside>
  )
}
