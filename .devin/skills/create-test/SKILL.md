---
name: create-test
description: Define or implement behavior-focused regression checks, integration tests, refactor baselines and performance measurements.
argument-hint: "<behavior, file, directory or test strategy>"
triggers: [user]
---

# Create test

Follow the [development workflow](../using-development-skills/SKILL.md) and the
project's testing guide. Establish the user-visible outcome or invariant before
choosing test files or assertions. Strategy and audit requests return findings
without editing.

## Define verification

Identify actors, expected outcomes, behavior that must remain unchanged and any
intentional differences. Cover relevant rejection, permissions, timeout, retry,
concurrency and partial-failure cases. Record environment limits.

Prefer integration tests with the real database and application test client for
database-dependent behavior. Use black-box API, UI, job or CLI tests for complete
workflows. Contract, replay, property and characterization tests address narrower
risks. Unit tests are for pure logic; do not replace integration evidence with
mocks of internal calls. Mock external services where needed for isolation,
cost or reliability, and state which boundary remains unverified.

Use the repository's test harness and isolated environments. Do not start an
ad-hoc application server, alter shared test configuration, or reset another
environment. For runtime or deployment claims, exercise the actual container
and process boundaries where applicable. Avoid leaking test-only settings into
subprocesses meant to represent normal runtime.

Assert outcomes and persisted state. After browser writes, verify the result
through the API or an integration database query; visible DOM text is not proof
of a save. Include project-required desktop and phone checks for UI changes.

## Match the check to the change

For a bug fix or new behavior, observe the relevant regression test fail before
the implementation and pass afterward. Check that the failure reflects the
missing behavior rather than a broken test environment.

For a refactor, capture a characterization baseline that passes on unchanged
code and remains green afterward. Do not break working behavior to force a red
test. If the baseline cannot run, report the blocker before refactoring.

For performance claims, measure the unchanged baseline and the proposed change
with the same tool, environment and workload. Define relevant metrics, datasets,
windows, repetition rules and acceptance limits before measuring. Do not invent
thresholds. Report measurements and variation; an average does not establish a
hard maximum. Profile before adding complex optimizations.

## Run and report

Implement the smallest useful checks within the authorized scope. Run focused
tests, then relevant broader suites. Do not remove, weaken, skip or rebaseline
checks without explicit approval. Report commands, results, pre-existing
failures and what the evidence does not establish.
