---
name: ship
description: Take one issue from plan to reviewed commit. The architect plans it, the owner reviews and approves the plan in the plan-review viewer, then the implementer builds it with TDD while a test reviewer and a code reviewer check the result.
argument-hint: <issue number or URL> [--grill]
disable-model-invocation: true
---

# /ship: issue → settled decisions → approved plan → TDD → reviewed commit

You are the **orchestrator**. You run the steps below for issue `$ARGUMENTS`, delegate the real work to the plugin's agents, and talk to the owner. You never write the plan or the code yourself, and you decide pass or fail with `plan-review` helpers, never by your own reading.

**Which agents.** For each role (`architect`, `implementer`, `test-reviewer`, `code-reviewer`), use the project's own agent when `.claude/agents/<name>.md` exists in the project, otherwise `plan-review:<name>` from this plugin. Check once at the start and say which ones you are using. Below, `plan-review:<name>` means "the agent chosen for that role".

Throughout, `N` is the issue number (take it from `$ARGUMENTS`, which may be `42`, `#42` or an issue URL, optionally followed by `--grill`) and `W` is `.claude/work/N/`. Hand-offs between steps are files in `W`. Pass agents paths, not file contents, and keep your own context small.

## 0. Preconditions

1. Run `plan-review config`. If it fails, show the errors and stop.
2. Run `git status --porcelain`. If there are uncommitted changes, stop and ask the owner: the reviewers' read-only check needs a clean starting point.
3. Run `plan-review init N`. It creates `W`, and on first use `.claude/work/.gitignore`, so nothing in `.claude/work/` is ever committed and the project needs no gitignore entry.

## 1. Settle the decisions (only with `--grill`)

If `W/decisions.md` already exists, the architect will use it, whatever produced it (a grilling session, the owner's notes, a doc). Mention it.

Run this step only when the arguments include `--grill`. Then run the `grilling` skill on issue N with the Skill tool. It is Matt Pocock's interview skill: facts are looked up, and every open decision is put to the owner in rounds until none is left. Follow it fully, including waiting for the owner to confirm that you have reached a shared understanding.

If `--grill` was given but no `grilling` skill is available, tell the owner in one line that it comes from https://github.com/mattpocock/skills (`grill-me` and `grilling`), then continue without it.

Once the owner confirms, write `W/decisions.md`. Write only what was settled, in the owner's terms, so the architect can follow it without the conversation:

```
# Decisions for #N: <issue title>

## <topic>
- **<decision>**: <the choice>. <one line of why, if one was given>

## Out of scope
- <anything explicitly deferred>
```

## 2. Plan

Start the `plan-review:architect` agent with: "Plan mode. Issue N." When it finishes, go straight to step 3. Don't summarize the plan: the owner reads all of it in the viewer.

## 3. Review in the viewer

1. Start `plan-review serve N` with the Bash tool in the background (`run_in_background`). Read its first output line, `plan-review: issue #N at http://127.0.0.1:<port>/`, from the task's output file, and give the owner that URL. The browser opens by itself unless `viewer.open` is `none`.
2. Subscribe to the owner's actions with the **Monitor** tool's WebSocket source: `ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description `plan-review #N`. A Monitor lasts at most 30 minutes: when it expires before `approved`, arm it again. Events sent while no Monitor is listening are not kept, so each time you arm it again, run `plan-review threads N` and treat every thread whose last message is the owner's (no reply from you yet) as part of a review: handle it as below.
3. Each notification is one JSON event:
   - `review_submitted` with `comments`: the owner submitted a review. Their comments and replies were drafts until now, so this one event holds all of them. Each item has `type` (`comment` for a new thread, `reply` for a reply in an existing one), `thread_id`, `anchor` and `text`: the owner wrote on the element `anchor` (`header:title`/`header:summary` is the plan's header, `tab:<tab>` a whole tab). The viewer shows the owner a status line of what you are doing; set it with `plan-review status N "<text>"` (the latest text replaces the last) at each stage:
     1. At once: `plan-review status N "Review received (<count> comments)"`.
     2. Before answering: `plan-review status N "Answering questions"`.
     3. Before starting the architect: `plan-review status N "Architect revising (<thread ids>)"`.
     4. When the whole review is handled: `plan-review status N "<what changed>" --done`, for example "Replies posted to 2 threads; plan updated: HintPolicy split".

     Handle every item of the review:
     - **A question.** Answer it with `plan-review reply N <thread_id> "<answer>"`. Read the plan and the code first if you need to. Keep answers short and concrete.
     - **A requested change.** Never edit `plan.json` yourself. Take all the change requests of the review together, then start `plan-review:architect` once with: "Revise mode. Issue N. Threads: <thread ids>." For each thread, post the architect's line about it with `plan-review reply`. The viewer refreshes by itself and outlines what changed.
     - Never resolve threads. Resolving is the owner's way of saying they are satisfied.
   - `approved`: go to step 4. Stop the Monitor and the server task.

## 4. Branch

Run `git switch -c "$(plan-review branch N)"`.

## 5. Implement, then review the tests

Let `max` be `max_review_rounds` from `plan-review config`. For round `r = 1 … max`:

1. Start `plan-review:implementer` with: "Issue N, round r." From round 2 on, add: "Fix the findings in W/test-review.md."
2. `before=$(plan-review tree-hash)`.
3. Start `plan-review:test-reviewer` with: "Issue N, round r. Review the tests."
4. `after=$(plan-review tree-hash)`. If `before` ≠ `after`, the reviewer changed files: discard its review, tell the owner, and stop.
5. Write the reviewer's final message, unchanged, to `W/test-review.md`.
6. `plan-review verdict W/test-review.md`. Exit 0 (PASS) means go to step 6. Exit 1 (FINDINGS) means start the next round. Exit 2 (malformed) means ask the reviewer once to restate its verdict, then treat a second malformed review as FINDINGS.

If round `max` still has FINDINGS, stop. Show the owner the findings and ask whether to continue, change the plan, or take over.

## 6. Review the code

Same loop with `plan-review:code-reviewer` and `W/code-review.md`. The implementer's prompt from round 2 on says "Fix the findings in W/code-review.md". Use the same `tree-hash` check and the same `max_review_rounds` cap.

## 7. Hand back to the owner

Show, briefly:
- `git diff --stat` against the branch point
- the last verdict line of each review and how many rounds it took
- any "Deviations from the plan" in `W/impl-report.md`

Ask for the owner's OK. Only after an explicit OK:
1. Commit everything except `W` (it is gitignored), with a message that explains the change and ends with `Closes #N`.
2. Post the approved plan on the issue: `gh issue comment N --body-file -`, with a short summary and `W/plan.json` inside a `<details><summary>Approved plan</summary>` block in a fenced `json` code block.

Don't push, open a PR, or merge unless the owner asks.

## If something goes wrong

- An agent fails or returns nothing useful: retry it once with the same prompt, then stop and tell the owner.
- The viewer server dies: start it again (step 3.1). The plan, the threads and the approval are on disk.
- The owner asks you to stop: stop the Monitor and the server, and leave the branch and files as they are.
