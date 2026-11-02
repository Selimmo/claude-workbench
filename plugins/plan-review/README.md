# plan-review

Review an agent's implementation plan as interactive diagrams, comment on any element, and approve it before agents implement and review the code.

> Status: v0.1 in development. Not yet published.

## Commands

```bash
plan-review --version
plan-review schema               # print the plan.json JSON Schema
plan-review validate plan.json   # check a plan; exit 0 = valid, 1 = invalid, 2 = file not found
```

`validate` prints one line per problem, as `location: message`:

```
issue.number: Input should be a valid integer, unable to parse string as an integer
sumary: Extra inputs are not permitted
Value error, rel:orch-llm: 'to' points at unknown class id 'class:LLM'
```

## The plan format (`plan.json`)

The architect agent writes it and the viewer renders it. [`examples/plan.json`](examples/plan.json) uses every part of the format.

| Section | What it holds | Shown on tab |
|---|---|---|
| `issue` | `number`, `title`, optional `url` | header |
| `summary` | one paragraph: what changes and why | header |
| `classes` | `id`, `name`, `kind` (class, dataclass, protocol, enum, interface, function, module, type), `status`, `members` (`id`, `signature`, `status`) | Classes |
| `relations` | `id`, `from`, `to` (class ids), `kind` (inherits, implements, uses, creates, contains, depends_on), `status` | Classes |
| `flows` | `kind: "sequence"`: `participants` and ordered `steps` (`from`, `to`, `label`); `kind: "flowchart"`: `nodes` and `edges` (optional `label`) | Flows |
| `architecture` | optional: `nodes` (`kind`: client, service, worker, database, queue, external, library) and `edges` | Architecture |
| `files` | `id`, `path`, `kind` (code, test, config, doc), `change` (added, modified, removed), `reason` | Files |
| `tests` | the TDD order: `id`, `name`, `target` (id of the element it drives out), `behaviour` | Tests |
| `risks` | `id`, `kind` (risk or question), `text`, `severity` (low, medium, high), optional `mitigation` | Risks & open questions |

Rules:

- **`status`** is `added`, `modified`, `removed` or `unchanged`; the viewer colours elements by it.
- **Every element has an `id`, unique across the whole plan.** Comment threads attach to ids, so keep an element's id stable when revising a plan. Prefixes such as `class:`, `flow:`, `test:` are a convention, not a rule.
- **References must exist:** relation ends, flow step and edge ends (within their own flow), architecture edge ends, and test targets.
- **Unknown fields are errors**, so typos are caught rather than ignored.
