#!/usr/bin/env bash
set -euo pipefail

# Resolve the repository from this script, so setup works from any directory.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

HARNESS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --harness) HARNESS=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

uv sync --dev

VENV_PATH="$REPO_ROOT/.venv"
if [ -z "${VIRTUAL_ENV:-}" ]; then
    source "$VENV_PATH/bin/activate"
fi

uv run pre-commit install

if [ "$HARNESS" = true ]; then
    echo ""
    echo "Installing locked Node dependencies, Playwright Chromium and harness MCP server..."
    npm ci
    uv run harness browsers
    uv run harness install --agent all --yes
fi
