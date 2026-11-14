import type { Plan } from '../plan'
import { tabOf } from '../viewModels'
import { Prose } from '../Prose'

interface Props {
  plan: Plan
  /** Show the element a test targets: its tab, highlighted. */
  onShow: (target: string) => void
}

export function TestsTab({ plan, onShow }: Props) {
  return (
    <ol className="rows">
      {plan.tests.map((test) => {
        const targetTab = tabOf(plan, test.target)
        return (
          <li key={test.id} data-element-id={test.id}>
            <code>{test.name}</code>
            <span className="reason">
              <Prose text={test.behaviour} />
            </span>
            <button
              className="link"
              disabled={targetTab === null}
              onClick={() => targetTab && onShow(test.target)}
            >
              {test.target}
            </button>
          </li>
        )
      })}
    </ol>
  )
}
