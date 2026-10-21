# Product events, flags and runtime settings

Language-neutral. These rules hold wherever the code runs, because an event emitted by a backend
and one emitted by a browser land in the same stream, and a flag gates both.

## The event schema

The schema is the lasting asset and does not depend on the analytics vendor. Every event carries
the same required fields wherever it is emitted: **company, product, feature, and who acted —
including when that is an automation**, so agent actions and human actions share one stream.

Changes to the schema are reviewed like an API change, under one named owner.

**An event recording that someone adopted a feature ships with a paired event recording the
outcome.** Pairing them in the schema is what stops adoption being reported as success on its own,
and it is what decides a rollout.

## Where a runtime setting belongs

Four homes, which pre-answers the argument:

| The value | Its home |
|---|---|
| Structural — a database address, a queue name | Deploy-time configuration |
| Exposure, an emergency switch, an experiment | A feature flag |
| An operational value a non-engineer adjusts | Admin settings |
| Prompt text | Managed prompts |

## Flags

Flags are reached through **OpenFeature**, a vendor-neutral interface, so the platform behind it
stays replaceable even though the platform is decided.

**Flag hygiene is a rule, not a hope.** Every flag gets an owner and an expiry date when it is
created, expired flags fail the build, and a flag used for a rollout is deleted once the rollout
finishes. Only genuine emergency switches and long-lived entitlement gates persist.

For a model-backed feature, **only one thing varies at a time** — the prompt version, or the
model, or a flag. Never all three on one screen, because nothing can then be attributed.
