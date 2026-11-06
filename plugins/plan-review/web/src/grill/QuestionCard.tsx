import type { AnswerDraft, GrillQuestion } from '../grill'
import { otherIsFinal, pick, type Pick } from '../grillModel'

const CHOICE_HINT = 'Add a few words to your choice (optional)'
const OTHER_HINT = 'Type your own option, a question, or a comment'
const FINAL_HINT = 'Claude has replied enough: this text now counts as your answer'

/** The owner's messages and Claude's replies on a question, if there are any. */
export function Thread({ question }: { question: GrillQuestion }) {
  if (question.thread.length === 0) return null
  return (
    <ul className="ask-thread" aria-label="Conversation">
      {question.thread.map((m, i) => (
        <li key={i} data-author={m.author}>
          <strong>{m.author === 'owner' ? 'You' : 'Claude'}:</strong> {m.text}
        </li>
      ))}
    </ul>
  )
}

/** One open question: its choices and Other as radio buttons, with one text box under the pick. */
export function QuestionCard({
  question,
  draft,
  maxReplies,
  onDraft,
}: {
  question: GrillQuestion
  draft?: AnswerDraft
  maxReplies: number
  onDraft: (draft: AnswerDraft) => void
}) {
  const options = [
    ...question.choices.map((c, i) => ({
      key: `choice:${c.id}`,
      target: { kind: 'choice', choice_id: c.id } as Pick,
      label: c.label,
      description: c.description,
      recommended: i === 0,
      checked: draft?.kind === 'choice' && draft.choice_id === c.id,
    })),
    {
      key: 'other',
      target: { kind: 'other' } as Pick,
      label: 'Other',
      description: '',
      recommended: false,
      checked: draft !== undefined && draft.kind !== 'choice',
    },
  ]
  const write = (text: string) => {
    const kept = text === '' ? {} : { text }
    onDraft(
      draft?.kind === 'choice'
        ? { kind: 'choice', choice_id: draft.choice_id, ...kept }
        : { kind: 'other', ...kept },
    )
  }
  return (
    <fieldset className="question-card" aria-label={question.title}>
      <legend>
        {question.title}
        {question.updated && <span className="updated-tag">updated</span>}
      </legend>
      <p>{question.explanation}</p>
      <Thread question={question} />
      {options.map((option) => (
        <div key={option.key} className="option">
          <label className="choice">
            <input
              type="radio"
              name={question.id}
              aria-label={option.label}
              checked={option.checked}
              onChange={() => onDraft(pick(draft, option.target))}
            />
            <span className="choice-label">
              {option.label}
              {option.recommended && <span className="recommended">Recommended</span>}
            </span>
            {option.description && <span className="choice-description">{option.description}</span>}
          </label>
          {option.checked && (
            <textarea
              aria-label={
                option.target.kind === 'other' ? 'Your own option' : 'Note on your choice'
              }
              placeholder={
                option.target.kind !== 'other'
                  ? CHOICE_HINT
                  : otherIsFinal(question, maxReplies)
                    ? FINAL_HINT
                    : OTHER_HINT
              }
              required={option.target.kind === 'other'}
              value={draft?.text ?? ''}
              onChange={(e) => write(e.target.value)}
            />
          )}
        </div>
      ))}
    </fieldset>
  )
}
