import type { Plan } from '../plan'
import { criteriaOf, criterionId } from '../viewModels'

/** What the plan promises to deliver; the owner approves these along with the plan. */
export function CriteriaTab({ plan }: { plan: Plan }) {
  return (
    <ol className="rows">
      {criteriaOf(plan).map((criterion, index) => (
        <li key={criterionId(index)} data-element-id={criterionId(index)}>
          {criterion}
        </li>
      ))}
    </ol>
  )
}
