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
        ├── src/plan_review/            # CLI, plan schema, server, comment threads, review drafts, /ship helpers, init, upgrade
        │   ├── adapters/               # one adapter per CLI (Claude Code): upgrade steps, generated files, its words
        │   ├── generate.py             # writes agents/ and skills/ from workflow/; `--check` fails on a stale copy
        │   └── static/                 # built viewer page (generated, gitignored)
        ├── tests/                      # pytest
        └── web/                        # viewer page: React + TypeScript + Vite
            └── src/
                ├── plan.ts             # plan.json types (mirror plan.py)
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
uv run python -m plan_review.generate           # rewrite the generated files
uv run python -m plan_review.generate --check   # what check.sh runs: fails if a copy is stale
```

Wording that belongs to one CLI (its tool names, its model nicknames, its override folder) lives in that CLI's adapter under `src/plan_review/adapters/`; the workflow holds a `{{slot}}` there instead.
