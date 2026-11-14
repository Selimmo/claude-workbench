import type { Plan } from '../plan'
import { criteriaOf, criterionId } from '../viewModels'
import { Prose } from '../Prose'

/** What the plan promises to deliver; the owner approves these along with the plan. */
export function CriteriaTab({ plan }: { plan: Plan }) {
  return (
    <ol className="rows">
      {criteriaOf(plan).map((criterion, index) => (
        <li key={criterionId(index)} data-element-id={criterionId(index)}>
          <Prose text={criterion} />
        </li>
      ))}
    </ol>
  )
}
