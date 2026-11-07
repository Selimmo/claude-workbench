# The Classes tab, before and after (#60)

Two real plans, each kept twice:

| File | What it is |
|---|---|
| `53/plan-0.1.11.json`, `56/plan-0.1.11.json` | The #53 and #56 plans as approved, unchanged: the Classes tab draws them the old way (one diagram, front and back mixed, signatures in the boxes). |
| `53/plan.json`, `56/plan.json` | The same plans in the new shape. Only the classes changed. |

The conversion was done by hand, by these rules:

1. `side`: `front` for everything under `web/` (components, hooks, `.ts` modules, the FakeServer test helper), `back` for the Python.
2. Every member gets a `name` (its id after the class id) and a `kind` (`method` for a function, method or route; `property` for a field, constant or type alias). Its id, signature and status stay.
3. React components (kind `function`) become kind `component`.
4. Other function boxes become a `module` box named after their file (`grill_routes` becomes `plan_review.grill_routes`) and keep their id and members.
5. `bases` come from the merged code (`class GrillError(Exception)` gives `["Exception"]`).
6. `inherits`/`implements` relations, relations across sides and unchanged classes with no changed neighbour would be dropped, but #53 and #56 have none, so the relations stay as they are.

`tests/test_before_after.py` checks that nothing else changed. These files are not shipped in the release zip.

## Open both at the same time

Everything happens in a throwaway folder, never this repo's own `.claude/work/53` or `56` (those are the real runs). Once:

```bash
mkdir -p ~/tmp/before-after && cd ~/tmp/before-after
curl -fsSLO https://github.com/Selimmo/claude-workbench/releases/download/plan-review--v0.1.11/plan-review-0.1.11.zip
unzip -q plan-review-0.1.11.zip -d plan-review-0.1.11
npm --prefix ~/src/claude-workbench/plugins/plan-review/web run build   # with the #60 branch checked out
EX=~/src/claude-workbench/plugins/plan-review/examples/before-after
for n in 53 56; do
  mkdir -p .claude/work/$n-old .claude/work/$n-new
  cp $EX/$n/plan-0.1.11.json .claude/work/$n-old/plan.json
  cp $EX/$n/plan.json .claude/work/$n-new/plan.json
done
```

Side by side, in two terminals:

```bash
cd ~/tmp/before-after && ./plan-review-0.1.11/bin/plan-review serve 53-old   # the old way
cd ~/tmp/before-after && ~/src/claude-workbench/plugins/plan-review/bin/plan-review serve 53-new   # the new way
```

Each opens its own browser window on its own port; put them side by side. Ctrl+C both, then the same with `56-old` and `56-new`. Afterwards `rm -rf ~/tmp/before-after`.
