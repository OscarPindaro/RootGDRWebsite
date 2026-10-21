---
name: kickoff
description: Start an approved project using the feature-module and JinjaX/htmx workflow, or route an existing project to a scoped audit.
argument-hint: "[new project name/path or existing-project focus]"
triggers: [user]
---

# Kickoff

Follow the [development workflow](../using-development-skills/SKILL.md).
Read applicable project instructions and preserve unrelated work. Installation
does not authorize creating a project, installing dependencies or refactoring
the current repository.

## Resolve the target

Distinguish a new-project request from work on an existing project. A name does
not automatically authorize creating a nested project in the current checkout.
Confirm the intended absolute destination and inspect its parent before writing.

Use [detect-mode.sh](scripts/detect-mode.sh) with the resolved target. It only
reports the directory's state:

- `missing`: propose creation under the verified parent; create nothing yet.
- `empty`: a new starter can be planned, preserving existing documentation.
- `existing`: follow [kickoff-fix](../kickoff-fix/SKILL.md) with the requested focus.
- `nonproject`: ask whether to use a new subdirectory or inspect the contents.
- `kickoff`: a legacy marker exists; inspect the unfinished work and ask whether
  to resume or audit it. Do not delete the marker or call an unavailable guide.

Invalid files or symlink targets are refused. Do not overwrite an existing
project or remove contents to make a directory appear empty.

## Agree on the first version

Discover facts before asking. Resolve purpose, users, the first useful flow,
scope, UI need, integrations, data/privacy constraints and hosting needs.
Ask in plain prose, one consequential decision at a time.
Do not force a cloud/platform choice or provision infrastructure during kickoff.

Use [brainstorming](../brainstorming/SKILL.md) for unresolved decisions and the
[project recipe](references/project-recipe.md) for technology and verification.
Preserve a sufficiently specified approved ticket instead of reopening its
decisions. Otherwise obtain approval for the resulting plan before generation.

## Build and verify

Create the smallest approved foundation, then one tested feature layer at a
time. This port supplies a guided procedure, not an automatic scaffold generator
or a template that imports the application's domain data.

Use FastAPI, Pydantic, PostgreSQL, typed SQLAlchemy models and Alembic. When a web
UI is needed, use JinjaX and htmx. Do not substitute React/Next.js, introduce
private company dependencies or call missing auth/setup skills.

Establish the approved test harness and isolation before runtime verification.
Verify persisted behavior through the API/database and inspect desktop/phone
results where applicable. A booting starter is not a verified product flow.
Update the repository's documentation and make the required scoped local
commits after verification. Do not push, deploy, choose a release version or
create external tickets without separate authority.
