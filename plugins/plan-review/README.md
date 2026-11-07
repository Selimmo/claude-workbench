# plan-review

Review an agent's implementation plan as interactive diagrams, comment on any element, and approve it before agents implement and review the code.

> Status: v0.1, installable with the command below. See the [changelog](../../CHANGELOG.md) for what each release changed.

## Install

Runs on macOS, Linux, or Windows with [Git for Windows](https://gitforwindows.org/). You need [Claude Code](https://claude.com/claude-code) v2.1.292 or later, `git` (Claude Code clones the marketplace from GitHub), [uv](https://docs.astral.sh/uv/) 0.13.0 or later and, only for GitHub issues, [`gh`](https://cli.github.com/), logged in (`/plan-review:ship` reads the issue with it; Jira and Linear issues are read through your Claude Code connector for them); nothing else: no clone, no build, no Node.js.

```bash
claude plugin install plan-review --marketplace Selimmo/claude-workbench
```

This adds the `claude-workbench` marketplace and installs the latest release: a zip attached to a GitHub release, holding the skill, the agents, the CLI and the built viewer page. The plugin's `bin/plan-review` goes on Claude Code's PATH and runs the CLI with `uv`, which creates its environment on first use. In a session, run `/reload-plugins` (or start a new one).

**Coming from a local clone's marketplace?** It is also named `claude-workbench`, so remove it first: `claude plugin marketplace remove claude-workbench` (this uninstalls its plan-review), then run the install command above.

Then run `/plan-review:ship <issue number, issue link or prompt>` in your project, optionally with a `.claude/pipeline.json` (see below). There is no other setup: plan-review keeps its files in `.claude/work/`, and creates `.claude/work/.gitignore` (`*`) the first time it writes there, so they are never committed.

### Upgrade

```bash
plan-review upgrade
```

It refreshes the marketplace and updates the plugin (`claude plugin marketplace update claude-workbench`, then `claude plugin update plan-review@claude-workbench`); run `/reload-plugins` or start a new session to load the new version. Or let Claude Code do it: in `/plugin`, open **Marketplaces**, select `claude-workbench` and choose **Enable auto-update**. It then updates the plugin in the background after a session starts, and the new version loads on your next launch.

Claude Code keeps a copy of each installed version and only fetches a new one when a new version is released, so editing a clone of this repo never changes your installed plugin. To work on the plugin itself, see [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Commands

```bash
plan-review --version
plan-review init 42              # create .claude/work/42/ (and .claude/work/.gitignore); /ship runs it first
plan-review init PROJ-123        # a run id is an issue number or key: letters, digits, '.', '_' and '-'
plan-review init --prompt add-dark-mode   # a prompt run: creates .claude/work/add-dark-mode-<today>/ (-2, -3, ... if taken)
plan-review upgrade              # update the installed plugin to its latest release
plan-review schema               # print the plan.json JSON Schema
plan-review validate plan.json   # check a plan; exit 0 = valid, 1 = invalid, 2 = file not found
plan-review serve 42             # open the viewer for .claude/work/42/plan.json
plan-review serve 42 --open none # only print the URL (e.g. over SSH)
plan-review config               # this project's pipeline settings, defaults filled in
plan-review prefs grill          # the grill mode in force (page or chat); exit 3 if none is chosen
plan-review prefs grill page     # record the owner's choice (page or chat) in .claude/work/preferences.json
plan-review grill post 42 turn.json   # add the agent's next turn (replies, decisions, next round, done) to grill.json
plan-review grill pending 42     # JSON {confirmed, pending}: what the owner did that is not answered yet
plan-review grill decisions 42   # write .claude/work/42/decisions.md from the confirmed grill
plan-review grill schema         # the JSON Schema of a turn
plan-review threads 42           # open comment threads, as JSON (for Claude)
plan-review reply 42 t-1a2b3c4d "Because ..."   # answer a thread as Claude
plan-review status 42 "Answering questions"     # tell the owner what Claude is doing (--done when finished, --clear to remove)
plan-review branch 42            # the branch: the one recorded in plan.json, else made from pipeline.json's pattern and the plan title, and recorded there
plan-review verdict review.md    # a review's last line: exit 0 PASS, 1 FINDINGS, 2 malformed
plan-review tree-hash            # fingerprint of uncommitted changes (gitignored files excluded)
```

### `serve`

Run it from the project root. It reads `.claude/work/<id>/plan.json`, refuses to start if the plan is invalid, or if there is neither a plan nor a `grill.json` (exit 2), and serves the viewer on `127.0.0.1` (never other interfaces) on a free port. It prints `plan-review: #42 at http://127.0.0.1:<port>/` (`plan-review: PROJ-123 at ...` for a key) and opens your default browser. With a `grill.json` and no plan yet it prints and opens `http://127.0.0.1:<port>/grill` instead.

`--open browser|none` decides whether the browser opens. Without it, `viewer.open` in the project's `.claude/pipeline.json` decides, and the default is `browser`:

```json
{ "viewer": { "open": "none" } }
```

While it runs:

| Endpoint | What |
|---|---|
| `GET /` | the viewer page; redirects to `/grill` while there is no `plan.json` |
| `GET /grill` | the viewer page, showing the grill |
| `GET /api/grill` | the grill (`title`, `label`, `rounds`, `decisions`, `out_of_scope`, `done`, `confirmed_at`, `log`, `handled`) plus `max_replies: 3` (how many times Claude may reply to Other answers on one question before it must settle it); 404 without `grill.json` |
| `GET /api/grill/drafts`, `PUT`, `DELETE /api/grill/drafts/<question id>` | the owner's unsent answers (`{kind: choice\|other, choice_id?, text?}`; an Other draft may be empty while the owner types); 404 for an unknown or answered question, 422 for an invalid draft (`own` and `ask` drafts are no longer accepted). Not announced to `/events` |
| `POST /api/grill/submit` | records every draft as an answer (an Other goes into the question's thread and the question stays open) and sends one `grill_submitted` event; 422 while an open question has no draft or an Other has no text, 409 while it is Claude's turn |
| `POST /api/grill/confirm`, `/api/grill/reopen {text}` | the owner answers Yes to the finished grill (`grill_confirmed`), or No with what is missing (`grill_reopened`); 409 unless Claude said it is done, 422 for blank text |
| `GET /api/plan` | the plan (200); `{"errors": [...]}` with 404 if missing, 422 if invalid |
| `WS /api/updates` | also `{"type": "grill_changed"}` / `{"type": "grill_drafts_changed"}` for `grill.json` / `grill_drafts.json`. Sends `{"type": "plan_changed"}` / `{"type": "threads_changed"}` / `{"type": "drafts_changed"}` / `{"type": "status_changed"}` whenever `plan.json` / `comments.json` / `drafts.json` / `status.json` changes on disk |
| `GET /api/status` | `{"status": null}`, or `{"status": {"text", "done", "at"}}`: what Claude last said it is doing |
| `GET /api/threads` | all comment threads, each with `orphaned: true` if its element left the plan |
| `POST /api/threads/<id>/resolve`, `/reopen` | close or reopen a thread |
| `GET /api/drafts` | the owner's unsent review comments |
| `POST /api/drafts` | `{"anchor", "text"}` for a new comment, or `{"thread_id", "text"}` for a reply: adds a draft (201). Not announced |
| `PUT /api/drafts/<id>`, `DELETE /api/drafts/<id>` | edit (`{"text"}`) or discard a draft |
| `POST /api/review` | submit the review: every draft becomes a thread or a reply, the drafts are cleared, and one `review_submitted` event goes to `/events`; 422 if there are no drafts |

| `GET /api/approve` | `{"approved": false}`, or `true` with the approval record |
| `POST /api/approve` | approve the plan: 409 while any draft is unsent or any thread is unresolved, 422 if the plan is invalid; otherwise writes `approved.json` (`approved_at`, `plan_sha256`) |
| `GET /api/last-event` | `{"last_event": null}`, or `{"last_event": {"type", "sent_at", "answered"}}`: the last event sent to `/events`; `answered` is true once Claude set a status after it |
| `POST /api/resend` | send the kept event to `/events` again: `{"sent": true}`; `{"sent": false, "status": ...}` and nothing sent if Claude already answered; 409 if nothing was sent yet |
| `WS /events` | the owner's actions, for Claude (below) |

Errors come back as `{"errors": [...]}`: 404 for an unknown thread or draft, 422 for blank text.

A run file that is there but broken (`plan.json`, `grill.json`, `comments.json`, `drafts.json`, `grill_drafts.json`, `status.json`, `last_event.json`, `approved.json`) answers 422 on the routes that read it, with lines that start with its path, such as `.claude/work/42/comments.json: Invalid JSON: key must be a string at line 1 column 2`. The viewer shows them in a red banner and keeps the rest on screen. A command that reads such a file prints the same lines on stderr and exits 1. plan-review never deletes or overwrites a broken file. The one exception is `status.json`, which holds only the status line: when Claude sets or clears a status over a broken one, the old file is renamed to `status.json.broken` (replacing an older copy), the command says so on stderr, and the new status is written.

### Events for Claude (`WS /events`)

The page grill adds three events: `{"type": "grill_submitted", "answers": [{"question_id", "kind": "choice"|"other", "choice_id"?, "text"?}]}`, `{"type": "grill_confirmed"}` and `{"type": "grill_reopened", "text"}`. They are kept and resent like the others.

One JSON message per owner action. The owner reviews like a pull request: comments and replies stay drafts, which never reach this socket, until **Submit review** sends them all as one message:

```json
{"type": "review_submitted", "comments": [
  {"type": "comment", "thread_id": "t-1a2b3c4d", "anchor": "class:HintPolicy", "text": "Why a class?"},
  {"type": "reply",   "thread_id": "t-5e6f7a8b", "anchor": "risk:1",           "text": "Thanks"}
]}
{"type": "approved"}
```

In `comments`, in the order written, `comment` is a new thread and `reply` an owner reply in an existing one. One message per review, not one per comment, so Claude wakes once with the whole batch and can answer and revise together. Claude's own replies go through the CLI, not the server, so they never produce an event and Claude is never woken by itself.

In Claude Code, subscribe with the `Monitor` tool's WebSocket source. Each message becomes one notification:

```
Monitor({ ws: { url: "ws://127.0.0.1:<port>/events" }, description: "plan-review #42", timeout_ms: 1800000 })
```

A Monitor expires after at most 30 minutes, so re-arm it until `approved` arrives (then also check for `approved.json`, as an approval sent meanwhile is not replayed).

The socket is fire-and-forget: an event sent while no Monitor is connected is lost. So the server keeps the last event in `last_event.json` (with `sent_at`), and the viewer's **Resend** button sends it again, unless Claude has set a status since. Nothing else is replayed.

**Commenting in the viewer.** Click any element to comment on it: the issue title or summary, an arrow, a flow participant or step, a flowchart or architecture box or arrow, a file, a test, a risk or question. A click on a class box opens its details popup instead (see Diagrams), whose **Comment** buttons comment on the class or on one of its members. Hovering outlines what a click will comment on; dragging pans instead. **Comment on this tab** comments on the tab as a whole. **Add to review** saves the comment as a draft (a dashed pin on its element, and a line under **Your review** on the right), where you can edit or discard it; replies in a thread are drafts too. Drafts are kept in `drafts.json`, so a reload or a restarted server keeps them. **Submit review** sends them all to Claude at once and confirms with a toast, "Review sent (N comments)" (or the error, keeping the drafts). A full-width banner at the top then says "Sent to Claude, waiting for a response"; once Claude sets a status (with `plan-review status`) it shows what Claude is doing (blinking while Claude works, green when done). With no status after 120 s it turns red, "No response from Claude yet", with a **Resend** button; the same goes for an approval. Each submitted thread shows as a numbered pin on its element: hover it for a preview, click it for the whole conversation, where you can reply, resolve or reopen it (Esc or × closes it). Claude's replies appear without a reload. Threads whose element left the plan are listed under **Orphaned comments** on every tab.

**Diagrams.** The page fills the window and each diagram takes all the space below the tabs. It opens fitted, the whole diagram as large as it can be (small ones enlarged up to 1.5x). Wheel or pinch zooms around the pointer, drag pans. **Fit all** returns to the whole picture, **Fill** makes a wide diagram as tall as the window (a tall one as wide) to read it by panning along, and **100%** shows actual size. Whenever part of the diagram is off screen, a minimap in the corner shows all of it with your view outlined: click or drag in it to move there. Flows show one at a time, chosen by title. Boxes are sized from their text measured in the page's real fonts, and sequence columns are spaced so participant names and step labels always fit. Diagrams have a legend for the status colours, files say their change in words, and removed text is struck through. A test's target link opens the target's tab (and flow) and outlines the element. Risks and questions keep the architect's order.

**Classes.** The Classes tab draws one side at a time, with a **Front end** / **Back end** switch (no switch when every class is on one side). A box shows only the names of its members, properties first and then methods as `name()`, with a small colour mark on new, changed and removed ones, and its title shows what it extends or implements (`Car: AutoMobile, Insurable`). New and changed classes are drawn in full; unchanged classes directly linked to them are drawn faded. Click a box for a popup beside it with the full signatures, what the plan changes (new, changed, removed, plus the optional `note`) and **Comment** buttons; it opens on an approved plan too, without the buttons. Comments on the other side's classes are listed under **Comments on the other side**. The architecture diagram uses tighter gaps and wraps long arrow labels. A plan written before 0.1.12 (classes without `side`) still opens and is drawn as one diagram with signatures; only `plan-review validate` requires the new shape.

**Revisions and approval.** When the architect revises `plan.json`, the page updates in place (same tab, threads still attached), outlines every changed element and shows "Plan revised: N elements changed" until you click **Mark as seen**. **Approve plan** stays disabled while any draft is unsent or any thread is unresolved; once you approve, the page becomes read-only and the implementer takes over.

The page has a theme switch (top right): **Auto** follows your OS, or pick **Light** or **Dark**. Your choice is remembered in the browser. Text and status colours meet WCAG AA contrast (at least 4.5:1) in both themes.

### Comment threads

Threads live in `.claude/work/<id>/comments.json`, next to the plan; unsent drafts in `drafts.json` beside it (the CLI and Claude never read them). Every read-modify-write of these files holds an OS file lock (a `<file>.lock` sibling), so the server and `plan-review reply` never lose each other's updates. Each thread is anchored to a plan element id (such as `class:HintPolicy`), to the plan's header (`header:title`, `header:summary`) or to a whole tab (`tab:criteria`, `tab:classes`, `tab:flows`, `tab:architecture`, `tab:files`, `tab:tests`, `tab:risks`), and holds ordered messages from `owner` or `claude` plus a `resolved` flag. The page writes as the owner; Claude answers with `plan-review reply`, never by editing the file. A thread whose element disappears from a revised plan is **orphaned**: kept, and shown separately. Header and tab threads never orphan.

`validate` prints one line per problem, as `location: message`:

```
issue.kind: Field required
sumary: Extra inputs are not permitted
rel:orch-llm: 'to' points at unknown class id 'class:LLM'
```

## The plan format (`plan.json`)

The architect agent writes it and the viewer renders it. [`examples/plan.json`](examples/plan.json) uses every part of the format for an issue, and [`examples/prompt-plan.json`](examples/prompt-plan.json) is a prompt run with `acceptance_criteria` and `branch`.

| Section | What it holds | Shown on tab |
|---|---|---|
| `issue` | `id` (the run id), `kind` (`issue` or `prompt`), `title`, optional `url`. An old `number: 42` still loads, as id `"42"`, kind `issue` | header |
| `summary` | one paragraph: what changes and why | header |
| `acceptance_criteria` | a list of strings, required when `issue.kind` is `prompt`. Numbered from 1; each is commentable as `criterion:<n>` | Acceptance criteria (first tab, only when present) |
| `branch` | optional: the branch name; `plan-review branch` records it | header |
| `classes` | `id`, `name`, `kind` (class, dataclass, protocol, enum, interface, component, module, type; `function` still loads but `validate` refuses it), `side` (`front` or `back`), `bases` (what it extends or implements, text), optional `note`, `status`, `members` (`id`, `name`, `kind` (`property` or `method`), `signature`, optional `note`, `status`) | Classes |
| `relations` | `id`, `from`, `to` (class ids), `kind` (uses, creates, contains, depends_on; `inherits` and `implements` still load but `validate` refuses them: use `bases`), `status` | Classes |
| `flows` | `kind: "sequence"`: `participants` and ordered `steps` (`from`, `to`, `label`); `kind: "flowchart"`: `nodes` and `edges` (optional `label`) | Flows |
| `architecture` | optional: `nodes` (`kind`: client, service, worker, database, queue, external, library) and `edges` | Architecture |
| `files` | `id`, `path`, `kind` (code, test, config, doc), `change` (added, modified, removed), `reason` | Files |
| `tests` | the TDD order: `id`, `name`, `target` (id of the element it drives out), `behaviour` | Tests |
| `risks` | `id`, `kind` (risk or question), `text`, `severity` (low, medium, high), optional `mitigation` | Risks & open questions |

Rules:

- **`status`** is `added`, `modified`, `removed` or `unchanged`; the viewer colours elements by it.
- **Criteria are numbered by position** (`criterion:1`, ...), so a revision should append criteria and keep existing ones in place; a comment on a removed row becomes orphaned.
- **Every element has an `id`, unique across the whole plan.** Comment threads attach to ids, so keep an element's id stable when revising a plan. Prefixes such as `class:`, `flow:`, `test:` are a convention, not a rule.
- **References must exist:** relation ends, flow step and edge ends (within their own flow), architecture edge ends, and test targets.
- **Unknown fields are errors**, so typos are caught rather than ignored.
- **`validate` also requires the current class shape**, which loading does not: every class has a `side`, every member a `name` and `kind`, no class has kind `function` (put a plain function in its module's box as a method), no `inherits`/`implements` relation (use `bases`), no relation joins a front and a back class, and no unchanged class is linked to no changed class on its side (it would not be drawn). A class counts as changed when its own status or any member's status is not `unchanged`.

## Just the viewer

The viewer works on its own, with no agents or pipeline. Any valid `plan.json` will do, whether you wrote it, another tool or agent generated it, or it came from `plan-review schema`:

```bash
plan-review init 7 && cp my-plan.json .claude/work/7/plan.json
plan-review validate .claude/work/7/plan.json
plan-review serve 7        # review, comment, approve in the browser
plan-review threads 7      # read the comments from scripts or other agents
```

Use as much or as little of the rest as you like.

## The pipeline: `/plan-review:ship <issue number, issue link or prompt>`

One command takes an issue, or a plain prompt, to a reviewed commit. The input can be a GitHub issue (`42`, `#42` or its link), a Jira or Linear link or a bare key such as `PROJ-123` (read through the connector Claude Code has for that tracker), or any other text, which is a prompt. Only the GitHub and prompt inputs are proven end to end. `/ship` reads the issue once, with its comments, into `.claude/work/<id>/issue.md` (a prompt is written there exactly as given); the agents read that file and never call a tracker. The run id `<id>` names the work folder: `42`, `PROJ-123`, or `<prompt name>-<date>`.

0. **Settle decisions (optional).** Anything already decided can go in `.claude/work/<id>/decisions.md`: notes, a doc, the outcome of any discussion. The architect treats it as settled. With `/ship <input> --grill`, `/ship` first grills the input with Matt Pocock's [`grilling`](https://github.com/mattpocock/skills) skill, if you have it, and saves the outcome there. There are two ways to be asked. The **page grill** puts each round on a `/grill` page of the same `plan-review serve`: each question is a set of radio buttons, the choices (the first is the recommendation) plus **Other**. Picking one opens a single text box under it: optional for a choice (a few words of note), required for Other (your own option, a question or a comment), and the text moves along when you switch options. You submit the round at once. A choice closes its question. An Other keeps it open: Claude either settles it with a decision (your text becomes the answer) or replies, and you pick again; after three replies Claude has to settle it, and the box says so. Answered questions are tidy rows with a tick, the answer in bold and your note in grey, under a heading for each round. The decisions pile up in a collapsible column beside the rounds (grouped by topic, with each why; replaced ones behind 'Show replaced'; open or closed is remembered in the browser). Claude's banner stays at the top of the window. At the end Claude asks 'Is this the shared understanding?': **Yes** confirms at once, **No** asks what is missing and reopens the grill. Claude's side goes through `plan-review grill post`, and `plan-review grill decisions` writes `decisions.md`. The **chat grill** asks in the chat, as before. The mode is `--grill=page` or `--grill=chat`; for a plain `--grill`, the `grill` setting in `.claude/pipeline.json`, else your recorded preference (`plan-review prefs grill page|chat`); if neither exists `/ship` asks once and records the answer. If `serve` cannot start, the chat grill is the fallback. A confirmed grill is not asked again when you run `/ship` again.
1. **Plan.** The `architect` writes `.claude/work/<id>/plan.json`. For a prompt run it also writes the `acceptance_criteria`, which you approve with the plan; they open as the first tab.
2. **Review.** The viewer opens. Your comments and replies are drafts until you press **Submit review**; the submitted review wakes Claude through the `/events` socket: questions are answered in the thread, change requests go back to the architect, the page updates live, and a banner shows what Claude is doing (or offers Resend if it hears nothing). Approve when no draft is left unsent and every thread is resolved.
3. **Branch.** Named by `plan-review branch` and recorded in `plan.json`; the viewer shows it the next time it opens. A prompt run's branch is its id.
4. **Implement and review the tests.** `implementer` ⇄ `test-reviewer` until `VERDICT: PASS`.
5. **Review the code.** `implementer` ⇄ `code-reviewer` until `VERDICT: PASS`. Each loop stops and asks you after `max_review_rounds`, and a review that changed files (detected by `plan-review tree-hash` before and after) is discarded.
6. **Hand back.** You get a summary. Claude commits only after your OK, referencing the issue without a closing keyword (`Refs #42`, or `PROJ-123`; nothing for a prompt) unless your CLAUDE.md says otherwise. Nothing is written to the tracker, and nothing is pushed or merged unless you ask.

Every pass or fail decision goes through `plan-review verdict` and `tree-hash`, not Claude's own reading.

## The agents

The plugin ships four subagents. Claude Code lists them as `plan-review:<name>`.

| Agent | Model | Can edit files? | Job |
|---|---|---|---|
| `architect` | Opus | writes only `plan.json` | Reads `issue.md`, `decisions.md` (if any), the project's rules and code; writes or revises `.claude/work/<id>/plan.json` and validates it. In revise mode it keeps element ids stable so comment threads stay attached. |
| `implementer` | Sonnet | yes | Works through the plan's `tests` in order with strict TDD (red for the right reason, minimal green, refactor), runs the checks, and writes `impl-report.md` with the evidence of each red run. Fixes review findings in later rounds. Never commits. |
| `test-reviewer` | Opus | no | Checks the plan's tests exist, one behaviour per test, the red evidence, no untested code, edge cases. Ends with `VERDICT: PASS` or `VERDICT: FINDINGS`. |
| `code-reviewer` | Opus | no | Checks correctness, scope against the issue and plan, the project's rules, docs, and runs every configured check. Same verdict line. |

No agent can start other agents. The reviewers have no edit tools; because they keep Bash to run tests, the orchestrator also compares the working tree before and after each review and discards a review that changed anything.

**Your own copies.** To commit the agents in a project and adapt them, copy them in: `cp <clone>/plugins/plan-review/agents/*.md .claude/agents/`. `/ship` then uses the project's `architect`, `implementer`, `test-reviewer` and `code-reviewer` in place of the plugin's, role by role, for any role whose file exists. Copy them again after you upgrade: copies from 0.1.7 still call `gh` and expect an issue number. Keep each file's frontmatter `name` the same as its file name, and keep the reviewers' last-line verdict format, because `/ship` reads it with `plan-review verdict`.

Every project-specific rule comes from the project itself: its `CLAUDE.md` (or `AGENTS.md`) and `.claude/pipeline.json`.

## Project settings (`.claude/pipeline.json`)

All fields are optional. `plan-review config` prints the resolved settings, and reports mistakes such as unknown keys. See [`examples/pipeline.json`](examples/pipeline.json):

| Field | Default | Meaning |
|---|---|---|
| `checks` | `[]` | `{"name", "run"}` commands the implementer and code reviewer run from the project root; each must pass |
| `review_rules` | `[]` | extra rules the code reviewer enforces, in plain words |
| `branch` | `"{issue}-{slug}"` | the branch name for an issue; must contain `{issue}`, which is the run id (`42`, `PROJ-123`). A prompt run's branch is just its id |
| `viewer.open` | `"browser"` | `"none"` to only print the viewer's URL |
| `grill` | none | `"page"` or `"chat"`: where `/ship --grill` asks its questions; unset means your recorded preference, else it asks once |
| `max_review_rounds` | `3` | review rounds before the orchestrator stops and asks you |
