---
name: eval-regression
description: Check Claude Code or Codex skill behavior with bounded evaluations. Devin is not supported by this runner.
argument-hint: "--agent <claude|codex> --model <id> --effort <level> [--base <commit>]"
triggers: [user]
---

# Evaluation regression

Devin is not supported. This runner accepts only Claude Code and Codex; there
is no Devin session, tool-event or transcript adapter. Do not route a case through
Devin CLI or a Devin subagent as a substitute. Plugin feedback can still be
written independently of this runner.

Follow the [development workflow](../using-development-skills/SKILL.md).
Run deterministic repository tests first. If there is no behavioral change,
report that and stop. Read the
[runner requirements and limits](../ai-agent-bench/references/runner-support.md).

## Plan before launching

Resolve the target plugin and its compatible `evals/evals.json` catalog. If the
catalog, required packages or native plugin layout are absent, report the missing
setup. This port does not supply a behavioral catalog for its Devin skills.

The shared runner is [run_evals.py](../ai-agent-bench/scripts/run_evals.py).
Require the user's agent, model and effort choices. Select cases by changed
paths or explicit case identifiers, not the whole catalog by default.
Routing cases apply only to a deliberately tested routing contract; they stop
at the first skill selection and must not execute it.

First run without `--run` to obtain the plan without model sessions. Present
cases, modes, repetitions, session count, timeout, maximum duration, environment
access and cost limits. A prior approval naming this exact run is sufficient;
otherwise ask for approval in plain prose and stop.

## Execute the approved plan

Repeat the same command with `--run` only after approval and permission review.
Defaults are candidate-only, one run per case, 180 seconds per session and at
most four sessions. Report assertion failures, timeouts, nonzero exits, duration
and tokens. Missing evidence is inconclusive.

Compare base and candidate only when requested or needed to distinguish a new
failure from an existing one. Extract the base with `git archive` into a new
temporary location. Use the same cases, model, effort, repetitions and timeouts
on both, then compare reports with `--compare`.

Repeat only a failed or observed unstable case. Selecting all cases, increasing
repetitions, raising session limits or extending timeouts requires an updated
approved plan. Remove only temporary resources this run created, with its
approved cleanup scope. Do not edit or commit the evaluated target.

Prefer checks of tools, ordering, files and outputs over a semantic judge.
Use model-based judging only when those observations cannot express the
requirement, and approve its additional cost separately.
