import { useState } from 'react'

import type { GrillQuestion, GrillRound } from '../grill'
import { answerLine } from '../grillModel'

function Line({ question }: { question: GrillQuestion }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <li>
      <button className="link" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        {answerLine(question)}
      </button>
      {expanded && (
        <div className="collapsed-detail">
          <p>{question.explanation}</p>
          <ul>
            {question.choices.map((c) => (
              <li key={c.id}>
                {c.label}: {c.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  )
}

/** An answered round as one `title → answer` line per question; click a line to expand it. */
export function CollapsedRound({ round }: { round: GrillRound }) {
  return (
    <section className="collapsed-round" aria-label={`Round ${round.n}`}>
      <ul>
        {round.questions.map((q) => (
          <Line key={q.id} question={q} />
        ))}
      </ul>
    </section>
  )
}
