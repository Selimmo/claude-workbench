---
name: ship
description: Take one issue (from GitHub, Jira, Linear or another tracker) or one plain prompt from plan to reviewed commit. The architect plans it, the owner reviews and approves the plan in the plan-review viewer, then the implementer builds it with TDD while a test reviewer and a code reviewer check the result.
argument-hint: <issue number, issue link or prompt> [--grill]
disable-model-invocation: true
---

# /ship: issue or prompt → settled decisions → approved plan → TDD → reviewed commit

You are the **orchestrator**. You run the steps below for the input `$ARGUMENTS`, delegate the real work to the plugin's agents, and talk to the owner. You never write the plan or the code yourself, and you decide pass or fail with `plan-review` helpers, never by your own reading.

**Which agents.** For each role (`architect`, `implementer`, `test-reviewer`, `code-reviewer`), use the project's own agent when `.claude/agents/<name>.md` exists in the project, otherwise `plan-review:<name>` from this plugin. Check once at the start and say which ones you are using. Below, `plan-review:<name>` means "the agent chosen for that role".

Throughout, `ID` is the run id and `W` is `.claude/work/ID/`. Step 0 settles `ID` from `$ARGUMENTS` (optionally followed by `--grill`): the issue number or key (`42`, `PROJ-123`), or a dated name for a prompt (`add-dark-mode-2026-11-05`). The label of a run is `#42` when `ID` is all digits, otherwise `ID` itself; use it when you talk to the owner. Hand-offs between steps are files in `W`. Pass agents paths, not file contents, and keep your own context small. Only you read the issue from its tracker, once, in step 0. The agents read `W/issue.md`.

## 0. Preconditions

1. Run `plan-review config`. If it fails, show the errors and stop.
2. Run `git status --porcelain`. If there are uncommitted changes, stop and ask the owner: the reviewers' read-only check needs a clean starting point.
3. Read the input (without `--grill`) and decide what it is, in this order:
   - A GitHub issue: `42` or `#42` (read it with `gh issue view 42 --comments`), or a `https://github.com/<owner>/<repo>/issues/<n>` link (`gh issue view <link> --comments`). `ID` is the number.
   - Another tracker's link: pick the tracker by host (`*.atlassian.net` is Jira, `linear.app` is Linear) and read the issue with that tracker's connector (an MCP tool). `ID` is the tracker's key, such as `PROJ-123` or `ENG-42`.
   - A bare key such as `PROJ-123`: use the one issue-tracker connector that is available. If none fits, or several do, ask the owner which tracker it is, or whether it is a prompt.
   - Anything else is a prompt.

   For an issue, read its title, link, body and comments once. If it cannot be read (no connector for the tracker, `gh` not logged in), stop with one line: "<tracker> needs a connector; paste the text as a prompt". Then run `plan-review init ID`; an existing `W` means you are resuming that run. It creates `W`, and on first use `.claude/work/.gitignore`, so nothing in `.claude/work/` is ever committed and the project needs no gitignore entry. Overwrite `W/issue.md` with:

   ```
   # <title>
   <link>

   <body>

   ## Comments
   <each comment, with its author>
   ```

   For a prompt, pick a name of two to four lowercase words joined by dashes, tell the owner which one you picked, and run `plan-review init --prompt <name>`. It prints the new folder, `.claude/work/<name>-<date>`, with `-2`, `-3`, ... when that name was already used today. `ID` is that folder's name. Write `W/issue.md` as the prompt exactly as given, nothing added.

## 1. Settle the decisions (only with `--grill`)

