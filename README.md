# claude-workbench

Claude Code plugins for taking an issue to a reviewed commit with agents.

| Plugin | What it does |
|---|---|
| [plan-review](plugins/plan-review/README.md) | Agents plan an issue; you review the plan as interactive diagrams (classes, flows, architecture, files, tests, risks), comment on any element, and approve it; agents then implement it with TDD and review it. |

> Status: v0.1 in development. Not yet published.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12+ is downloaded automatically)
- Node.js 24 LTS (see `plugins/plan-review/web/.nvmrc`), to build the viewer page
- [Claude Code](https://claude.com/claude-code)

## Project structure

```
claude-workbench/
├── .claude-plugin/marketplace.json     # lists the plugins in this repo
├── .github/workflows/plan-review.yml   # CI for plan-review
└── plugins/
    └── plan-review/
        ├── .claude-plugin/plugin.json  # plugin manifest
        ├── bin/plan-review             # on Claude Code's PATH: runs the CLI from this source
        ├── pyproject.toml              # Python package `plan-review`
        ├── check.sh                    # every check for this plugin
        ├── README.md                   # commands, plan.json, agents, pipeline.json
        ├── agents/                     # architect, implementer, test-reviewer, code-reviewer
        ├── skills/ship/SKILL.md        # /plan-review:ship — the orchestrator
        ├── examples/                   # plan.json and pipeline.json samples
        ├── src/plan_review/            # CLI, plan schema, server, comment threads, /ship helpers
        │   └── static/                 # built viewer page (generated, gitignored)
        ├── tests/                      # pytest
        └── web/                        # viewer page: React + TypeScript + Vite
            └── src/
                ├── plan.ts             # plan.json types (mirror plan.py)
                ├── viewModels.ts       # pure plan → view functions (tested)
                ├── diagram.ts          # plan → boxes-and-arrows model (classes, architecture, flowcharts)
                ├── sequence.ts         # sequence-diagram geometry
                ├── layout.ts           # ELK layout (loaded lazily); DiagramView renders it as DOM
                ├── api.ts, App.tsx, PlanView.tsx
                ├── comments/           # pins, thread cards, composer, comment mode
                └── tabs/               # one component per tab
```

## Install

See [plan-review's install section](plugins/plan-review/README.md#install-local-v01).

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

## Tech stack

| Area | Tech |
|---|---|
| CLI and server | Python 3.12+, uv, argparse, pydantic 2, FastAPI, uvicorn, websockets |
| Python checks | ruff, pyright, pytest |
| Viewer page | React 19, TypeScript 6, Vite 8, elkjs (diagram layout) |
| Web checks | vitest 4 (jsdom, Testing Library), oxlint, prettier |
| CI | GitHub Actions |

## License

[MIT](LICENSE)
