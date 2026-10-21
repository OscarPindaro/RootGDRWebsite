---
name: refactor
description: Audit maintenance problems read-only, then implement selected improvements in bounded, verified batches.
argument-hint: "[area, directory or maintenance goal]"
triggers: [user]
---

# Refactor

Follow the [development workflow](../using-development-skills/SKILL.md). With a
focus, inspect that area and its relevant dependencies; otherwise inspect the
project. Exclude generated code, vendored content and dependencies.

## Audit without editing

Read project standards and existing architecture. Inspect data models, ownership,
API boundaries, access control, query batching and indexes, retries, resource
lifetime and behavior with concurrent processes. Include tests, documentation,
UI and deployment configuration where relevant to the scope.

Use available specialized checks only with the required permissions. Do not
depend on uninstalled plugins or launch agents without approval. Verify claims
about incorrect library usage against installed-version documentation.

Report each finding with its location, evidence, impact, effort, dependencies,
uncertainty, change risk and required verification. Distinguish severity from
implementation priority. Put security and data-loss risks first; then consider
impact, effort and how often the affected code changes. Group shared root causes.
Keep speculative improvements separate from demonstrated defects.

## Select work

Present findings and recommend bounded batches. Ask in plain prose which work
to pursue. Selecting none ends the audit. Do not write files during an audit
unless the user asks to save the report.

Each batch has one scope, compatible dependencies and a verification and recovery
strategy. Use the repository's existing planning and tracking conventions.

## Implement approved batches

Resolve material design questions using the
[brainstorming playbook](../brainstorming/SKILL.md). Establish invariants and a
passing characterization baseline with the [testing playbook](../create-test/SKILL.md)
before changing behavior-preserving code.

An already specified implementation batch can proceed under the development
workflow's ticket rule. Otherwise obtain approval for its plan. Work in small
slices and run the nearest check after each. Finish cumulative verification and
review before starting a dependent batch; stop on failed checks.

Keep behavior changes and new findings outside the approved batch. Record them
for a separate decision rather than widening the refactor. Preserve remaining
findings and enough context to resume without repeating the audit. Follow the
repository's commit rules.
