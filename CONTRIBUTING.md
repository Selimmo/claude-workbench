# Contributing

How to build, test and change the plugins in this repo. To use them, see the [README](README.md); to cut a release, see [RELEASING.md](RELEASING.md).

Work is tracked in GitHub issues, one branch per issue (`<issue#>-short-slug`), with test-driven development; [CLAUDE.md](CLAUDE.md) has the full rules. Any change to prerequisites, structure, commands, tech or versions updates the docs in the same issue.

## Prerequisites

Everything the [README](README.md#install-and-upgrade) lists for using the plugins, plus:

- Node.js 24 LTS (see `plugins/plan-review/web/.nvmrc`), to build the viewer page
- `jq` and `zip` (preinstalled on macOS and GitHub's runners), for the release scripts

## Development (plan-review)

```bash
cd plugins/plan-review
npm install --prefix web   # once
uv sync                    # once

./check.sh                 # everything: web lint, format, tests, build; then ruff, pyright, pytest

uv run plan-review --version
uv run plan-review schema
uv run plan-review validate examples/plan.json
uv run plan-review threads 42 && uv run plan-review reply 42 <thread-id> "text"
npm --prefix web run dev   # viewer page with hot reload
```

**Trying your changes in Claude Code.** Load the plugin from your clone for one session, in place of the installed release (build the viewer page first):

```bash
npm --prefix plugins/plan-review/web run build
claude --plugin-dir ~/src/claude-workbench/plugins/plan-review
```

Edits take effect at the next session start or `/reload-plugins`. Normal sessions keep using the released version.

**Looking at the grill page with demo data.** Build the page once, then serve a copy of an example (`grill.json` is an open round, `grill-done.json` shows the Yes/No step) from the repo root:

```bash
npm --prefix plugins/plan-review/web run build
uv run --project plugins/plan-review plan-review init grill-demo
cp plugins/plan-review/examples/grill.json .plan-review/work/grill-demo/grill.json   # or grill-done.json
uv run --project plugins/plan-review plan-review serve grill-demo
```

Changing anything that ships in the plugin's zip (including `plugins/plan-review/README.md`) means bumping its version; see [Version guard](RELEASING.md#version-guard). Add a line for it to [CHANGELOG.md](CHANGELOG.md).

## Project structure

```
claude-workbench/
├── README.md, CHANGELOG.md             # for users
├── CONTRIBUTING.md, RELEASING.md       # for maintainers
├── .gitattributes                      # LF line endings everywhere (the launcher is a sh script)
├── docs/img/                           # the two README demo GIFs (grill and plan review)
├── .claude-plugin/marketplace.json     # lists the plugins in this repo
├── .github/workflows/
│   ├── plan-review.yml                 # CI for plan-review: version guard, check.sh, backend tests on Windows
│   └── plan-review-release.yml         # on a plan-review--v* tag: build, zip, release, update marketplace.json
└── plugins/
    └── plan-review/
        ├── .claude-plugin/plugin.json  # plugin manifest (its version is the released version)
        ├── bin/plan-review             # on Claude Code's PATH: runs the CLI from this source
        ├── pyproject.toml              # Python package `plan-review`
        ├── check.sh                    # every check for this plugin
        ├── release.sh                  # ./release.sh <version|patch>: set the version, tag, push
        ├── scripts/                    # release helpers: set-version, package (the zip), version-guard,
        │                               #   set-marketplace-entry, link-release, prove-release;
        │                               #   shipped-paths lists what the zip holds, build-inputs what
        │                               #   its viewer page is built from
        ├── README.md                   # commands, plan.json, agents, config.json
        ├── workflow/                   # the /ship workflow and the four agents, written once (edit these)
        ├── agents/                     # GENERATED from workflow/: architect, implementer, test-reviewer, code-reviewer
        ├── skills/ship/SKILL.md        # GENERATED from workflow/: /plan-review:ship, the orchestrator
        ├── examples/                   # plan.json, config.json, grill samples, and demo/ (the README GIFs' inputs)
        ├── src/plan_review/            # only __init__.py at the root; every module lives in a folder (cli/ holds the entry point)
        │   ├── cli/                    # the command line: __init__.py has the parser and main(), one file per command group
        │   │   ├── __main__.py         # python -m plan_review.cli: how the detached viewer starts
        │   │   ├── runtime.py          # Runtime: what a command takes from outside (work folder, date, server, browser), so tests hand in fakes
        │   │   ├── viewer.py           # serve, stop, viewer-process
        │   │   ├── agent.py            # wait, status, reply, threads
        │   │   ├── grill.py            # grill post, pending, decisions, schema
        │   │   ├── pipeline.py         # init, schema, validate, branch, verdict, tree-hash
        │   │   ├── settings.py         # config, prefs
        │   │   └── setup.py            # install, upgrade
        │   ├── utils/                  # generic helpers: safe file saving, JSON files, text checks (imports no other folder)
        │   ├── paths/                  # run ids, the work folder, and RunPaths (every file a run keeps)
        │   ├── settings/               # preferences, pipeline config, migration of old files
        │   ├── plan/                   # the plan.json schema
        │   ├── review/                 # comment threads, review drafts, approval and their routes
        │   │   ├── approval.py         # the approve routes
        │   │   ├── approval_file.py    # ApprovalFile: the only code that reads or writes approved.json
        │   │   ├── drafts.py           # the owner's unsent review comments (drafts.json)
        │   │   ├── routes.py           # the comment-thread routes
        │   │   ├── service.py          # the review: drafts, then one submit that sends them all
        │   │   └── threads.py          # comment threads on plan elements (comments.json)
        │   ├── grill/                  # the grilling before the plan: state, drafts, turns, routes
        │   ├── events/                 # what the agent is told and doing: events, status, last event
        │   │   ├── subscribers.py      # Subscribers (the sockets on one endpoint) and Listeners
        │   │   ├── agent_events.py     # AgentEvents: log, keep for a Resend, push
        │   │   ├── event_log.py        # events.json: record, offer, confirm
        │   │   ├── waiter.py           # wait_for_event, behind `plan-review wait`
        │   │   ├── last_event.py       # the event kept for a Resend
        │   │   ├── resend.py           # the Resend route
        │   │   └── status.py           # what the agent says it is doing
        │   ├── pipeline/               # /ship helpers: branch name, tree hash, review verdict
        │   ├── viewer/                 # the web server (app.py) and the detached viewer
        │   ├── harness/                # workflow, generate.py (writes agents/ and skills/ from workflow/; `--check` fails on a stale copy), upgrade
        │   │   ├── wording.py          # Wording: a tool's 7 names for things
        │   │   ├── adapters/           # one small file per tool (found automatically): its Wording and the pieces it picks
        │   │   ├── agent_files/        # file formats: MarkdownAgents, TomlAgents
        │   │   ├── distribution/       # install and upgrade: MarketplacePlugin, WheelInstall, releases.py
        │   │   └── waiting/            # how an agent waits for the owner: SocketWaiting, PollingWaiting
        │   └── static/                 # built viewer page (generated, gitignored)
        ├── tests/                      # pytest; the folders mirror src/plan_review/
        └── web/                        # viewer page: React + TypeScript + Vite
            └── src/
                ├── plan.ts             # plan.json types (mirror plan/plan.py)
                ├── viewModels.ts       # pure plan → view functions (tested)
                ├── diagram.ts          # plan → boxes-and-arrows model (classes, architecture, flowcharts)
                ├── sequence.ts         # sequence-diagram geometry
                ├── layout.ts           # ELK layout (loaded lazily); DiagramView renders it as DOM
                ├── fit.ts, PanZoom.tsx # full-window pan and zoom: fit all, fill, 100%, minimap
                ├── api.ts, App.tsx, PlanView.tsx
                ├── comments/           # click-to-comment, pins, thread cards, composer, review panel (drafts)
                └── tabs/               # one component per tab
```

## Tech stack

| Area | Tech |
|---|---|
| CLI and server | Python 3.15+, uv, argparse, pydantic 2, filelock, FastAPI, uvicorn, websockets |
| Python checks | ruff, pyright, pytest |
| Viewer page | React 19, TypeScript 6, Vite 8, elkjs (diagram layout) |
| Web checks | vitest 4 (jsdom, Testing Library), oxlint, prettier |
| CI and releases | GitHub Actions; bash, jq, zip and `gh` for the release scripts |

## Changing the /ship workflow or an agent

Edit the text in `plugins/plan-review/workflow/`, never `skills/ship/SKILL.md` or `agents/*.md`: those are generated. Then run, from `plugins/plan-review/`:

```bash
uv run python -m plan_review.harness.generate           # rewrite the generated files
uv run python -m plan_review.harness.generate --check   # what check.sh runs: fails if a copy is stale
```

Wording that belongs to one CLI (its tool names, its model nicknames, its override folder) lives in that CLI's file under `src/plan_review/harness/adapters/` (its `Wording` and the pieces it picks); the workflow holds a `{{slot}}` there instead.

To add a tool, add one file to `adapters/` with one `HARNESS` value built from the existing pieces. Every module in that folder is a tool, found in file-name order (the first tool that recognises a plugin folder wins), so keep only tool files there.
