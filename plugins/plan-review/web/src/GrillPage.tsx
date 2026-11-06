import { useState } from 'react'

import { BrokenFilesBanner } from './BrokenFilesBanner'
import { ClaudeBanner } from './ClaudeBanner'
import { StickyHead } from './StickyHead'
import { CollapsedRound } from './grill/CollapsedRound'
import { ConfirmBar } from './grill/ConfirmBar'
import { DecisionsPanel } from './grill/DecisionsPanel'
import { QuestionCard } from './grill/QuestionCard'
import { canSubmit } from './grillModel'
import { useGrill } from './useGrill'

export function GrillPage() {
  const {
    grill,
    grillErrors,
    brokenFiles,
    drafts,
    planReady,
    status,
    lastEvent,
    resend,
    saveDraft,
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
      <StickyHead>
        <BrokenFilesBanner errors={brokenFiles} />
        <ClaudeBanner status={status} lastEvent={lastEvent} onResend={resend} />
      </StickyHead>
      <h1>
        {grill.label} {grill.title}
      </h1>
      <div className="grill-body">
        <DecisionsPanel grill={grill} />
        <div className="rounds">
          {grill.rounds.map((round) => (
            <section key={round.n} className="round" aria-labelledby={`round-${round.n}`}>
              <h2 id={`round-${round.n}`}>Round {round.n}</h2>
              {round.questions.some((q) => q.answer !== null) && (
                <CollapsedRound questions={round.questions.filter((q) => q.answer !== null)} />
              )}
              {round.questions
                .filter((q) => q.answer === null)
                .map((question) => (
                  <QuestionCard
                    key={question.id}
                    question={question}
                    draft={drafts[question.id]}
                    maxReplies={grill.max_replies}
                    onDraft={(draft) => run(() => saveDraft(question.id, draft))}
                  />
                ))}
            </section>
          ))}
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
        </div>
      </div>
    </main>
  )
}
