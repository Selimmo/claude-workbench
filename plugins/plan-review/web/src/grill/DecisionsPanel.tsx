import type { Grill } from '../grill'

/** What is settled so far, beside the rounds, and what was left out of scope. */
export function DecisionsPanel({ grill }: { grill: Grill }) {
  const replaced = new Set(grill.decisions.flatMap((d) => (d.replaces ? [d.replaces] : [])))
  const titles = new Map(grill.rounds.flatMap((r) => r.questions.map((q) => [q.id, q.title])))
  return (
    <aside className="decisions-panel" aria-label="Decisions">
      <h2>Decisions</h2>
      <ul>
        {grill.decisions.map((d) => (
          <li key={d.id} data-replaced={replaced.has(d.id)}>
            <span className="topic">{d.topic}</span> <strong>{d.decision}</strong>: {d.choice}
            {d.question_id && titles.get(d.question_id) && (
              <span className="from"> (from {titles.get(d.question_id)})</span>
            )}
          </li>
        ))}
      </ul>
      {grill.out_of_scope.length > 0 && (
        <>
          <h3>Out of scope</h3>
          <ul>
            {grill.out_of_scope.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
    </aside>
  )
}
