import type { AnswerDraft } from './grill'

/** What `mark` notes when a reload starts. */
export interface DraftMark {
  edits: number
  /** Questions that still had a save on its way when the reload started. */
  busy: ReadonlySet<string>
}

/** Keeps what the owner types on the grill page: one save at a time per question, and a merge for reloads. */
export class DraftSync {
  private edits = 0
  private editedAt = new Map<string, number>()
  private saving = new Map<string, Promise<void>>()
  private waiting = new Map<string, AnswerDraft>()

  private send: (questionId: string, draft: AnswerDraft) => Promise<void>

  constructor(send: (questionId: string, draft: AnswerDraft) => Promise<void>) {
    this.send = send
  }

  /** Saves one answer. While a save for the question is on its way, the newest text waits to go next. */
  save(questionId: string, draft: AnswerDraft): Promise<void> {
    this.edits++
    this.editedAt.set(questionId, this.edits)
    const running = this.saving.get(questionId)
    if (running) {
      this.waiting.set(questionId, draft)
      return running
    }
    const loop = this.run(questionId, draft)
    this.saving.set(questionId, loop)
    return loop
  }

  private async run(questionId: string, first: AnswerDraft): Promise<void> {
    try {
      let next: AnswerDraft | undefined = first
      while (next) {
        await this.send(questionId, next)
        next = this.waiting.get(questionId)
        this.waiting.delete(questionId)
      }
    } catch (error) {
      this.waiting.delete(questionId)
      throw error
    } finally {
      this.saving.delete(questionId)
    }
  }

  /** Resolves once no answer is saving or waiting, whether the saves worked or not. */
  async settled(): Promise<void> {
    while (this.saving.size) await Promise.allSettled([...this.saving.values()])
  }

  /** Notes the moment a reload starts, to pass to `merge` when the server's answers arrive. */
  mark(): DraftMark {
    return { edits: this.edits, busy: new Set(this.saving.keys()) }
  }

  /** A question typed in since the mark, or still saving at it, keeps the page's text. Others take the server's. */
  merge(
    server: Record<string, AnswerDraft>,
    page: Record<string, AnswerDraft>,
    mark: DraftMark,
  ): Record<string, AnswerDraft> {
    const merged = { ...server }
    for (const [id, at] of this.editedAt) {
      if (at <= mark.edits && !mark.busy.has(id)) continue
      const mine = page[id]
      if (mine) merged[id] = mine
      else delete merged[id]
    }
    return merged
  }
}
