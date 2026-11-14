import { useState } from 'react'

import type { GrillQuestion } from '../grill'
import { answerParts } from '../grillModel'
import { Thread } from './QuestionCard'
import { Prose } from '../Prose'

function Row({ question }: { question: GrillQuestion }) {
  const [expanded, setExpanded] = useState(false)
  const { answer, note } = answerParts(question)
  return (
    <li className="answered-row">
      <button aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        <span className="tick" aria-hidden="true">
          ✓
        </span>
        <span className="answered-title">
          <Prose text={question.title} />
        </span>
        <strong>
          <Prose text={answer} />
        </strong>
        {note && (
          <span className="answer-note">
            <Prose text={note} />
          </span>
        )}
      </button>
      {expanded && (
        <div className="collapsed-detail">
          <p>
            <Prose text={question.explanation} />
          </p>
          <ul>
            {question.choices.map((c) => (
              <li key={c.id}>
                <Prose text={c.label} />: <Prose text={c.description} />
              </li>
            ))}
          </ul>
          <Thread question={question} />
        </div>
      )}
    </li>
  )
}

/** Answered questions as tidy rows: a tick, the title, the answer in bold and the note in grey. */
export function CollapsedRound({ questions }: { questions: GrillQuestion[] }) {
  return (
    <ul className="answered-list">
      {questions.map((q) => (
        <Row key={q.id} question={q} />
      ))}
    </ul>
  )
}
