# plan-review in opencode

Install it as the [README](../README.md#opencode) shows. Then run `/plan-review-ship <issue number, link or prompt>` in opencode; `plan-review upgrade` updates both parts.

What differs from Claude Code:

- **Waiting.** opencode has no background watcher, so the agent runs `plan-review serve <id> --detach` (the viewer is its own process, and stops 2 hours after its page closes) and waits with `plan-review wait <id> --timeout 100`. opencode's shell stops a command after 2 minutes, so the wait is 100 seconds, not 240: the model wakes about every 100 seconds while you are away, which uses more quota than in Codex.
- **Where the files go.** The command goes to `~/.config/opencode/commands/plan-review-ship.md` and the agents to `~/.config/opencode/agents/plan-review-<role>.md`, or under `$XDG_CONFIG_HOME/opencode/` when that is set and not empty. `plan-review install opencode` never replaces a file it did not write, and never touches `~/.agents` or `~/.codex`.
- **The command runs in your session.** It sets `agent: build` (opencode's built-in `plan` agent can't write project files such as `decisions.md` and the commit) and `subagent: false`, and it names no model: the session's model is used.
- **The Codex skill.** opencode also lists the Codex `ship` skill from `~/.agents/skills` when it is installed. The command tells the model to follow only its own text and not to load a skill named `ship`.
- **Agents.** They are subagents that may not start other agents; the two reviewers may not edit files. The architect can edit files as well as write them, because opencode's `edit` permission covers both; its instructions still say it writes only `plan.json`.
- **Rules file.** The agents read `AGENTS.md`. opencode itself falls back to `CLAUDE.md` when a project has no `AGENTS.md`.
- **Overrides.** To override an agent for one project, put `.opencode/agents/<name>.md` in it (for example `.opencode/agents/plan-review-architect.md` to replace the plan-review architect).
- **Model.** plan-review sets none, so opencode uses its own default unless you pick one with `/models`, `-m`, or `model` in `opencode.json`. With an Anthropic login, that default was a Fable model.

## What a real run showed

On 2026-11-12, with opencode 2.2.7, signed in with a Claude Pro/Max login, on Sonnet 5.5, we ran `/plan-review-ship Add a subtract(a, b) function to calc.py --grill` in a small Python project. The Codex `ship` skill was installed in `~/.agents/skills` at the same time.

- It went the whole way: grill page (two rounds, an Other answer, a reopen), plan page (a comment and its reply), approval, the implementer, both reviews, and the commit after the owner's OK. It took about 4 minutes and cost about $0.16.
- The command switched opencode from its `plan` agent to `build`. The only skill it loaded was `grilling`; it never loaded the Codex `ship` skill.
- Every `plan-review wait` returned inside opencode's 2-minute shell limit; the longest took 86 seconds.
- Each of the four `plan-review-<role>` agents ran as a subagent and finished.
- One slip by the model: it took a `tree-hash` "before" value too early once, saw that the value was wrong, and checked the diff by hand instead.
- It also showed that a decision from the grill can be left out of the plan without a reviewer noticing. That isn't specific to opencode: see #91.
