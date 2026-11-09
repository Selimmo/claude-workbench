# claude-workbench

A Claude Code plugin marketplace. Each tool lives in `plugins/<tool>/` and is its own plugin and its own Python package. The first tool is **plan-review**: agents plan an issue, the owner reviews the plan as interactive diagrams in a local viewer, then agents implement it with TDD and review the result.

## Workflow rules

1. **GitHub issues are the source of truth** (`Selimmo/claude-workbench`). The v0.1 work order is in the pinned tracker, #14; take the first unchecked issue. Stay inside the issue's scope, and propose a new issue for anything else. An issue is done when every acceptance criterion is checked off and the tool's `check.sh` passes.
2. **TDD.** Red → green → refactor, one behaviour at a time. No production code without a failing test that needs it.
3. **Owner involvement.** The owner tests finished tools rather than reviewing each step. Work through issues end to end, and only ask about real product decisions or blockers.
4. **Keep the README current.** Any change to prerequisites, structure, commands, tech or versions updates `README.md` in the same issue.
5. **Git.** One branch per issue (`<issue#>-short-slug`). Commit when the issue is done, referencing it (`Closes #N`).
6. **Public, released through GitHub.** The repo is public. Each release is a zip on a GitHub release that the marketplace points at, and install and upgrade are proven with `scripts/prove-release.sh` (see RELEASING.md). Nothing goes to PyPI.

## Conventions

- Tools are generic. Nothing is specific to one project: project rules come from that project's `.plan-review/config.json` and its CLAUDE.md.
- Python ≥ 3.15, managed with uv; ruff, pyright (strict on `src`) and pytest. CLIs use argparse, and `main(argv) -> int` returns its exit code instead of calling `sys.exit()`.
- Web pages: TypeScript, React and Vite, tested with vitest. They are built into `src/<package>/static/` (gitignored) and shipped inside the Python package.