If `W/decisions.md` already exists, the architect will use it, whatever produced it (a grilling session, the owner's notes, a doc). Mention it.

Run this step only when the arguments include `--grill`. Then run the `grilling` skill on the run described in `W/issue.md` with the Skill tool. It is Matt Pocock's interview skill: facts are looked up, and every open decision is put to the owner in rounds until none is left. Follow it fully, including waiting for the owner to confirm that you have reached a shared understanding.

If `--grill` was given but no `grilling` skill is available, tell the owner in one line that it comes from https://github.com/mattpocock/skills (`grill-me` and `grilling`), then continue without it.

Once the owner confirms, write `W/decisions.md`. Write only what was settled, in the owner's terms, so the architect can follow it without the conversation:

```
# Decisions for <label>: <title>

## <topic>
- **<decision>**: <the choice>. <one line of why, if one was given>

## Out of scope
- <anything explicitly deferred>
```

## 2. Plan

Start the `plan-review:architect` agent with: "Plan mode. Run ID. The issue is in W/issue.md." When it finishes, go straight to step 3. Don't summarize the plan: the owner reads all of it in the viewer.

## 3. Review in the viewer

1. Start `plan-review serve ID` with the Bash tool in the background (`run_in_background`). Read its first output line, `plan-review: <label> at http://127.0.0.1:<port>/`, from the task's output file, and give the owner that URL. The browser opens by itself unless `viewer.open` is `none`.
2. Subscribe to the owner's actions with the **Monitor** tool's WebSocket source: `ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description `plan-review <label>`. A Monitor lasts at most 30 minutes: when it expires before `approved`, arm it again. Events sent while no Monitor is listening are not replayed (the viewer keeps the last one only so the owner can press Resend), so each time you arm it again, catch up: run `plan-review threads ID` and treat every thread whose last message is the owner's (no reply from you yet) as part of a review, and handle it as below; if `W/approved.json` exists, the plan was approved: handle it as `approved` below.
3. Each notification is one JSON event:
   - `review_submitted` with `comments`: the owner submitted a review. If every thread in it is already handled or being handled by you (a Resend repeats the same event), ignore it. Their comments and replies were drafts until now, so this one event holds all of them. Each item has `type` (`comment` for a new thread, `reply` for a reply in an existing one), `thread_id`, `anchor` and `text`: the owner wrote on the element `anchor` (`header:title`/`header:summary` is the plan's header, `tab:<tab>` a whole tab). The viewer shows the owner a banner of what you are doing; set it with `plan-review status ID "<text>"` (the latest text replaces the last) at each stage:
     1. At once: `plan-review status ID "Review received (<count> comments)"`.
     2. Before answering: `plan-review status ID "Answering questions"`.
     3. Before starting the architect: `plan-review status ID "Architect revising (<thread ids>)"`.
     4. When the whole review is handled: `plan-review status ID "<what changed>" --done`, for example "Replies posted to 2 threads; plan updated: HintPolicy split".

     Handle every item of the review:
     - **A question.** Answer it with `plan-review reply ID <thread_id> "<answer>"`. Read the plan and the code first if you need to. Keep answers short and concrete.
     - **A requested change.** Never edit `plan.json` yourself. Take all the change requests of the review together, then start `plan-review:architect` once with: "Revise mode. Run ID. Threads: <thread ids>." For each thread, post the architect's line about it with `plan-review reply`. The viewer refreshes by itself and outlines what changed.
     - Never resolve threads. Resolving is the owner's way of saying they are satisfied.
   - `approved`: first run `plan-review status ID "Approved, implementing"`, so the viewer knows you got it. Then go to step 4: stop the Monitor and the server task.

## 4. Branch

Run `git switch -c "$(plan-review branch ID)"`. It records the branch in `W/plan.json`; the viewer shows it the next time it opens. For a prompt run the branch is `ID` itself; for an issue it follows the project's `branch` pattern.

## 5. Implement, then review the tests

Let `max` be `max_review_rounds` from `plan-review config`. For round `r = 1 … max`:

1. Start `plan-review:implementer` with: "Run ID, round r." From round 2 on, add: "Fix the findings in W/test-review.md."
2. `before=$(plan-review tree-hash)`.
3. Start `plan-review:test-reviewer` with: "Run ID, round r. Review the tests."
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
Commit everything except `W` (it is gitignored), with a message that explains the change. End it with a reference to the issue and no closing keyword: `Refs #42` for a GitHub issue, the key (`PROJ-123`) for another tracker, and nothing for a prompt run. The project's CLAUDE.md overrides this default if it says how commits reference issues. You write nothing to the tracker: no comments, no status changes. Closing the issue is the owner's call.

Don't push, open a PR, or merge unless the owner asks.

## If something goes wrong

- An agent fails or returns nothing useful: retry it once with the same prompt, then stop and tell the owner.
- The viewer server dies: start it again (step 3.1). The plan, the threads and the approval are on disk.
- The owner asks you to stop: stop the Monitor and the server, and leave the branch and files as they are.
