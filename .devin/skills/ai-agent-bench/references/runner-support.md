# Runner support

Supported runner agents: Claude Code and Codex only.
Devin is not supported: there is no Devin execution adapter, transcript parser
or tool-event mapping. Access to the same model through Devin does not supply
those missing interfaces. Do not infer support from the skill being discoverable.

The source runners, monitor, transcript parser and pricing snapshot are retained.
Local changes remove automatic permission-bypass flags, refuse an existing
benchmark worktree instead of replacing it, and disable evaluation telemetry
export. These changes do not constitute a full runner security audit.

## Prerequisites

The benchmark scripts use Python 3.14 and the standard library.
The behavioral runner additionally needs `pydantic-evals` and Logfire or its
API package. The source environment specifies `pydantic-evals[logfire]==2.9.*`.
Those optional packages are not installed by this port or added to the hosting
application. Check dependencies before attempting even a plan-only invocation;
the behavioral runner imports them at startup.

Use a separately approved environment and dependency setup. Do not install
packages, authenticate clients or access the network automatically.
Confirm native plugin layout and a compatible evaluation catalog before
running cases. This port does not supply a catalog for its Devin skills.

## Execution limits

Inspect current client flags, inherited permissions, hooks, integrations and
credentials before launching. Use an appropriately isolated environment for
coding trials. Non-interactive mode does not itself restrict writes or network
access. If normal permissions prevent a trial from completing, report the
failure rather than bypassing them.

Approve the exact run, branch creation, artifact destinations and cleanup.
Benchmark cleanup removes its trial worktree while preserving the result branch.
Do not let a trial start long-lived environments without an approved teardown
that finishes before cleanup. Never launch against production resources.

Run sequentially with the same checks and comparable machine load. Do not rank
results with failed checks, missing evidence or incompatible test environments.
The bundled pricing file is a dated snapshot, not evidence of current charges.
Report measured usage separately from estimated costs.

Validation of this port covers discovery, local references, script syntax and
agent restrictions. No paid model trials, behavioral evaluations, private
dependencies or telemetry services were exercised.
