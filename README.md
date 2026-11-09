# claude-workbench

**See your coding agent's plan as diagrams before it writes any code.** plan-review is a Claude Code plugin: an agent plans an issue from your tracker (or a plain prompt), and the plan opens in your browser as interactive diagrams of classes, flows, architecture, files, tests and risks. Click anything to comment (a class opens its details first, with a Comment button). Claude answers or revises the plan and the page updates live. When you approve, agents implement it with TDD and review the result.

![Opening a class's details and commenting on it: Claude replies, revises the plan and the new member appears in the diagram](docs/img/demo.gif)

> Status: v0.1, public and installable. Built and dogfooded by one developer, so expect rough edges; [issues](https://github.com/Selimmo/claude-workbench/issues) welcome.

## Who it's for

Developers who use Claude Code for multi-file changes and want to steer the design before the code exists, rather than review a large diff afterwards. The full pipeline takes a GitHub issue, a Jira or Linear issue, or a plain prompt; the viewer on its own needs nothing but a `plan.json`.

## Prerequisites

- macOS, Linux, or Windows with [Git for Windows](https://gitforwindows.org/) (Claude Code's Bash tool on Windows)
- [Claude Code](https://claude.com/claude-code) v2.1.292 or later
- `git`: Claude Code clones the marketplace from GitHub
- [uv](https://docs.astral.sh/uv/) 0.13.0 or later (Python 3.15 is downloaded automatically)
- For GitHub issues in the pipeline: [`gh`](https://cli.github.com/), logged in with `gh auth login`, to read the issue

## Try it

Install the plugin, then run `/reload-plugins` in any open Claude Code session (or start a new one):

```bash
claude plugin install plan-review --marketplace Selimmo/claude-workbench
```

**Without an issue: just the viewer.** The plugin puts `plan-review` on Claude Code's PATH. In a Claude Code session in any folder, load the sample plan in bash mode (start each line with `!`):

```bash
plan-review init 42
curl -fsSL https://raw.githubusercontent.com/Selimmo/claude-workbench/main/plugins/plan-review/examples/plan.json -o .plan-review/work/42/plan.json
```

Then ask Claude to *run `plan-review serve 42` in the background*; it keeps running and opens the viewer in your browser. Comment on anything and submit the review; `plan-review threads 42` shows what Claude would read. Any valid `plan.json` works, whoever wrote it ([format](plugins/plan-review/README.md#the-plan-format-planjson)).

**With an issue or a prompt: the whole pipeline.** In a project, run `/plan-review:ship` with a GitHub issue number or link, a Jira or Linear link or key (through your Claude Code connector for it), or a plain prompt. Only GitHub issues and prompts are proven end to end. For example:

```
/plan-review:ship 42
```

The architect plans issue #42 and the plan opens as diagrams. Comment, submit your review, and Claude answers or revises. Approve it, and agents implement it with TDD and review the result. Nothing is committed without your OK.

### Codex

plan-review also runs in OpenAI Codex. You need [Codex](https://developers.openai.com/codex), `git` and [uv](https://docs.astral.sh/uv/) 0.13.0 or later. Install the command from the newest release's wheel, then put the skill and agents where Codex reads them:

```bash
uv tool install https://github.com/Selimmo/claude-workbench/releases/download/plan-review--v0.3.0/plan_review-0.3.0-py3-none-any.whl
plan-review install codex
```

(Each public release updates the version in that link.) Then run `$ship <issue number, link or prompt>` in Codex; `plan-review upgrade` updates both parts. What differs from Claude Code: Codex has no background watcher, so the agent runs `plan-review serve <id> --detach` (the viewer is its own process, and stops 2 hours after its page closes) and waits with `plan-review wait`, about every 4 minutes while you are away. Codex's sandbox must allow network access, or `gh` and `uv` fail and the viewer can't listen on `127.0.0.1`: in `~/.codex/config.toml` set `network_access = true` under `[sandbox_workspace_write]` (or use a sandbox mode that has it). The agents read `AGENTS.md`; if your project keeps its rules in `CLAUDE.md` only, set `project_doc_fallback_filenames = ["CLAUDE.md"]` in the same file so Codex reads them. To override an agent for one project, put `.codex/agents/<name>.toml` in it. Not tested in Codex's own sandbox yet: run `$ship` once and report what you see.

Upgrade with `plan-review upgrade`, or turn on marketplace auto-update. See [plan-review's README](plugins/plan-review/README.md) for every command, the `plan.json` format, the agents and the project settings.

## What a plan looks like

Every tab of the [sample plan](plugins/plan-review/examples/plan.json). Elements are coloured by whether the plan adds, modifies or removes them, and each one can be commented on.

**Classes**: the types the change touches, one side (front end or back end) at a time. A box lists member names with a mark on what changes, its title shows what it extends (`Car: AutoMobile`), and a click opens the full signatures and Comment buttons.

![Classes tab, back end: boxes list member names with a coloured dot on what the plan adds, modifies or removes](docs/img/plan.png)

| | |
|---|---|
| **Flows**: sequence diagrams… ![Flows tab: a sequence diagram](docs/img/flows-sequence.jpg) | …and flowcharts. ![Flows tab: a flowchart](docs/img/flows-flowchart.jpg) |
| **Architecture**: the components and how they talk. ![Architecture tab](docs/img/architecture.jpg) | **Files**: what is added, modified or removed, and why. ![Files tab](docs/img/files.jpg) |
| **Tests**: the planned tests, in TDD order, each tied to what it covers. ![Tests tab](docs/img/tests.jpg) | **Risks & open questions**, with mitigations. ![Risks tab](docs/img/risks.jpg) |

## What it can touch

From 0.2.0 the project files live in `.plan-review/`: `config.json` for settings and `work/<id>/` for each run. Files that 0.1.x left under `.claude/` are still read when they are the only ones, and are never changed (see the plugin README).

plan-review runs inside your Claude Code session, under your permission settings: anything an agent does through Bash or file edits goes through the same approval prompts as the rest of your session.

- **The viewer** is a local server bound to `127.0.0.1` on a random port. It reads and writes only `.plan-review/work/<id>/` in your project (the plan, comment threads, drafts, approval, and the grill's `grill.json` and `grill_drafts.json`), plus a `.plan-review/work/.gitignore` that keeps it all out of git. It has no authentication, and cross-site requests to it are not blocked yet ([#36](https://github.com/Selimmo/claude-workbench/issues/36)).
- **Your tracker**, read once at the start: `/ship` reads the issue through your logged-in `gh` (GitHub) or the Jira or Linear connector you set up in Claude Code. Nothing is written to the tracker: no comments, no status changes.
- **Git**: `/ship` creates a branch and commits only after your explicit OK. It never pushes, opens a PR or merges unless you ask.
- **Agents**: all four can read your project and run shell commands, so your permission prompts are the real limit. The architect is told to write only `plan.json`, but has a Write tool. The implementer edits files and runs your configured checks. The two reviewers have no edit tools, and `/ship` discards any review that changed a file.

## Roadmap

plan-review is the first plugin here; the aim is a set of tools that take an issue to a reviewed commit with agents. Next for plan-review: see the [open issues](https://github.com/Selimmo/claude-workbench/issues).

## More

- [CHANGELOG.md](CHANGELOG.md): what changed in each release
- [CONTRIBUTING.md](CONTRIBUTING.md): build, test and change the plugins
- [RELEASING.md](RELEASING.md): cutting a release (maintainers)

## License

[MIT](LICENSE)
