# Changelog

Notable changes to the plugins in this repo. Versions are plan-review's; each is a GitHub release tagged `plan-review--v<version>`.

## plan-review

### Unreleased (0.1.5)

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
