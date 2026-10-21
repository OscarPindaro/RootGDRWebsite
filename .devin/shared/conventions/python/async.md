# Async execution conventions

Background work, queues, cross-process coordination, and what a service does when a dependency it
calls is failing — including on the request path. [backend](backend.md) owns how a request is
served; this owns the work around it and the behavior when something it depends on is down.

## Choosing the queue

One question decides it: **does this application already run Redis for something else** — cache,
rate limiting, sessions?

- **No.** Use a Postgres-native queue (procrastinate-class). The job is enqueued in the same
  transaction as the data change, so a rolled-back row can never leave a live job behind it, and
  no new service is added to operate.
- **Yes.** Use a Redis-backed queue: ARQ or Dramatiq in Python, BullMQ in TypeScript. Redis is
  already paid for, so the transactional guarantee is traded for throughput knowingly.

Two side cases sit outside that question. When the point is routing — topics, fan-out, priorities
— use a message broker such as RabbitMQ rather than either queue. Above roughly 10,000 jobs per
second, or when the latency budget is single-digit milliseconds, take the Redis-backed option
whichever answer the Redis question gave.

### The ladder above the queue

Each rung is earned, not chosen. A plain queue covers roughly nine background jobs in ten.

| Rung | What it buys | Move up when |
|---|---|---|
| Queue | everything in this file | the default |
| Remembered progress (DBOS, on trial) | each completed step is recorded in the Postgres already running, so a crash resumes instead of restarting | a process has several steps with real side effects, a pause for human approval, or expensive calls that must not be paid for twice. The tool is not settled: prove it on one real batch job before treating it as the default rung |
| A workflow engine (Temporal) | versioning, a UI to watch runs, several languages | only once remembered progress has proved insufficient |
| A streaming log (Kafka) | replay, many independent consumers | on a written trigger only — a real event stream with multiple independent consumers, not a task queue with ambition |

Never choose a rung for a reason the rung below already answers.

## Required in both

- **Idempotency keys.** Every job carries one, and running it twice has the same effect as
  running it once. Retries and at-least-once delivery make duplicates normal, not exceptional.
- **Bounded exponential backoff with jitter.** Unbounded retries turn a dependency's bad minute
  into your outage; retries without jitter synchronize every worker onto the same recovery spike.
- **A retry budget.** A job that has spent its budget stops and goes to the dead-letter queue.
- **A dead-letter queue with an alert on it.** A dead-letter queue nobody is paged for is a place
  where work goes to be forgotten silently.

## When a dependency fails

Classify every third-party dependency as **critical-path** or **enhancing**, and decide the
behavior per class before it fails rather than during:

- **mirror-and-reconcile** — keep our own copy and reconcile later;
- **serve-stale** — answer from the last known good value and say it is stale;
- **feature-off** — the feature disappears cleanly and the rest of the product works.

Degradation is visible and honest to the user. A feature that silently returns worse answers is
worse than one that says it is unavailable.

Never retry an expensive non-idempotent call blindly. Never keep a backup that has never been
restored — an unrestored backup is a belief, not a capability. State per class of system how long
a restore may take and how much data may be lost, and label a system with no backup **rebuildable**
in writing, so that is a decision somebody made rather than something nobody noticed.

Inject faults inside the sealed end-to-end suite — a dependency timing out, returning an error, or
answering slowly — so the degradation paths above are exercised rather than assumed, plus one exercise a year on anything external-facing.

Service level objectives with error budgets belong to cloud-tier services and to the model
gateway — the single path every model call goes through, once one exists.
Everywhere else, golden-signal dashboards without the ceremony; objectives on an internal tool
cost more attention than they return.

## Cross-process coordination

Use PostgreSQL advisory locks for a resource shared across processes, never for isolation inside
one transaction or locking within one process.

Derive the signed-bigint id as `int(sha256(key.encode("utf-8")).hexdigest()[:16], 16) - 2**63`.
Acquire multiple keys in sorted order and keep acquire and release in one async context manager.

- Prefer transaction-scoped `pg_advisory_xact_lock` when the region is one transaction.
- Use a dedicated connection with session locks when the region spans transactions; roll back
  aborted state, then `pg_advisory_unlock_all()`.
- Use `pg_try_advisory_lock[_shared]` to fail fast on contention.

A long-lived PostgreSQL listener that must be active once per logical channel uses a session
advisory lock on the same dedicated connection as `LISTEN`. Standbys release their pool
connection before waiting. Cleanup removes the listener, unlocks, and releases the connection.
This elects one active listener across workers and deployment tasks; it does not make
`LISTEN/NOTIFY` durable or exactly-once.

A connection holding session state must not come from the request pool. See
[backend](backend.md)'s pooling rules.
