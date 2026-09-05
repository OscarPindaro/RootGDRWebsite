#!/usr/bin/env bash
set -euo pipefail

HARNESS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --harness) HARNESS=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

uv sync --dev

VENV_PATH=".venv"
if [ -z "${VIRTUAL_ENV:-}" ]; then
    source "$VENV_PATH/bin/activate"
fi

uv run pre-commit install

if [ "$HARNESS" = true ]; then
    echo ""
    echo "Installing Playwright Chromium and harness MCP server..."
    uv run playwright install chromium
    uv run harness install --agent all --yes
fi
