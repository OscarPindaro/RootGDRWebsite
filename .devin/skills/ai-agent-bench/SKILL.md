---
name: ai-agent-bench
description: Compare Claude Code and Codex on the same coding task. Devin is not supported by this runner.
argument-hint: "<benchmark configuration and approved run>"
triggers: [user]
---

# AI agent benchmark

Devin is not supported. The runner and transcript parser support only Claude Code
and Codex. Do not substitute Devin CLI, a Devin-hosted model or a subagent and
claim the result is a supported benchmark. Adding that support is separate work.

Follow the [development workflow](../using-development-skills/SKILL.md).
Read the [runner requirements and limits](references/runner-support.md).
Installation does not authorize model sessions, worktrees, commits or cleanup.

## Prepare a comparable run

Use the same task, starting commit, dataset, environment and outcome check for
both agents. Require a clean target repository, available CLIs and a passing
baseline. Do not commit, stash or discard unrelated work to make it clean.

The repository's `.agent-bench.toml` supplies `prompt`, `start_branch` or
`start_commit`, `agents`, `outer_check` and `inner_check`. The outer check verifies
the outcome before and after; the inner check gives the agent focused feedback.
Do not invent a configuration or start a trial when these inputs are missing.

Agree on agents, models, effort, run ID, timeouts, cost limits and exact commands.
Review permission settings and isolate databases, ports, uploads, credentials
and external services as well as worktrees. Worktree separation alone is not
environment isolation. Obtain the repository's required delegation permissions.

## Run only after approval

The runner is [run_trial.py](scripts/run_trial.py). Inspect its help and launch
settings before using it. Run approved trials sequentially to reduce timing
differences from machine load. Do not skip the baseline or final checks to
report success. A returned process status alone does not establish that the
post-check passed.

Results default to `eval-results/<task>/<agent>/run-<id>-<timestamp>/`.
The runner records changes on its own result branch and removes its own trial
worktree. Approve that lifecycle in advance and verify environments are torn
down before removal; do not reuse a path owned by another run.

Record unexpected behavior using the [anomaly format](references/anomalies.md).
Aggregate saved results with [parse_transcript.py](scripts/parse_transcript.py).
Report outcome checks, branches, time, tokens, cost and uncertainty. Never rank
failed trials as successful solutions or present bundled pricing as current
without verification.

For skill behavior rather than a coding task, use the
[evaluation procedure](../eval-regression/SKILL.md). Preserve prior evidence.
Never commit on the user's branch, push, merge results or broaden the run
without approval.
