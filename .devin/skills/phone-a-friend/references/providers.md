# Review providers

Check the installed client's help and documentation before constructing commands.
Use an available, user-approved model identifier. Do not assume a CLI name
identifies the underlying model family. Do not change global configuration,
install a provider or weaken permissions to make a review run.

## Devin

The subagent tool selects a profile, not a model. A custom profile can pin
`model:` and restrict `allowed-tools`. Use an existing profile only when its
model and tools meet the approved review scope. An unpinned profile may be
router-selected; it does not establish a cross-family review.

If no suitable profile is available, use a fresh Devin CLI session. The
documented options include `--model`, `--print`, `--prompt-file` and `--config`;
confirm them with the installed `devin --help`. Supply the approved model and
neutral packet, capture output outside the repository, and enforce the agreed
deadline from the calling process. Do not resume the author's session.

Use a temporary, reviewed permission configuration to restrict the reviewer.
Deny edits, patches, shell execution, delegation and external tools outside
the approved access. Allow only the reads needed for the packet and scope.
Account for inherited project settings, hooks and MCP integrations before
starting. Non-interactive mode and the process sandbox alone do not make a
session read-only; the sandbox can still permit workspace writes.

The CLI supports `--resume` for a partner response, but confirm the session ID
and reapply the same model and restrictions. Never use a generic continue option
that could select the author's conversation. Do not bypass workspace trust.

## Claude Code

Use a fresh non-interactive session with the approved model. Check installed help
for model, output, effort, tool restrictions and resume options. Restrict it to
file reads needed for this review. Disable write-capable tools, shell access,
delegation and unrelated MCP services. Do not bypass permission checks.
Capture its session ID for the one response round; preserve restrictions on
resume. A Claude model accessed through Devin can serve the same role when
Claude Code is unavailable, subject to the approved provider choice.

## Codex

Use a fresh non-interactive review with the approved model and a read-only
sandbox. Check installed help for execution, model, effort, output and resume
options. Inspect configured tools and integrations as well as filesystem
restrictions; a read-only filesystem does not prevent external writes.
Preserve restrictions during the response round. A compatible model accessed
through Devin is another option with the user's approval.

## Failure and evidence

Stop on missing credentials, unavailable models, denied tools or inability to
apply the required restrictions. Do not request broader credentials or switch
providers silently. Report the selected model and any returned model metadata;
if actual model identity cannot be confirmed, state that limitation.

This is an agent procedure, not a bundled CLI runner. Validate launch settings
before any model call. Report timeouts, nonzero exits and unavailable usage data;
do not treat partial output or an authentication error as a completed review.
