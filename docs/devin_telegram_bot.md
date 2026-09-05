# Devin Telegram Bot

The first version is a private, single-repository Telegram bot that runs one non-interactive Devin CLI turn at a time. It uses `python-telegram-bot` with outbound long polling, so the host does not expose a port. Configuration is validated by `pydantic-settings`, and the Telegram token is held as a `SecretStr`.

## Configuration

Set these variables outside the repository:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_ALLOWED_USER_ID="123456789"
export DEVIN_PROJECT_DIR="/absolute/path/to/RootGDRWebsite"
export DEVIN_SANDBOX="true"
export DEVIN_PERMISSION_MODE="auto"
export DEVIN_MODELS="adaptive,gpt,opus,swe"
export DEVIN_DEFAULT_MODEL="adaptive"
```

`DEVIN_EXECUTABLE` optionally selects a non-default Devin executable. Local execution defaults to Devin's sandbox and `auto` permission mode. An unattended service may instead set `DEVIN_SANDBOX=false` and `DEVIN_PERMISSION_MODE=dangerous` only when the entire service is constrained by an OS-level sandbox such as the documented systemd unit. At startup the bot loads the models available to the authenticated account with `devin models list --format json`. `DEVIN_MODELS` is the comma-separated fallback used if discovery fails; `DEVIN_DEFAULT_MODEL` must be one of those fallback values. The configured Telegram user must send messages in a private chat. Other users and group messages are ignored.

Authenticate Devin before starting the bot:

```bash
devin auth login --force-manual-token-flow
devin auth status
```

Install dependencies and run locally with:

```bash
uv sync
uv run devin-telegram-bot
```

The bot starts each new conversation with a sandboxed `devin --print` invocation. Successful later turns use `--continue`, so a Telegram reply can answer a clarifying question. The selected model is passed through `devin --model` on every turn.

Supported commands:

- `/new` makes the next prompt start a new conversation.
- `/model` displays paginated model families and variants from the live account catalog.
- `/model refresh` reloads the catalog from Devin CLI.
- `/status` reports the active model and whether Devin is working.
- `/cancel` terminates the active Devin process.
- `/help` shows the command list.

Only one turn may run at a time. Additional prompts are rejected until it finishes. Conversation and model-selection state is intentionally in memory. Restarting the bot resets the selected model and makes the next prompt start a new conversation.

## Security

Run the service as an unprivileged account. Keep the Telegram token out of Git and restrict the Devin project permissions so secrets, privileged commands, and paths outside the repository remain unavailable. The bot passes prompts as subprocess arguments without a shell. HTTP client logs are suppressed because Telegram API URLs contain the bot token.

The Linux host needs Devin's sandbox prerequisites:

```bash
devin sandbox setup
```

## Planned ACP Upgrade

The subprocess transport is an MVP. It only knows whether Devin is running and receives the final response after each turn.

A later version should replace it with a client for `devin acp`. ACP will provide structured session identifiers, streamed agent messages, tool progress, protocol-level cancellation, and permission requests that can be rendered as Telegram buttons. The Telegram handlers, authorization, model picker, project registry, and service supervision can remain unchanged.

Multiple repositories should be introduced with an explicit allowlist and a separate session and execution lock per repository. Arbitrary Telegram-provided filesystem paths should not be accepted.
