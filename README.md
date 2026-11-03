# claude-workbench

Claude Code plugins for taking an issue to a reviewed commit with agents.

| Plugin | What it does |
|---|---|
| [plan-review](plugins/plan-review/README.md) | Agents plan an issue; you review the plan as interactive diagrams (classes, flows, architecture, files, tests, risks), comment on any element, and approve it; agents then implement it with TDD and review it. |

> Status: v0.1. The repo stays private until install and upgrade are proven with test releases (see [Releasing](#releasing-plan-review)); the install command works once it is public.

## Try it

You need macOS or Linux with [Claude Code](https://claude.com/claude-code), `git`, [uv](https://docs.astral.sh/uv/) and [`gh`](https://cli.github.com/) (logged in with `gh auth login`). Then, in a terminal:

```bash
claude plugin install plan-review --marketplace Selimmo/claude-workbench
```

Open Claude Code in a project whose issues live on GitHub, and run:

```
/plan-review:ship 42
```

The architect plans issue #42 and the plan opens in your browser as diagrams. Comment on anything and submit your review; Claude answers or revises. Approve it, and agents implement it with TDD and review the result. Nothing is committed without your OK.

## Prerequisites

To use the plugins:

- macOS or Linux: plan-review locks its files with POSIX `flock`, so Windows is not supported (WSL works)
- [Claude Code](https://claude.com/claude-code) v2.1.292 or later (for `plugin install --marketplace`)
- `git`: Claude Code clones the marketplace from GitHub
- [uv](https://docs.astral.sh/uv/) (Python 3.12+ is downloaded automatically)
- [`gh`](https://cli.github.com/), logged in: `/plan-review:ship` reads the issue and posts the approved plan on it

To develop them, also:

- Node.js 24 LTS (see `plugins/plan-review/web/.nvmrc`), to build the viewer page
- `jq` and `zip` (preinstalled on macOS and GitHub's runners), for the release scripts

## Project structure

```
claude-workbench/
├── .claude-plugin/marketplace.json     # lists the plugins in this repo
├── .github/workflows/
│   ├── plan-review.yml                 # CI for plan-review: version guard, then check.sh
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
        ├── README.md                   # commands, plan.json, agents, pipeline.json
        ├── agents/                     # architect, implementer, test-reviewer, code-reviewer
        ├── skills/ship/SKILL.md        # /plan-review:ship — the orchestrator
        ├── examples/                   # plan.json and pipeline.json samples
        ├── src/plan_review/            # CLI, plan schema, server, comment threads, review drafts, /ship helpers, init, upgrade
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

## Install

```bash
claude plugin install plan-review --marketplace Selimmo/claude-workbench
```

Upgrade with `plan-review upgrade`, or turn on auto-update. See [plan-review's install section](plugins/plan-review/README.md#install), which also covers moving from a local clone's marketplace.

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

## Releasing (plan-review)

Installs come from release zips, never from `main`: Claude Code copies a plugin into its cache and only fetches it again when its version changes.

```bash
cd plugins/plan-review
./release.sh patch     # or ./release.sh 0.3.0
```

`release.sh` runs on an up-to-date, clean `main`. It sets the version in `plugin.json`, `pyproject.toml` and `uv.lock`, commits, tags `plan-review--v<version>` and pushes both together. `patch` bumps the last release, or releases the version a pull request already set; any version must be newer than the last release (before the first one, newer than `plugin.json`'s, which may already be cached).

The tag starts `plan-review-release.yml`:

1. **build** (read-only token): runs `check.sh`, which builds the viewer page, and zips the plugin with `scripts/package.sh` (the files in `scripts/shipped-paths`, the built page and `LICENSE`, plugin root at the top). The built page ships only in the zip: `static/` stays gitignored.
2. **publish**: attaches `plan-review-<version>.zip` to the GitHub release, then runs `scripts/link-release.sh`. If the repo is **public**, it commits the marketplace entry (`archive` source: url, sha256, version) to `main`. If it is **private**, the release is a test release: the log says so and `main` is left alone, because the zip's URL is a 404 for anyone without access.

**Going public, in order:**

1. While the repo is private, make test releases (`./release.sh patch`) and prove them in a throwaway Claude Code config (your own `~/.claude` is not touched). In your terminal, after the first test release run `scripts/prove-release.sh install ~/tmp/proof`; after the second, `scripts/prove-release.sh upgrade ~/tmp/proof`. A private asset's download link takes no token, so the script builds a local copy of the marketplace whose entry downloads the latest release's zip through the GitHub API with your `gh` login, sent by a `headersHelper` (Claude Code asks you to accept it). It also prints the asset's download count before and after, and the versions now in the throwaway cache. When both steps are proven, delete the folder (`rm -rf ~/tmp/proof`): it holds a whole throwaway Claude Code config, the zips and a Python environment.
2. Make the repo public.
3. Release once more. This first public release writes the `archive` entry to `main`, and `claude plugin install plan-review --marketplace Selimmo/claude-workbench` works from then on.
4. Install it with that one command, then release again and check that `plan-review upgrade`, and separately marketplace auto-update, pick up the new version.

**When a release fails.** Use **Re-run failed jobs**: it reuses the zip `build` already made, the release is reused and the zip replaced (`--clobber`), and an entry already linked is left as it is. Avoid **Re-run all jobs** once `main` points at the zip: `build` makes a new zip with a different sha256 and replaces the asset, so installs fail on the sha256 pin until `publish` commits the new one. If `check.sh` fails, the tag already exists and the version guard treats it as released: fix the problem on `main` and release the next patch. To drop the broken tag too, run `git push origin :refs/tags/plan-review--v<version>` and `git tag -d plan-review--v<version>`. If `release.sh`'s push is refused (it is atomic, so neither `main` nor the tag reaches origin), remove the local commit and tag with `git reset --hard origin/main && git tag -d plan-review--v<version>`, then pull and run it again. Protecting `main` on GitHub would block both `release.sh`'s and the workflow's pushes.

**Version guard.** CI fails when anything that ends up in the zip changed since the release of the version in `plugin.json`: the shipped files, the viewer page's sources (`scripts/build-inputs`, without its tests) or `LICENSE`. The first pull request after a release that touches one bumps the version with `scripts/set-version.sh <next>`; `release.sh patch` then releases that version without another commit.

Each release asset's download count should be the install and update count (to be confirmed with the first release): `gh api repos/Selimmo/claude-workbench/releases --jq '.[] | {tag_name, downloads: [.assets[].download_count]}'`.

## Tech stack

| Area | Tech |
|---|---|
| CLI and server | Python 3.12+, uv, argparse, pydantic 2, FastAPI, uvicorn, websockets |
| Python checks | ruff, pyright, pytest |
| Viewer page | React 19, TypeScript 6, Vite 8, elkjs (diagram layout) |
| Web checks | vitest 4 (jsdom, Testing Library), oxlint, prettier |
| CI and releases | GitHub Actions; bash, jq, zip and `gh` for the release scripts |

## License

[MIT](LICENSE)
