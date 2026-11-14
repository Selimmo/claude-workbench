---
name: ship
description: Take one issue (from GitHub, Jira, Linear or another tracker) or one plain prompt from plan to reviewed commit. The architect plans it, the owner reviews and approves the plan in the plan-review viewer, then the implementer builds it with TDD while a test reviewer and a code reviewer check the result.
argument-hint: <issue number, issue link or prompt> [--grill[=page|chat]]
disable-model-invocation: true
---

# /ship: issue or prompt → settled decisions → approved plan → TDD → reviewed commit

You are the **orchestrator**. You run the steps below for the input `$ARGUMENTS`, delegate the real work to the plugin's agents, and talk to the owner. You never write the plan yourself, and you write the code only when `launch` says the implementer is not in the workflow (step 5). You decide pass or fail with `plan-review` helpers, never by your own reading.

**Starting an agent.** Every agent, whichever step it is for, is started the same way. First run `plan-review launch <name> --harness claude-code`, with the agent's name from the step (`grill-explorer`, `architect`, `implementer`, `test-reviewer`, `code-reviewer`, or the name of a custom reviewer from the workflow). It prints JSON: `agent` (what to start), `model` and `effort` (either may be `null`), `review` (for a reviewer, the name of its review file in `W`), `main_session` (true: there is no agent, you do the work yourself) and `instructions`. plan-review's own agents are named `plan-review:<name>`, for example `plan-review:architect`. Then start it with the Agent tool: `subagent_type` is the `agent` value, `model` is the `model` value and `effort` is the `effort` value. If `model` or `effort` is `null`, leave it out: the session's own applies. Never choose the agent, model or effort yourself: `launch` has read the config.

