# Engineering

Every design decision and every line of code follows this. It is the counterpart of the [writing contract](writing.md), for code instead of prose, and it holds in any language. Language and framework specifics live in the [Python](conventions/python/index.md) and [TypeScript](conventions/typescript/index.md) conventions; this file never repeats them.

## Derive, don't copy

A copied shape arrives without its premises. It works, but it cannot tell you when it stops being valid, because the reason stayed with whoever you copied it from. Before adopting a structure, ask why it worked there and whether that still holds here.

Name the constraints reality actually imposes. On a real problem there are usually two or three; the rest is furniture. Never remove a constraint you cannot explain — an odd retry or a strange nullable is often the only trace of a bug someone already paid for.

## Model the domain first

Settle the model before choosing a shape for it. Prefer a shape where a wrong state cannot be built over one that checks for it afterwards; a closed set of values beats a free string. Repeated conditionals on the same shape mean a missing model, not a missing branch. A new condition bolted onto an unrelated flow is a design fault, not a detail.

Sharpen a fuzzy term before modelling it: "account" is either the customer or the login, never both. Stress-test a relationship with one concrete awkward case. When the developer's description and the code disagree, say so instead of picking one.

Normalize only to prevent a real update anomaly. Derive a value rather than store it when it cannot drift.

## Design the seam

An interface is everything a caller must know to use something correctly: invariants, ordering, error modes, required configuration, and cost — not only the signature. Prefer a lot of behavior behind a small interface.

- **The deletion test.** Imagine removing the piece. If complexity vanishes, it was a pass-through. If complexity reappears across its callers, it earned its place.
- One implementation behind a seam makes the seam hypothetical; two make it real. Do not introduce one until something varies across it.
- The interface is also the test surface. Needing to reach behind it to test means the shape is wrong.

Give each behavior one owner. Reuse or extract real duplication, but never abstract coincidental similarity, and do not generalize before the third real case.

## Keep the cost honest

Count the concepts a reader must hold to follow the code. A change that leaves that count unchanged relocated complexity instead of reducing it. Prefer deleting an abstraction to polishing it.

Choose the lowest practical time and space cost for the real workload while keeping the code correct and clear, and measure hot paths before adding a complex optimization.

For database work, optimize each statement and its access path, and profile tables, schemas, and queries. Never issue single queries inside a loop when they can be batched. Add an index only for a filter or join that actually exists.

Add a cache, queue, worker, bus, or separate service only for a measured need, and name the threshold that would change the choice.

Remove any line or component whose deletion loses no useful behavior. A refactor must end clearer, more efficient, more reliable, or more maintainable — otherwise it was motion.

## Earn every dependency

Before adding one, check what the language and the frameworks already in the project do today. A capability that once needed a package is often built in now, and that check belongs in the current official documentation, not in memory.

When a dependency is genuinely needed, judge whether it can be relied on: adoption, release cadence, whether it is still maintained, and who stands behind it. A package with little use and no commits for months is a liability no matter who wrote it — say so and offer the maintained alternative or the native way. Every extra dependency is permanent cost: it ages, it breaks, and someone has to update it.

## Name your unknowns

The dangerous gap is not what the developer knows they haven't decided. It is what is so obvious to them that nobody would write it down. The agent does not know it, and fills the gap with the most probable thing rather than the intended one. A gap left to a machine never stays empty, so ask for what is missing instead of guessing.

## Fix the family, not the instance

A defect found in one branch of a check almost always lives in its siblings. When a fix lands,
state the rule it encodes — "each check reads one clause", "quoted text is data" — and walk the
other branches against that rule before calling it done. The same holds for a cheap filter in
front of an expensive one: widening what the slow path recognizes without widening the fast
path silently disables the difference, and every existing case still passes.

## Prove it, and let something else judge

A claim needs a check that could have said no. Ask which states the proof covers and whether the most fragile are among them — a high coverage number answers a different question.

The judge belongs outside what it judges; `staff-review` owns that. A suite you wrote for your own code and nobody attacked from outside is green because no one tried to break it, not because the code is right.

## Write the unit

One responsibility per function or method, no side effects, at most 70 lines. Simple, descriptive names for files, types, functions, variables, and arguments.

## Explain the why, once

Comments carry the non-obvious functional, business, or technical reason, never what the code already says; the [writing contract](writing.md) owns how to word them. Record a decision durably only when it is hard to reverse, would surprise a later reader, and came from a real trade-off.
