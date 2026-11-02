import type { Plan } from '../plan'
import { type TabId, tabOf } from '../viewModels'

interface Props {
  plan: Plan
  onShow: (tab: TabId) => void
}

export function TestsTab({ plan, onShow }: Props) {
  return (
    <ol className="rows">
      {plan.tests.map((test) => {
        const targetTab = tabOf(plan, test.target)
        return (
          <li key={test.id} data-element-id={test.id}>
            <code>{test.name}</code>
            <span className="reason">{test.behaviour}</span>
            <button
              className="link"
              disabled={targetTab === null}
              onClick={() => targetTab && onShow(targetTab)}
            >
              {test.target}
            </button>
          </li>
        )
      })}
    </ol>
  )
}
