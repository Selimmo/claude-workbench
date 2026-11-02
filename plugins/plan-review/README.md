# plan-review

Review an agent's implementation plan as interactive diagrams, comment on any element, and approve it before agents implement and review the code.

> Status: v0.1 in development. Not yet published.

## Commands

```bash
plan-review --version
plan-review schema               # print the plan.json JSON Schema
plan-review validate plan.json   # check a plan; exit 0 = valid, 1 = invalid, 2 = file not found
plan-review serve 42             # open the viewer for .claude/work/42/plan.json
plan-review serve 42 --open none # only print the URL (e.g. over SSH)
plan-review threads 42           # open comment threads, as JSON (for Claude)
plan-review reply 42 t-1a2b3c4d "Because ..."   # answer a thread as Claude
```

### `serve`

Run it from the project root. It reads `.claude/work/<issue>/plan.json`, refuses to start if the plan is missing or invalid, and serves the viewer on `127.0.0.1` (never other interfaces) on a free port. It prints `plan-review: issue #42 at http://127.0.0.1:<port>/` and opens your default browser.

`--open browser|none` decides whether the browser opens. Without it, `viewer.open` in the project's `.claude/pipeline.json` decides, and the default is `browser`:

```json
{ "viewer": { "open": "none" } }
```

While it runs:

| Endpoint | What |
|---|---|
| `GET /` | the viewer page |
| `GET /api/plan` | the plan (200); `{"errors": [...]}` with 404 if missing, 422 if invalid |
| `WS /api/updates` | sends `{"type": "plan_changed"}` whenever `plan.json` changes on disk |
| `GET /api/threads` | all comment threads, each with `orphaned: true` if its element left the plan |
| `POST /api/threads` | `{"anchor", "text"}`: new thread, written as the owner (201) |
| `POST /api/threads/<id>/replies` | `{"text"}`: owner reply |
| `POST /api/threads/<id>/resolve`, `/reopen` | close or reopen a thread |

| `POST /api/approve` | approve the plan: 409 while any thread is unresolved, 422 if the plan is invalid; otherwise writes `approved.json` (`approved_at`, `plan_sha256`) |
| `WS /events` | the owner's actions, for Claude (below) |

Errors come back as `{"errors": [...]}`: 404 for an unknown thread, 422 for blank text.

### Events for Claude (`WS /events`)

One JSON message per owner action:

```json
{"type": "comment", "thread_id": "t-1a2b3c4d", "anchor": "class:HintPolicy", "text": "Why a class?"}
{"type": "reply",   "thread_id": "t-1a2b3c4d", "anchor": "class:HintPolicy", "text": "Thanks"}
{"type": "approved"}
```

`comment` is a new thread and `reply` an owner reply in an existing one. Claude's own replies go through the CLI, not the server, so they never produce an event and Claude is never woken by itself.

In Claude Code, subscribe with the `Monitor` tool's WebSocket source. Each message becomes one notification:

```
Monitor({ ws: { url: "ws://127.0.0.1:<port>/events" }, description: "plan-review #42", timeout_ms: 1800000 })
```

A Monitor expires after at most 30 minutes, so re-arm it until `approved` arrives.

### Comment threads

Threads live in `.claude/work/<issue>/comments.json`, next to the plan. Each thread is anchored to a plan element id (such as `class:HintPolicy`) or to a whole tab (`tab:classes`, `tab:flows`, `tab:architecture`, `tab:files`, `tab:tests`, `tab:risks`), and holds ordered messages from `owner` or `claude` plus a `resolved` flag. The page writes as the owner; Claude answers with `plan-review reply`, never by editing the file. A thread whose element disappears from a revised plan is **orphaned**: kept, and shown separately. Tab threads never orphan.

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
