import { Fragment, useState } from 'react'

import { ClaudeBanner } from './ClaudeBanner'
import { CollapsedRound } from './grill/CollapsedRound'
import { ConfirmBar } from './grill/ConfirmBar'
import { DecisionsPanel } from './grill/DecisionsPanel'
import { QuestionCard } from './grill/QuestionCard'
import { canSubmit, roundIsOpen } from './grillModel'
import { useGrill } from './useGrill'

export function GrillPage() {
  const {
    grill,
    grillErrors,
    drafts,
    planReady,
    status,
    lastEvent,
    resend,
    saveDraft,
    discardDraft,
    submit,
    confirm,
    reopen,
  } = useGrill()
  const [error, setError] = useState<string | null>(null)
  const run = (action: () => Promise<void>) => {
    setError(null)
    action().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }
  if (grillErrors !== null)
    return (
      <div role="alert" className="status error">
        <h1>The grill can't be shown</h1>
        <ul>
          {grillErrors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      </div>
    )
  if (grill === null) return <p className="status">Loading the grill…</p>
  return (
    <main className="grill-page">
      <ClaudeBanner status={status} lastEvent={lastEvent} onResend={resend} />
      <h1>
        {grill.label} {grill.title}
      </h1>
      <DecisionsPanel grill={grill} />
      {grill.rounds.map((round) =>
        roundIsOpen(round) ? (
          <Fragment key={round.n}>
            {round.questions.some((q) => q.answer !== null) && (
              <CollapsedRound
                round={{ ...round, questions: round.questions.filter((q) => q.answer !== null) }}
              />
            )}
            {round.questions
              .filter((q) => q.answer === null)
              .map((question) => (
                <QuestionCard
                  key={question.id}
                  question={question}
                  draft={drafts[question.id]}
                  maxAsks={grill.max_asks}
                  onDraft={(draft) =>
                    run(() => (draft ? saveDraft(question.id, draft) : discardDraft(question.id)))
                  }
                />
              ))}
          </Fragment>
        ) : (
          <CollapsedRound key={round.n} round={round} />
        ),
      )}
      {planReady && <a href="/">Plan ready → open the plan</a>}
      <ConfirmBar grill={grill} onConfirm={confirm} onReopen={reopen} />
      {!grill.done && (
        <button
          className="primary"
          disabled={!canSubmit(grill, drafts)}
          onClick={() => run(submit)}
        >
          Submit answers
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </main>
  )
}
