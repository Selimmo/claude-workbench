# plan-review

Review an agent's implementation plan as interactive diagrams, comment on any element, and approve it before agents implement and review the code.

> Status: v0.1, installable with the command below. See the [changelog](../../CHANGELOG.md) for what each release changed.

## Install

Runs on macOS and Linux (files are locked with POSIX `flock`); Windows is not supported, WSL works. You need [Claude Code](https://claude.com/claude-code) v2.1.292 or later, `git` (Claude Code clones the marketplace from GitHub), [uv](https://docs.astral.sh/uv/) and [`gh`](https://cli.github.com/), logged in (`/plan-review:ship` reads the issue and posts the approved plan); nothing else: no clone, no build, no Node.js.

```bash
claude plugin install plan-review --marketplace Selimmo/claude-workbench
```

This adds the `claude-workbench` marketplace and installs the latest release: a zip attached to a GitHub release, holding the skill, the agents, the CLI and the built viewer page. The plugin's `bin/plan-review` goes on Claude Code's PATH and runs the CLI with `uv`, which creates its environment on first use. In a session, run `/reload-plugins` (or start a new one).

**Coming from a local clone's marketplace?** It is also named `claude-workbench`, so remove it first: `claude plugin marketplace remove claude-workbench` (this uninstalls its plan-review), then run the install command above.

Then run `/plan-review:ship <issue>` in your project, optionally with a `.claude/pipeline.json` (see below). There is no other setup: plan-review keeps its files in `.claude/work/`, and creates `.claude/work/.gitignore` (`*`) the first time it writes there, so they are never committed.

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
plan-review upgrade              # update the installed plugin to its latest release
plan-review schema               # print the plan.json JSON Schema
plan-review validate plan.json   # check a plan; exit 0 = valid, 1 = invalid, 2 = file not found
plan-review serve 42             # open the viewer for .claude/work/42/plan.json
plan-review serve 42 --open none # only print the URL (e.g. over SSH)
plan-review config               # this project's pipeline settings, defaults filled in
plan-review threads 42           # open comment threads, as JSON (for Claude)
plan-review reply 42 t-1a2b3c4d "Because ..."   # answer a thread as Claude
plan-review status 42 "Answering questions"     # tell the owner what Claude is doing (--done when finished, --clear to remove)
plan-review branch 42            # branch name from pipeline.json's pattern and the plan title
plan-review verdict review.md    # a review's last line: exit 0 PASS, 1 FINDINGS, 2 malformed
plan-review tree-hash            # fingerprint of uncommitted changes (gitignored files excluded)
```

### `serve`

Run it from the project root. It reads `.claude/work/<issue>/plan.json`, refuses to start if the plan is missing or invalid, and serves the viewer on `127.0.0.1` (never other interfaces) on a free port. It prints `plan-review: issue #42 at http://127.0.0.1:<port>/` and opens your default browser.

`--open browser|none` decides whether the browser opens. Without it, `viewer.open` in the project's `.claude/pipeline.json` decides, and the default is `browser`:

```json
{ "viewer": { "open": "none" } }
```

While it runs:

| Endpoint | What |
|---|---|
| `GET /` | the viewer page |
| `GET /api/plan` | the plan (200); `{"errors": [...]}` with 404 if missing, 422 if invalid |
| `WS /api/updates` | sends `{"type": "plan_changed"}` / `{"type": "threads_changed"}` / `{"type": "drafts_changed"}` / `{"type": "status_changed"}` whenever `plan.json` / `comments.json` / `drafts.json` / `status.json` changes on disk |
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

### Events for Claude (`WS /events`)

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

**Commenting in the viewer.** Click any element to comment on it: the issue title or summary, a class or one of its member rows, an arrow, a flow participant or step, a flowchart or architecture box or arrow, a file, a test, a risk or question. Hovering outlines what a click will comment on; dragging pans instead. **Comment on this tab** comments on the tab as a whole. **Add to review** saves the comment as a draft (a dashed pin on its element, and a line under **Your review** on the right), where you can edit or discard it; replies in a thread are drafts too. Drafts are kept in `drafts.json`, so a reload or a restarted server keeps them. **Submit review** sends them all to Claude at once and confirms with a toast, "Review sent (N comments)" (or the error, keeping the drafts). A full-width banner at the top then says "Sent to Claude, waiting for a response"; once Claude sets a status (with `plan-review status`) it shows what Claude is doing (blinking while Claude works, green when done). With no status after 120 s it turns red, "No response from Claude yet", with a **Resend** button; the same goes for an approval. Each submitted thread shows as a numbered pin on its element: hover it for a preview, click it for the whole conversation, where you can reply, resolve or reopen it (Esc or × closes it). Claude's replies appear without a reload. Threads whose element left the plan are listed under **Orphaned comments** on every tab.

**Diagrams.** The page fills the window and each diagram takes all the space below the tabs. It opens fitted, the whole diagram as large as it can be (small ones enlarged up to 1.5x). Wheel or pinch zooms around the pointer, drag pans. **Fit all** returns to the whole picture, **Fill** makes a wide diagram as tall as the window (a tall one as wide) to read it by panning along, and **100%** shows actual size. Whenever part of the diagram is off screen, a minimap in the corner shows all of it with your view outlined: click or drag in it to move there. Flows show one at a time, chosen by title. Boxes are sized from their text measured in the page's real fonts, and sequence columns are spaced so participant names and step labels always fit. Diagrams have a legend for the status colours, files say their change in words, and removed text is struck through. A test's target link opens the target's tab (and flow) and outlines the element. Risks and questions keep the architect's order.

**Revisions and approval.** When the architect revises `plan.json`, the page updates in place (same tab, threads still attached), outlines every changed element and shows "Plan revised: N elements changed" until you click **Mark as seen**. **Approve plan** stays disabled while any draft is unsent or any thread is unresolved; once you approve, the page becomes read-only and the implementer takes over.

The page has a theme switch (top right): **Auto** follows your OS, or pick **Light** or **Dark**. Your choice is remembered in the browser. Text and status colours meet WCAG AA contrast (at least 4.5:1) in both themes.

### Comment threads

Threads live in `.claude/work/<issue>/comments.json`, next to the plan; unsent drafts in `drafts.json` beside it (the CLI and Claude never read them). Every read-modify-write of these files holds an OS file lock (a `<file>.lock` sibling), so the server and `plan-review reply` never lose each other's updates. Each thread is anchored to a plan element id (such as `class:HintPolicy`), to the plan's header (`header:title`, `header:summary`) or to a whole tab (`tab:classes`, `tab:flows`, `tab:architecture`, `tab:files`, `tab:tests`, `tab:risks`), and holds ordered messages from `owner` or `claude` plus a `resolved` flag. The page writes as the owner; Claude answers with `plan-review reply`, never by editing the file. A thread whose element disappears from a revised plan is **orphaned**: kept, and shown separately. Header and tab threads never orphan.

`validate` prints one line per problem, as `location: message`:

```
issue.number: Input should be a valid integer, unable to parse string as an integer
sumary: Extra inputs are not permitted
rel:orch-llm: 'to' points at unknown class id 'class:LLM'
```

## The plan format (`plan.json`)

The architect agent writes it and the viewer renders it. [`examples/plan.json`](examples/plan.json) uses every part of the format.

| Section | What it holds | Shown on tab |
|---|---|---|
| `issue` | `number`, `title`, optional `url` | header |
| `summary` | one paragraph: what changes and why | header |
| `classes` | `id`, `name`, `kind` (class, dataclass, protocol, enum, interface, function, module, type), `status`, `members` (`id`, `signature`, `status`) | Classes |
| `relations` | `id`, `from`, `to` (class ids), `kind` (inherits, implements, uses, creates, contains, depends_on), `status` | Classes |
| `flows` | `kind: "sequence"`: `participants` and ordered `steps` (`from`, `to`, `label`); `kind: "flowchart"`: `nodes` and `edges` (optional `label`) | Flows |
| `architecture` | optional: `nodes` (`kind`: client, service, worker, database, queue, external, library) and `edges` | Architecture |
| `files` | `id`, `path`, `kind` (code, test, config, doc), `change` (added, modified, removed), `reason` | Files |
| `tests` | the TDD order: `id`, `name`, `target` (id of the element it drives out), `behaviour` | Tests |
| `risks` | `id`, `kind` (risk or question), `text`, `severity` (low, medium, high), optional `mitigation` | Risks & open questions |

Rules:

- **`status`** is `added`, `modified`, `removed` or `unchanged`; the viewer colours elements by it.
- **Every element has an `id`, unique across the whole plan.** Comment threads attach to ids, so keep an element's id stable when revising a plan. Prefixes such as `class:`, `flow:`, `test:` are a convention, not a rule.
- **References must exist:** relation ends, flow step and edge ends (within their own flow), architecture edge ends, and test targets.
- **Unknown fields are errors**, so typos are caught rather than ignored.

## Just the viewer

The viewer works on its own, with no agents or pipeline. Any valid `plan.json` will do, whether you wrote it, another tool or agent generated it, or it came from `plan-review schema`:

```bash
plan-review init 7 && cp my-plan.json .claude/work/7/plan.json
plan-review validate .claude/work/7/plan.json
plan-review serve 7        # review, comment, approve in the browser
plan-review threads 7      # read the comments from scripts or other agents
```

Use as much or as little of the rest as you like.

## The pipeline: `/plan-review:ship <issue>`

One command takes an issue to a reviewed commit:

0. **Settle decisions (optional).** Anything already decided can go in `.claude/work/<issue>/decisions.md`: notes, a doc, the outcome of any discussion. The architect treats it as settled. With `/ship <issue> --grill`, `/ship` first runs Matt Pocock's [`grilling`](https://github.com/mattpocock/skills) skill, if you have it, and saves the outcome there.
1. **Plan.** The `architect` writes `.claude/work/<issue>/plan.json`.
2. **Review.** The viewer opens. Your comments and replies are drafts until you press **Submit review**; the submitted review wakes Claude through the `/events` socket: questions are answered in the thread, change requests go back to the architect, the page updates live, and a banner shows what Claude is doing (or offers Resend if it hears nothing). Approve when no draft is left unsent and every thread is resolved.
3. **Branch.** Named by `plan-review branch`.
4. **Implement and review the tests.** `implementer` ⇄ `test-reviewer` until `VERDICT: PASS`.
5. **Review the code.** `implementer` ⇄ `code-reviewer` until `VERDICT: PASS`. Each loop stops and asks you after `max_review_rounds`, and a review that changed files (detected by `plan-review tree-hash` before and after) is discarded.
6. **Hand back.** You get a summary. Claude commits with `Closes #<issue>` only after your OK, and posts the approved plan on the issue. Nothing is pushed or merged unless you ask.

Every pass or fail decision goes through `plan-review verdict` and `tree-hash`, not Claude's own reading.

## The agents

The plugin ships four subagents. Claude Code lists them as `plan-review:<name>`.

| Agent | Model | Can edit files? | Job |
|---|---|---|---|
| `architect` | Opus | writes only `plan.json` | Reads the issue, `decisions.md` (if any), the project's rules and code; writes or revises `.claude/work/<issue>/plan.json` and validates it. In revise mode it keeps element ids stable so comment threads stay attached. |
| `implementer` | Sonnet | yes | Works through the plan's `tests` in order with strict TDD (red for the right reason, minimal green, refactor), runs the checks, and writes `impl-report.md` with the evidence of each red run. Fixes review findings in later rounds. Never commits. |
| `test-reviewer` | Opus | no | Checks the plan's tests exist, one behaviour per test, the red evidence, no untested code, edge cases. Ends with `VERDICT: PASS` or `VERDICT: FINDINGS`. |
| `code-reviewer` | Opus | no | Checks correctness, scope against the issue and plan, the project's rules, docs, and runs every configured check. Same verdict line. |

No agent can start other agents. The reviewers have no edit tools; because they keep Bash to run tests, the orchestrator also compares the working tree before and after each review and discards a review that changed anything.

**Your own copies.** To commit the agents in a project and adapt them, copy them in: `cp <clone>/plugins/plan-review/agents/*.md .claude/agents/`. `/ship` then uses the project's `architect`, `implementer`, `test-reviewer` and `code-reviewer` in place of the plugin's, role by role, for any role whose file exists. Keep each file's frontmatter `name` the same as its file name, and keep the reviewers' last-line verdict format, because `/ship` reads it with `plan-review verdict`.

Every project-specific rule comes from the project itself: its `CLAUDE.md` (or `AGENTS.md`) and `.claude/pipeline.json`.

## Project settings (`.claude/pipeline.json`)

All fields are optional. `plan-review config` prints the resolved settings, and reports mistakes such as unknown keys. See [`examples/pipeline.json`](examples/pipeline.json):

| Field | Default | Meaning |
|---|---|---|
| `checks` | `[]` | `{"name", "run"}` commands the implementer and code reviewer run from the project root; each must pass |
| `review_rules` | `[]` | extra rules the code reviewer enforces, in plain words |
| `branch` | `"{issue}-{slug}"` | the branch name for an issue; must contain `{issue}` |
| `viewer.open` | `"browser"` | `"none"` to only print the viewer's URL |
| `max_review_rounds` | `3` | review rounds before the orchestrator stops and asks you |
