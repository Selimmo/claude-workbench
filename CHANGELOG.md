# Changelog

Notable changes to the plugins in this repo. Versions are plan-review's; each is a GitHub release tagged `plan-review--v<version>`.

## plan-review

### 0.1.12 (2026-11-07)

- The Classes tab is smaller and clearer. Each class says which side it is on (`side`: `front` or `back`), and the tab draws one side at a time with a **Front end** / **Back end** switch (no switch when the plan has one side). A box lists only member names (properties first, methods as `name()`) with a small colour mark on new, changed and removed ones, and its title shows what it extends or implements (`Car: AutoMobile, Insurable`, from a new `bases` list) instead of inherits/implements arrows. New and changed classes are drawn in full, unchanged classes linked to them faded, and plain functions live in a `module` box. Clicking a box opens a popup beside it with the full signatures, what the plan changes and Comment buttons (so commenting on a class takes two clicks). Members get `name`, `kind` (`property` or `method`) and an optional `note`; classes get `side`, `bases`, an optional `note` and the kind `component`. The architecture diagram uses smaller gaps and wrapped edge labels, so arrows stay short. Old plans still open and are drawn as before; only `plan-review validate` now requires the new shape (a new `shape_problems` check), and the architect agent writes it ([#60](https://github.com/Selimmo/claude-workbench/issues/60)).

### 0.1.11 (2026-11-06)

- The page grill has simpler answer controls. Each question is a set of radio buttons, the choices plus **Other**, with one text box under the picked option (optional for a choice, required for Other). The separate own-answer and ask-back boxes are gone: an Other goes into the question's thread, and Claude settles it with a decision or replies (after 3 replies it must settle it; `plan-review grill pending` marks that `must_settle`). The last step is **Yes** or **No**. The page gets answered rows with a tick, a heading per round, a collapsible decisions list grouped by topic (replaced ones behind 'Show replaced'), and Claude's banner stays at the top. `/ship` keeps each decision to one line. `own` and `ask` answers are no longer accepted, but a `grill.json` from 0.1.9 or later still loads. A `grill_drafts.json` left over from an earlier version with `own` or `ask` drafts shows as a broken file: delete it (it only holds unsent answers). A draft left on a question Claude closes is dropped, so it can no longer block Submit, and the broken-file alert and Claude's banner share one solid sticky header on the grill and plan pages ([#56](https://github.com/Selimmo/claude-workbench/issues/56)).

### 0.1.10 (2026-11-05)

- A broken run file is named in its error. A bad `grill.json` or `plan.json` now reads `.claude/work/53/grill.json: Invalid JSON: ...` in the terminal and on the page, like `preferences.json` already did. The same goes for `comments.json`, `drafts.json`, `grill_drafts.json`, `status.json`, `last_event.json` and `approved.json`, which used to crash with a long technical error: a command prints the named lines and exits 1, and the viewer keeps the plan or the questions on screen under a red banner naming the broken file. plan-review only reports a broken file and never overwrites it, except `status.json` (only the status line): when Claude sets a new status over a broken one, it is renamed to `status.json.broken` first ([#55](https://github.com/Selimmo/claude-workbench/issues/55)).

### 0.1.9 (2026-11-05)

- `/plan-review:ship --grill` can ask its questions on a page of its own: with `--grill=page` (or `grill` in `.claude/pipeline.json`, or a recorded preference set with `plan-review prefs grill page|chat`, or the answer to a one-time question) the grilling rounds move from the chat to `/grill` in the viewer. Pick a choice, write your own answer or ask back, submit the round at once, watch the decisions beside it, then confirm; `plan-review grill post|pending|decisions|schema` carry Claude's side. The chat grill is unchanged and stays the fallback ([#53](https://github.com/Selimmo/claude-workbench/issues/53)).

### 0.1.8 (2026-11-05)

- `/plan-review:ship` takes any tracker issue or a plain prompt: a GitHub issue number or link, a Jira or Linear link or a bare key (read through the tracker's connector), or any other text as a prompt. It reads the input once into `.claude/work/<id>/issue.md`, and the agents read that file instead of calling `gh`. Runs are keyed by a text id (`42`, `PROJ-123`, `add-dark-mode-2026-11-05`) in every command; `plan-review init --prompt <name>` creates a dated run folder. A prompt run's plan carries `acceptance_criteria`, shown on their own first tab where each one can be commented on. `plan-review branch` records the branch in `plan.json`, and the viewer shows it the next time it opens. `/ship` no longer comments on or closes anything in a tracker, and the commit references the issue without a closing keyword (unless the project's CLAUDE.md says otherwise). Plans with `issue.number` still load. Only the GitHub and prompt inputs are proven end to end. **If you copied the agents into `.claude/agents/`, copy them again**: the 0.1.7 copies still call `gh` ([#47](https://github.com/Selimmo/claude-workbench/issues/47), supersedes [#40](https://github.com/Selimmo/claude-workbench/issues/40)).

### 0.1.7 (2026-11-04)

- Windows (with Git for Windows) is supported: files are locked with the `filelock` package, a write retries while another process has the file open, and CI runs the backend tests on Windows. `plan-review upgrade` also works with an npm-installed Claude Code on Windows. The minimum Python is now 3.15 and the minimum uv 0.13.0 ([#39](https://github.com/Selimmo/claude-workbench/issues/39)).

### 0.1.6 (2026-11-04)

- Fix: an approval or review sent before Claude's Monitor connected was lost. The last event is now kept in `last_event.json`; the viewer shows a full-width banner that waits for Claude, turns red after 120 s without a response, and offers **Resend** (`GET /api/last-event`, `POST /api/resend`). `/ship` sets a status on approval, ignores a review it already handles, and checks `approved.json` when it re-arms the Monitor ([#45](https://github.com/Selimmo/claude-workbench/issues/45)).

### 0.1.5 (2026-11-03)

- Docs: the README leads with the viewer, has a demo and a security note; maintainer docs moved to [CONTRIBUTING.md](CONTRIBUTING.md) and [RELEASING.md](RELEASING.md) ([#43](https://github.com/Selimmo/claude-workbench/issues/43)).

### 0.1.4 (2026-11-03)

No changes to the plugin. Released to prove `plan-review upgrade` against a public release ([#34](https://github.com/Selimmo/claude-workbench/issues/34)).

### 0.1.3 (2026-11-03)

No changes to the plugin. The first public release: `claude plugin install plan-review --marketplace Selimmo/claude-workbench` works from here on.

### 0.1.2 (2026-11-03)

No changes to the plugin. A private test release, to prove upgrades.

### 0.1.1 (2026-11-03)

The first release, a private test release.

- **Viewer**: `plan-review serve <issue>` opens an issue's `plan.json` as tabs of diagrams and tables: Classes, Architecture, Flows (sequence diagrams and flowcharts), Files, Tests and Risks. Full-page pan and zoom, and an Auto, Light or Dark theme.
- **Review**: click any element to comment. Comments and replies are drafts until you submit the review; Claude answers in the thread or revises the plan, and the page updates live. Approve when every thread is resolved.
- **Pipeline**: `/plan-review:ship <issue>` runs the architect, the viewer review, then the implementer with strict TDD, checked by a test reviewer and a code reviewer. Optional `--grill` to settle decisions first. Project agents in `.claude/agents/` override the plugin's.
- **CLI**: `init`, `serve`, `schema`, `validate`, `threads`, `reply`, `status`, `config`, `branch`, `verdict`, `tree-hash` and `upgrade`.
- **Settings**: `.claude/pipeline.json` for checks, review rules, the branch pattern, how the viewer opens and the review round limit.
- **Install**: one command from a GitHub release zip; upgrade with `plan-review upgrade` or marketplace auto-update.
