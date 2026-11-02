---
name: ship
description: Take one issue from plan to reviewed commit. The architect plans it, the owner reviews and approves the plan in the plan-review viewer, then the implementer builds it with TDD while a test reviewer and a code reviewer check the result.
argument-hint: <issue number or URL>
disable-model-invocation: true
---

# /ship: issue → approved plan → TDD → reviewed commit

You are the **orchestrator**. You run the steps below for issue `$ARGUMENTS`, delegate the real work to the plugin's agents, and talk to the owner. You never write the plan or the code yourself, and you decide pass or fail with `plan-review` helpers, never by your own reading.

**Which agents.** For each role (`architect`, `implementer`, `test-reviewer`, `code-reviewer`), use the project's own agent when `.claude/agents/<name>.md` exists in the project, otherwise `plan-review:<name>` from this plugin. Check once at the start and say which ones you are using. Below, `plan-review:<name>` means "the agent chosen for that role".

Throughout, `N` is the issue number (take it from `$ARGUMENTS`, which may be `42`, `#42` or an issue URL) and `W` is `.claude/work/N/`. Hand-offs between steps are files in `W`. Pass agents paths, not file contents, and keep your own context small.

## 0. Preconditions

1. Run `plan-review config`. If it fails, show the errors and stop.
2. Run `git status --porcelain`. If there are uncommitted changes, stop and ask the owner: the reviewers' read-only check needs a clean starting point.
3. If `W/decisions.md` exists (written by a grilling session), the architect will use it. Mention that it does.

## 1. Plan

Start the `plan-review:architect` agent with: "Plan mode. Issue N." When it finishes, relay its summary lines to the owner in two or three sentences.

## 2. Review in the viewer

1. Start `plan-review serve N` with the Bash tool in the background (`run_in_background`). Read its first output line, `plan-review: issue #N at http://127.0.0.1:<port>/`, from the task's output file, and give the owner that URL. The browser opens by itself unless `viewer.open` is `none`.
2. Subscribe to the owner's actions with the **Monitor** tool's WebSocket source: `ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description `plan-review #N`. A Monitor lasts at most 30 minutes: when it expires before `approved`, arm it again.
3. Each notification is one JSON event:
   - `comment` or `reply` with `thread_id`, `anchor` and `text`: the owner wrote on the element `anchor`.
     - **A question.** Answer it with `plan-review reply N <thread_id> "<answer>"`. Read the plan and the code first if you need to. Keep answers short and concrete.
     - **A requested change.** Never edit `plan.json` yourself. Collect the change requests that arrive close together, then start `plan-review:architect` with: "Revise mode. Issue N. Threads: <thread ids>." For each thread, post the architect's line about it with `plan-review reply`. The viewer refreshes by itself and outlines what changed.
     - Never resolve threads. Resolving is the owner's way of saying they are satisfied.
   - `approved`: go to step 3. Stop the Monitor and the server task.

## 3. Branch

Run `git switch -c "$(plan-review branch N)"`.

## 4. Implement, then review the tests

Let `max` be `max_review_rounds` from `plan-review config`. For round `r = 1 … max`:

1. Start `plan-review:implementer` with: "Issue N, round r." From round 2 on, add: "Fix the findings in W/test-review.md."
2. `before=$(plan-review tree-hash)`.
3. Start `plan-review:test-reviewer` with: "Issue N, round r. Review the tests."
4. `after=$(plan-review tree-hash)`. If `before` ≠ `after`, the reviewer changed files: discard its review, tell the owner, and stop.
5. Write the reviewer's final message, unchanged, to `W/test-review.md`.
6. `plan-review verdict W/test-review.md`. Exit 0 (PASS) means go to step 5. Exit 1 (FINDINGS) means start the next round. Exit 2 (malformed) means ask the reviewer once to restate its verdict, then treat a second malformed review as FINDINGS.

If round `max` still has FINDINGS, stop. Show the owner the findings and ask whether to continue, change the plan, or take over.

## 5. Review the code

Same loop with `plan-review:code-reviewer` and `W/code-review.md`. The implementer's prompt from round 2 on says "Fix the findings in W/code-review.md". Use the same `tree-hash` check and the same `max_review_rounds` cap.

## 6. Hand back to the owner

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
- The viewer server dies: start it again (step 2.1). The plan, the threads and the approval are on disk.
- The owner asks you to stop: stop the Monitor and the server, and leave the branch and files as they are.
