import type { AnswerDraft, GrillQuestion } from '../grill'
import { asksLeft } from '../grillModel'

/** One open question: its explanation and choices, the first being the recommendation. */
export function QuestionCard({
  question,
  draft,
  maxAsks,
  onDraft,
}: {
  question: GrillQuestion
  draft?: AnswerDraft
  maxAsks: number
  /** Null removes the draft (the owner cleared what they wrote). */
  onDraft: (draft: AnswerDraft | null) => void
}) {
  const written = (kind: 'own' | 'ask') => (draft?.kind === kind ? (draft.text ?? '') : '')
  const write = (kind: 'own' | 'ask', text: string) =>
    onDraft(text.trim() === '' ? null : { kind, text })
  return (
    <fieldset className="question-card" aria-label={question.title}>
      <legend>
        {question.title}
        {question.updated && <span className="updated-tag">updated</span>}
      </legend>
      <p>{question.explanation}</p>
      {question.thread.length > 0 && (
        <ul className="ask-thread" aria-label="Asks back">
          {question.thread.map((m, i) => (
            <li key={i} data-author={m.author}>
              <strong>{m.author === 'owner' ? 'You' : 'Claude'}:</strong> {m.text}
            </li>
          ))}
        </ul>
      )}
      {question.choices.map((choice, i) => (
        <label key={choice.id} className="choice">
          <input
            type="radio"
            name={question.id}
            aria-label={choice.label}
            checked={draft?.kind === 'choice' && draft.choice_id === choice.id}
            onChange={() => onDraft({ kind: 'choice', choice_id: choice.id })}
          />
          <span className="choice-label">
            {choice.label}
            {i === 0 && <span className="recommended">Recommended</span>}
          </span>
          <span className="choice-description">{choice.description}</span>
        </label>
      ))}
      {draft?.kind === 'choice' && (
        <textarea
          aria-label="Note on your choice"
          value={draft.text ?? ''}
          onChange={(e) =>
            onDraft({
              kind: 'choice',
              choice_id: draft.choice_id,
              ...(e.target.value ? { text: e.target.value } : {}),
            })
          }
        />
      )}
      <textarea
        aria-label="Your own answer"
        value={written('own')}
        onChange={(e) => write('own', e.target.value)}
      />
      {asksLeft(question, maxAsks) <= 0 && (
        <p className="hint">{maxAsks} questions asked; pick a choice or write your own answer</p>
      )}
      <textarea
        aria-label="Ask back"
        disabled={asksLeft(question, maxAsks) <= 0}
        value={written('ask')}
        onChange={(e) => write('ask', e.target.value)}
      />
    </fieldset>
  )
}
