# Demo inputs for the README GIFs

The two GIFs at the top of the repo's README (`docs/img/grill.gif` and `docs/img/plan-review.gif`) are recorded from these files, so they can be recorded again after the pages change.

- `plan.json`: a plan that fills every tab, including front-end and back-end classes, two sequence diagrams, a flowchart, the architecture, files, tests, risks and open questions.
- `plan-revised.json`: the same plan after the owner's comment on `HintPolicy.max_hints`. It adds `from_config()`, an `InterviewConfig` box and a test.
- `grill/turn-1.json` … `turn-3.json`: the agent's three grill turns. Turn 1 posts round 1. Turn 2 settles two decisions, replies to the owner's own answer with revised choices, and posts round 2. Turn 3 settles the rest and sets `done`.

## Recording the plan review

In a throwaway project, run `plan-review init 42`, copy `plan.json` into `.plan-review/work/42/`, set `"viewer": {"open": "none"}` in `.plan-review/config.json`, and run `plan-review serve 42`. Then:

1. Show each tab: front-end and back-end classes, the three flows, Architecture, Files, Tests, and Risks & open questions.
2. On the back end, open `HintPolicy` and comment on `max_hints`, then submit the review.
3. As the agent, run `plan-review status 42 "Review received (1 comment)"` and then `plan-review status 42 "Architect revising (<thread>)"`. Copy `plan-revised.json` over `plan.json`, then run `plan-review reply 42 <thread> "..."` and `plan-review status 42 "..." --done`.
4. Open the thread, resolve it and approve.

## Recording the grill

Run `plan-review init 43`, then `plan-review grill post 43 grill/turn-1.json`, and serve `43` (the page is `/grill`). Then:

1. Answer round 1 in three ways: pick a choice and add a note to it, answer Other with your own text, and pick a plain choice.
2. Submit, then as the agent post `grill/turn-2.json`. Pick one of the revised choices, and answer round 2.
3. Submit, then post `grill/turn-3.json`. Confirm the summary page with **Yes**.

Record the browser at about 1500×740 and scale each GIF to 75% with one shared palette, so it stays readable and small.
