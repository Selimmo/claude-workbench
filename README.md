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
        ├── pyproject.toml              # Python package `plan-review`
        ├── check.sh                    # every check for this plugin
        ├── README.md                   # commands and the plan.json format
        ├── examples/plan.json          # sample plan using every part of the format
        ├── src/plan_review/            # CLI, plan schema (plan.py), server
        │   └── static/                 # built viewer page (generated, gitignored)
        ├── tests/                      # pytest
        └── web/                        # viewer page: React + TypeScript + Vite
```

## Development (plan-review)

```bash
cd plugins/plan-review
npm install --prefix web   # once
uv sync                    # once

./check.sh                 # everything: web lint, format, tests, build; then ruff, pyright, pytest

uv run plan-review --version
uv run plan-review schema
uv run plan-review validate examples/plan.json
npm --prefix web run dev   # viewer page with hot reload
```

## Tech stack

| Area | Tech |
|---|---|
| CLI and server | Python 3.12+, uv, argparse, pydantic 2 |
| Python checks | ruff, pyright, pytest |
| Viewer page | React 19, TypeScript 6, Vite 8 |
| Web checks | vitest 4 (jsdom, Testing Library), oxlint, prettier |
| CI | GitHub Actions |

## License

[MIT](LICENSE)