If a start is refused because of its model or effort (an unknown model, an effort the model doesn't offer, a model the owner has no access to), don't wait on it: start the same agent again without `model` and `effort`, and tell the owner in one line: "<agent> runs on the session's model: <the tool's error>". If the tool says the agent itself doesn't exist, tell the owner the agent file is missing (`launch` printed its name) and stop.

Throughout, `ID` is the run id and `W` is `.plan-review/work/ID/`. Step 0 settles `ID` from `$ARGUMENTS` (optionally followed by `--grill`, `--grill=page` or `--grill=chat`): the issue number or key (`42`, `PROJ-123`), or a dated name for a prompt (`add-dark-mode-2026-11-05`). The label of a run is `#42` when `ID` is all digits, otherwise `ID` itself; use it when you talk to the owner. Hand-offs between steps are files in `W`. Pass agents paths, not file contents, and keep your own context small. Only you read the issue from its tracker, once, in step 0. The agents read `W/issue.md`.

## 0. Preconditions

1. Run `plan-review config --harness claude-code` before anything else. It reads the owner's own `config.json` and this project's `.plan-review/config.json` and checks them. If it fails, show the errors and stop: no agent has started. If it works, its output is JSON: `settings` (everything in force, with the workflow in `settings.harness.claude-code.workflow` and each agent's model and effort) and `from` (which file each setting came from). Show the owner each line it printed on stderr, once: a line about moving an old file (an old `preferences.json` choice moves into `.plan-review/config.json`), an agent file that is in use because the config lists it in `replace`, an agent file that is not used and how to turn it on, or a group that runs one after another. Say which agents are in use.

   plan-review's own `implementer`, `test-reviewer` and `code-reviewer` always run, unless the config lists the role in `replace` under `harness.claude-code` and the owner's own file is at `.claude/agents/<name>.md` in the project, or `~/.claude/agents/<name>.md`: the project's first, and if there is none, the owner's own. The `architect` and the `grill-explorer` are always plan-review's own. The project's `.plan-review/config.json` is never committed: plan-review keeps it out of git (it writes `.plan-review/.gitignore`), so it never counts as an uncommitted change, and the step 0 move of an old choice doesn't either.
2. Run `git status --porcelain`. If there are uncommitted changes, stop and ask the owner: the reviewers' read-only check needs a clean starting point. The one exception is a `.plan-review/config.json` that the project already commits: git keeps tracking it, so a change plan-review made to it (the moved choice) shows here. Then ask the owner to commit it first.
3. Read the input (without `--grill`, `--grill=page` or `--grill=chat`) and decide what it is, in this order:
   - A GitHub issue: `42` or `#42` (read it with `gh issue view 42 --comments`), or a `https://github.com/<owner>/<repo>/issues/<n>` link (`gh issue view <link> --comments`). `ID` is the number.
   - Another tracker's link: pick the tracker by host (`*.atlassian.net` is Jira, `linear.app` is Linear) and read the issue with that tracker's connector (an MCP tool). `ID` is the tracker's key, such as `PROJ-123` or `ENG-42`.
   - A bare key such as `PROJ-123`: use the one issue-tracker connector that is available. If none fits, or several do, ask the owner which tracker it is, or whether it is a prompt.
   - Anything else is a prompt.

   For an issue, read its title, link, body and comments once. If it cannot be read (no connector for the tracker, `gh` not logged in), stop with one line: "<tracker> needs a connector; paste the text as a prompt". Then run `plan-review init ID`; an existing `W` means you are resuming that run. It creates `W`, and on first use `.plan-review/work/.gitignore`, so nothing in `.plan-review/work/` is ever committed and the project needs no gitignore entry. Overwrite `W/issue.md` with:

   ```
   # <title>
   <link>

   <body>

   ## Comments
   <each comment, with its author>
   ```

   For a prompt, pick a name of two to four lowercase words joined by dashes, tell the owner which one you picked, and run `plan-review init --prompt <name>`. It prints the new folder, `.plan-review/work/<name>-<date>`, with `-2`, `-3`, ... when that name was already used today. `ID` is that folder's name. Write `W/issue.md` as the prompt exactly as given, nothing added.

## 1. Settle the decisions (only with `--grill`)

If `W/decisions.md` already exists, the architect will use it, whatever produced it (a grilling session, the owner's notes, a doc). Mention it.

Run this step only when the arguments include `--grill`, `--grill=page` or `--grill=chat`. The grilling is done by the **grill explorer**, a plan-review agent that runs one round and ends. You start a new one for every round, and everything is kept on disk, in `W/grill.json` (the questions, the owner's answers and the decisions) and `W/grill-notes.md` (the facts it found), so no round depends on a conversation. Its instructions are Matt Pocock's `grilling` skill (https://github.com/mattpocock/skills, MIT), copied word for word, plus how a round is delivered. You never load a grilling skill yourself.

**Which mode.** Settle it in this order:
1. `--grill=page` or `--grill=chat` decides.
2. For a plain `--grill`, run `plan-review prefs grill`. It prints `page` or `chat` from `grill` in the project's `.plan-review/config.json`, else in the owner's own `config.json`, and exits 0.
3. If it exits 1 (a config file is unreadable), show the owner its message and stop: they fix the file or choose with `--grill=page` / `--grill=chat`.
4. If it exits 3 (nothing is chosen), ask the owner once: "Answer the grilling questions on a page in the viewer, or here in the chat?" Record the answer with `plan-review prefs grill <mode>` (it saves to the owner's own `config.json`; `--project` saves to this project's) and say in one line how to change it: `plan-review prefs grill page|chat`, or `--grill=page` / `--grill=chat` for one run.

**A round, in both modes.** Start the explorer (see "Starting an agent": the name is `grill-explorer`) with "Grill round. Run ID. Mode page." (or "Mode chat."). It reads `W/issue.md`, `W/grill.json` and `W/grill-notes.md`, looks the facts up itself, posts the round with `plan-review grill post` and ends. Its final message says what it posted; in chat mode it also holds the round, in the skill's own format.

**Chat grill.**
1. Start the explorer for the first round. Put its round to the owner in the chat, each question with its recommended answer, and wait for the owner's answers.
2. Write the answers to `W/grill-answers.json`, a JSON list with one item per answered question: `{"question_id": "q1", "kind": "choice", "choice_id": "b"}`, or `{"question_id": "q1", "kind": "other", "text": "<the owner's own words>"}`. Run `plan-review grill answer ID W/grill-answers.json` (if it refuses, fix the file and run it again), then start a new explorer for the next round: it settles what the answers settled, replies to an `other`, and posts the next round.
3. When the explorer says the grill is done, ask the owner: "Is this the shared understanding?" Yes: run `plan-review grill confirm ID`, then `plan-review grill decisions ID`, which writes `W/decisions.md`, and go to step 2. No, with what is missing: run `plan-review grill reopen ID "<what is missing>"` and start a new explorer.

**Page grill.** The owner answers on the page at `/grill` of the same `plan-review serve`; the page records answers, confirm and reopen itself.

1. Run `plan-review grill pending ID`. If it says the grill is `confirmed`, run `plan-review grill decisions ID` and skip to step 2. If `W/grill.json` exists but is not confirmed, you are resuming: start `plan-review serve ID` as in point 2, give the owner its `/grill` URL, then go to point 3 and catch up. Otherwise start the explorer for the first round.
2. Then start `plan-review serve ID` with the Bash tool in the background (`run_in_background`) as in step 3, and read its first line, `plan-review: <label> at http://127.0.0.1:<port>/grill`. Give the owner that URL. The browser opens by itself unless `viewer.open` is `none`; in page mode `none` still uses the page, so give the owner the URL. If `serve` cannot start, carry on in chat mode with the same `W/grill.json`.
3. Subscribe with the **Monitor** tool's WebSocket source: `ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description `plan-review <label> grill`. When it expires, arm it again and catch up with `plan-review grill pending ID`, because events sent while no Monitor listens are lost: handle every pending owner action as below.
4. Each notification is one event, and you answer each with `plan-review status ID "<text>"` first, so the viewer's banner knows you got it:
   - `grill_submitted` with `answers`: status "Answers received". Start a new explorer ("Grill round. Run ID. Mode page."): it settles or replies to every answer the owner gave in their own words (`other`), and posts the next round, or says the grill is done. A Resend repeats an event: if `plan-review grill pending ID` shows nothing pending, ignore it. When the explorer has posted, `plan-review status ID "<what it posted>" --done`.
   - `grill_reopened` with `text`: the owner said No and what is missing. Status "Reading your comment", then start a new explorer for it.
   - `grill_confirmed`: status "Confirmed, planning". Keep the server and the Monitor running: step 3 reuses them. Run `plan-review grill decisions ID` to write `W/decisions.md`, and go to step 2.

## 2. Plan

Start the `architect` with: "Plan mode. Run ID. The issue is in W/issue.md." When it finishes, go straight to step 3. Don't summarize the plan: the owner reads all of it in the viewer.

## 3. Review in the viewer

If a page grill started `plan-review serve` for this run and it is already running, do not start another (point 1) or arm a second Monitor (point 2): the same Monitor receives the review events too. Then set `plan-review status ID "Plan ready for review" --done` (not `--clear`: that would make the owner's last grill event look unanswered), and give the owner the plan page's URL, `http://127.0.0.1:<port>/`.
1. Start `plan-review serve ID` with the Bash tool in the background (`run_in_background`). Read its first output line, `plan-review: <label> at http://127.0.0.1:<port>/`, from the task's output file, and give the owner that URL. The browser opens by itself unless `viewer.open` is `none`.
2. Subscribe to the owner's actions with the **Monitor** tool's WebSocket source: `ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description `plan-review <label>`. A Monitor lasts at most 30 minutes: when it expires before `approved`, arm it again. Events sent while no Monitor is listening are not replayed (the viewer keeps the last one only so the owner can press Resend), so each time you arm it again, catch up: run `plan-review threads ID` and treat every thread whose last message is the owner's (no reply from you yet) as part of a review, and handle it as below; if `W/approved.json` exists, the plan was approved: handle it as `approved` below.
3. Each notification is one JSON event:
   - `review_submitted` with `comments`: the owner submitted a review. If every thread in it is already handled or being handled by you (a Resend repeats the same event), ignore it. Their comments and replies were drafts until now, so this one event holds all of them. Each item has `type` (`comment` for a new thread, `reply` for a reply in an existing one), `thread_id`, `anchor` and `text`: the owner wrote on the element `anchor` (`header:title`/`header:summary` is the plan's header, `tab:<tab>` a whole tab). The viewer shows the owner a banner of what you are doing; set it with `plan-review status ID "<text>"` (the latest text replaces the last) at each stage:
     1. At once: `plan-review status ID "Review received (<count> comments)"`.
     2. Before answering: `plan-review status ID "Answering questions"`.
     3. Before starting the architect: `plan-review status ID "Architect revising (<thread ids>)"`.
     4. When the whole review is handled: `plan-review status ID "<what changed>" --done`, for example "Replies posted to 2 threads; plan updated: HintPolicy split".

     Handle every item of the review:
     - **A question.** Answer it with `plan-review reply ID <thread_id> "<answer>"`. Read the plan and the code first if you need to. Keep answers short and concrete. Put all code and file paths in your answers in backticks; the viewer shows them as code.
     - **A requested change.** Never edit `plan.json` yourself. Take all the change requests of the review together, then start the `architect` once with: "Revise mode. Run ID. Threads: <thread ids>." For each thread, post the architect's line about it with `plan-review reply`. The viewer refreshes by itself and outlines what changed.
     - Never resolve threads. Resolving is the owner's way of saying they are satisfied.
   - `approved`: first run `plan-review status ID "Approved, implementing"`, so the viewer knows you got it. Then go to step 4: stop the Monitor and the server task.

## 4. Branch

Run `git switch -c "$(plan-review branch ID)"`. It records the branch in `W/plan.json`; the viewer shows it the next time it opens. For a prompt run the branch is `ID` itself; for an issue it follows the project's `branch` pattern.

## 5. Implement, then review

Let `max` be `settings.max_review_rounds` and `workflow` be `settings.harness.claude-code.workflow`, both from step 0's output. `workflow` lists the agents after the architect, in order. If the implementer is listed it is the first. Everything else is a review stage, in order: a name is one reviewer, and a list is a group of reviewers that run at the same time. A stage's reviewer may be plan-review's own `test-reviewer` or `code-reviewer`, or a custom reviewer by its own name. A reviewer that is not listed does not run. If `workflow` has no review stage, there is nothing to review.

**Build.** Launch the `implementer` (see "Starting an agent"). If `launch` says `main_session` is true, the implementer is not in the workflow, and you write the code yourself: read the file `instructions` names and follow it as the implementer would, with the same `tdd` setting and the same report, `W/impl-report.md`. Otherwise start it with: "Run ID, round 1." In a fix round the writer (the implementer, or you) is started with: "Run ID, round r. Fix the findings in <every FINDINGS file of the stage, each as W/<review file>>."

**Each stage, in order.** For round `r = 1 … max`:

1. `before=$(plan-review tree-hash)`.
2. Launch each reviewer of the stage and start it with: "Run ID, round r." followed by: "Your final message is the review. It ends with the line `VERDICT: PASS` or `VERDICT: FINDINGS`, with every finding numbered above it as `[must-fix]` or `[should-fix]`." A group is started together (one Agent call per reviewer, all in the same message; wait until every one has returned). If step 0 printed that this tool can't start agents at the same time, start the group's reviewers one after another and say so in one line.
3. `after=$(plan-review tree-hash)`. If `before` ≠ `after`, a reviewer changed files: discard the stage's reviews, tell the owner, and stop.
4. Write each reviewer's final message, unchanged, to its own file `W/<review>` (the `review` value `launch` printed). Then run `plan-review verdict W/<review>` on each. Exit 0 (PASS), exit 1 (FINDINGS), exit 2 (malformed): ask that reviewer once to restate its verdict, then treat a second malformed review as FINDINGS.
5. If every reviewer of the stage has PASS, the stage is done: go to the next stage.
6. Otherwise run one **combined fix round**: the writer gets every FINDINGS file of the stage at once (see above), and then the whole stage runs again, passed reviewers too (go back to point 1 with `r + 1`). However many reviewers a group has, this counts as one round against `max`.

If round `max` of a stage still has FINDINGS, stop. Show the owner the findings and ask whether to continue, change the plan, or take over. When every stage has passed, go to step 6.

## 6. Hand back to the owner

Show, briefly:
- `git diff --stat` against the branch point
- the last verdict line of each review and how many rounds each stage took
- any "Deviations from the plan" in `W/impl-report.md`

Ask for the owner's OK. Only after an explicit OK:
Commit everything except `W` (it is gitignored), with a message that explains the change. End it with a reference to the issue and no closing keyword: `Refs #42` for a GitHub issue, the key (`PROJ-123`) for another tracker, and nothing for a prompt run. The project's CLAUDE.md overrides this default if it says how commits reference issues. You write nothing to the tracker: no comments, no status changes. Closing the issue is the owner's call.

Don't push, open a PR, or merge unless the owner asks.

## If something goes wrong

- An agent fails or returns nothing useful: retry it once with the same prompt, then stop and tell the owner.
- The viewer server dies: start it again (step 3.1). The plan, the threads and the approval are on disk.
- The owner asks you to stop: stop the Monitor and the server, and leave the branch and files as they are.
