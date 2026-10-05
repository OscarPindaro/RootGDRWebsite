# Request metadata

Request documents under `docs/features-request/` carry typed frontmatter so IDs,
dates and links stay stable while the board owns live ticket status.

## What it does

- Frontmatter is exactly `id` (`REQ-nnnn`), `requested_on` (ISO date, or
  `unknown` with `recorded_on` as the first-Git-recording evidence) and
  `title`. Extra fields, including any status field, are rejected.
- `uv run harness backlog check-requests` validates, offline: unique IDs,
  filename agreement, field validity, relative links that resolve, ticket
  references (`REQ-nnnn/Tnn`) to existing requests, known `H1`–`H7` aliases,
  and that a request with a legacy filename is listed in the historical
  inventory.
- `docs/development_processes/legacy-document-inventory.md` catalogues the
  pre-REQ documents with stated or first-Git-recording dates and the retained
  `F1`–`F22` aliases. Nothing there is imported, renamed or renumbered.

## How it is built

`src/harness/backlog/requests.py` holds the Pydantic models, the scanner and
`load_requests()`, which raises a bounded error instead of returning a partly
valid set. The command lives in `src/harness/commands/backlog.py`. The check
reads only repository files: no board token and no network.

## Limits

- It validates identity and links, not that a ticket was completed or a date
  is historically true.
- `F1`–`F22` mentions are not machine-checked: `F2` also names the keyboard
  key in REQ-0003 and REQ-0006.
- The inventory is history, not a board: it is not updated with ticket status.
