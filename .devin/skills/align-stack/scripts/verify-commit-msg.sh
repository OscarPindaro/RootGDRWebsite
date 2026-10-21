#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 ]]; then
  printf 'Usage: %s [repository-root]\n' "${0##*/}" >&2
  exit 2
fi

target=${1:-.}
repo_root=$(git -C "$target" rev-parse --show-toplevel 2>/dev/null) || {
  printf 'ERROR: not a Git repository: %s\n' "$target" >&2
  exit 2
}
absolute_git_path() {
  local path
  path=$(git -C "$repo_root" rev-parse --git-path "$1")
  [[ "$path" == /* ]] || path="$repo_root/$path"
  printf '%s\n' "$path"
}
config="$repo_root/.pre-commit-config.yaml"
hook=$(absolute_git_path hooks/commit-msg)
[[ -f "$config" ]] || {
  printf 'ERROR: missing pre-commit configuration: %s\n' "$config" >&2
  exit 2
}
[[ -x "$hook" ]] || {
  printf 'ERROR: missing executable commit-msg hook: %s\n' "$hook" >&2
  exit 2
}

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/align-stack-commit-msg.XXXXXX")
trap 'rm -rf "$temp_dir"' EXIT
temp_index="$temp_dir/index"
real_index=$(absolute_git_path index)
if [[ -f "$real_index" ]]; then
  cp "$real_index" "$temp_index"
else
  GIT_INDEX_FILE="$temp_index" git -C "$repo_root" read-tree --empty
fi
GIT_INDEX_FILE="$temp_index" git -C "$repo_root" add --all

invalid_message="$temp_dir/invalid-message"
valid_message="$temp_dir/valid-message"
printf 'invalid message\n' >"$invalid_message"
printf 'chore: verify commit message hook\n' >"$valid_message"

set +e
(
  cd "$repo_root"
  GIT_INDEX_FILE="$temp_index" "$hook" "$invalid_message"
)
invalid_status=$?
set -e
[[ $invalid_status -ne 0 ]] || {
  printf 'ERROR: invalid commit message was accepted\n' >&2
  exit 1
}
printf 'PASS: invalid commit message rejected\n'

(
  cd "$repo_root"
  GIT_INDEX_FILE="$temp_index" "$hook" "$valid_message"
)
printf 'PASS: conventional commit message accepted\n'
