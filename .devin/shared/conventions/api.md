# API conventions

The HTTP contract, in any language. The [Python](python/index.md) and
[TypeScript](typescript/index.md) conventions own how a service is built; this owns what it
exposes. How far these rules reach on a given task is set by the
[development loop](../development-loop.md)'s Standards gate.

## Shape

REST over HTTP, described by OpenAPI. The schema is generated from the typed models the code
already has, never written by hand beside them — a hand-written schema drifts from the
implementation and nobody notices until a client breaks.

Client code is generated from that description, in CI. A description no generator consumes drifts
away from the real API.

## Versioning

The major version is in the URL: `/v1/...`. Inside a major version only additive change is
allowed — a new optional field, a new endpoint, a new enum value a client may ignore. Anything a
correct client could break on needs a new major.

Adding a required request field, removing or renaming a response field, narrowing a type, or
changing an error's meaning are all breaking, even when the tests still pass.

## Pagination

Cursor pagination for every collection. The response carries an opaque cursor for the next page
and the client sends it back unchanged. Offset pagination skips or repeats rows when the
underlying data changes between requests, which is the normal case for anything users are editing.

## Errors

Errors are RFC 9457 problem documents, served as `application/problem+json` with at least `type`,
`title` and `status`. The `title` is fixed text chosen when the error was defined; an exception
message never becomes the public body.

Python services raise HTTP-agnostic domain errors and let one handler render them. See the
[Python backend conventions](python/backend.md).

## Streaming to a browser

| The need | Use |
|---|---|
| A model's answer arriving word by word | Server-sent events — one long-lived HTTP response the server writes to as it goes |
| A view that refreshes every few seconds | Ask again on a timer, with a conditional request so an unchanged answer costs almost nothing |
| Client and server both genuinely push, unprompted, on one connection | Websockets, under both conditions below |

**Websockets are allowed, not encouraged.** The traffic must genuinely go both ways — a server
pushing while the client only acknowledges is not two-way — and session state must live outside
the server process, so any server can serve any client. Naming the conditions is what stops
websockets being chosen because they sound more capable.

**Serve streams over HTTP/2.** On HTTP/1.1 a browser allows about six connections per address and
every open stream holds one, so two tabs with two streams each stall the rest of the application.

A generation runs **inside the request that streams it** by default — no queue, no store, nothing
extra to operate. It becomes **a background job the client subscribes to** when any of these is
true:

- losing it halfway would mean paying again for model calls already made;
- it runs long enough that a person may navigate away — about thirty seconds is the starting
  point, to be replaced by a real number once there is one;
- it must survive a deploy.

As a job, the process producing tokens is not the one holding the browser connection, so the two
need a channel between them. That channel, storing tokens with ordered ids, is also what makes
resumption and several viewers possible — those are what it buys, not reasons to reach for it. Pick
the channel with the queue question in [async execution](python/async.md), not here.

Every stream message is framed with an event name and a JSON payload. The shared vocabulary is
`text`, `tool`, `progress`, `error` and `done`; anything project-specific carries the project's own
prefix. **A consumer ignores an event type it does not know**, so adding one is not a breaking
change.

## An agent-facing server

Before building one, check that a documented API plus a written skill would not do. A server is
another surface to secure and version, and that cost is only worth paying when an assistant
genuinely needs to reach the data directly.

Such a server speaks the Model Context Protocol (MCP), the open protocol an assistant uses to call
tools and read data without a bespoke integration per assistant.

When it is worth it: access is restricted to our own workspace — the server checks the identity
token and requires a verified address in our own domain before any tool runs. Tools are read-only
by default, and one that changes data needs the delegation rule in the
[auth patterns](python/patterns/auth-patterns.md) plus a recorded audit trail. Record every call: which tool, which source, which query. Keep the tool list
small and obvious — listing the available sources, searching one, and fetching a whole document is
the shape to copy.

## Rate limiting

Every service reachable by something it does not control declares a rate limit, recording the
limit, the window, and the identity it counts against. A service without a declared limit still
has one — it is the point at which it falls over.

Rate-limited responses use `429` with `Retry-After`.
