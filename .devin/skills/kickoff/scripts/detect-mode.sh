#!/usr/bin/env bash
# Inspect a target without creating or modifying it.
set -euo pipefail

if [[ $# -gt 1 ]]; then
    printf 'Usage: %s [target-directory]\n' "${0##*/}" >&2
    exit 2
fi

target=${1:-$PWD}
if [[ -L "$target" || ( -e "$target" && ! -d "$target" ) ]]; then
    printf 'Target must be a directory, not a file or symlink.\n' >&2
    exit 2
fi
if [[ ! -e "$target" ]]; then
    printf 'missing\n'
    exit 0
fi
if [[ -f "$target/.kickoff-project" ]]; then
    printf 'kickoff\n'
    exit 0
fi

for marker in pyproject.toml uv.lock setup.py setup.cfg requirements.txt \
    requirements.in package.json go.mod pom.xml build.gradle build.gradle.kts \
    Cargo.toml Gemfile composer.json docker-compose.yml docker-compose.yaml .git; do
    if [[ -e "$target/$marker" || -L "$target/$marker" ]]; then
        printf 'existing\n'
        exit 0
    fi
done
if [[ -d "$target/src/backend" || -d "$target/backend/app" ]]; then
    printf 'existing\n'
    exit 0
fi

shopt -s nullglob dotglob
for entry in "$target"/*; do
    case "${entry##*/}" in
        README*|LICENSE*|CHANGELOG*|COPYING*|NOTICE*|AUTHORS*|.gitignore|.editorconfig)
            continue ;;
        *)
            printf 'nonproject\n'
            exit 0 ;;
    esac
done
printf 'empty\n'
