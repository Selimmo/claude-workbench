import type { Plan, Risk } from '../plan'
import { risksByKind } from '../viewModels'

function RiskList({ title, items }: { title: string; items: Risk[] }) {
  return (
    <div className="group">
      <h2>{title}</h2>
      {items.length === 0 ? (
        <p className="empty">None.</p>
      ) : (
        <ul className="rows">
          {items.map((risk) => (
            <li key={risk.id} data-severity={risk.severity}>
              <span className="severity">{risk.severity}</span>
              <span>{risk.text}</span>
              {risk.mitigation && <span className="reason">Mitigation: {risk.mitigation}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function RisksTab({ plan }: { plan: Plan }) {
  const { risks, questions } = risksByKind(plan)
  return (
    <>
      <RiskList title="Risks" items={risks} />
      <RiskList title="Open questions" items={questions} />
    </>
  )
}
