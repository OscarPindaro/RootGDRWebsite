#!/usr/bin/env bash
set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/preflight-python.sh"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

assert_contains() {
  local output=$1 expected=$2
  [[ "$output" == *"$expected"* ]] || {
    printf 'Expected output to contain: %s\nActual output:\n%s\n' "$expected" "$output" >&2
    exit 1
  }
}

assert_not_contains() {
  local output=$1 unexpected=$2
  [[ "$output" != *"$unexpected"* ]] || {
    printf 'Expected output to NOT contain: %s\nActual output:\n%s\n' "$unexpected" "$output" >&2
    exit 1
  }
}

move_uv_repo_after_local() {
  local file=$1
  awk '
    function save_block() {
      if (block == "") return
      blocks[++count] = block
      if (block ~ /astral-sh\/uv-pre-commit/) uv_index = count
      if (!local_index && block ~ /^  - repo: local/) local_index = count
      block = ""
    }
    !seen_repo && !/^  - repo:/ {
      preamble = preamble $0 ORS
      next
    }
    /^  - repo:/ {
      seen_repo = 1
      save_block()
    }
    { block = block $0 ORS }
    END {
      save_block()
      printf "%s", preamble
      for (i = 1; i <= count; i++) {
        if (i == uv_index) continue
        printf "%s", blocks[i]
        if (i == local_index) printf "%s", blocks[uv_index]
      }
    }
  ' "$file" >"$file.tmp"
  mv "$file.tmp" "$file"
}

assert_preflight_rejected() {
  local project=$1 expected=$2 description=$3 output status
  set +e
  output=$($SCRIPT "$project" 2>&1)
  status=$?
  set -e
  [[ $status -eq 1 ]] || {
    printf 'Expected %s to exit 1, got %s\n%s\n' "$description" "$status" "$output" >&2
    exit 1
  }
  assert_contains "$output" "$expected"
}

create_parity_project() {
  local project=$1
  mkdir -p "$project/app"/{api,model,repository,service} "$project/.github/workflows"
  local layer
  for layer in api model repository service; do
    printf '' >"$project/app/$layer/__init__.py"
  done

  # The fixture must satisfy the conventions it is graded against. The tier line became a
  # preflight invariant without this fixture gaining one, so every run failed on the check
  # rather than on the project.
  cat >"$project/README.md" <<'EOF'
# parity-service

Hosting tier: velocity
EOF

  cat >"$project/pyproject.toml" <<'EOF'
[project]
name = "parity-service"
version = "0.0.1"
requires-python = ">=3.14,<3.15"
dependencies = ["fastapi==0.135.*", "gunicorn==26.0.*"]

[dependency-groups]
dev = [
  "commitizen==4.*",
  "import-linter==2.*",
  "mypy==1.*",
  "pip-audit==2.*",
  "pre-commit==4.*",
  "pytest==9.*",
  "pytest-cov==7.*",
  "pytest-randomly==3.*",
  "ruff==0.*",
]

[tool.uv]
package = false

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = [
  "E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "ASYNC", "S",
  "DTZ", "PT", "LOG", "G", "RET", "PTH", "TID", "FAST", "RUF", "PL",
]
ignore = ["E501"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends"]

[tool.mypy]
python_version = "3.14"
plugins = ["pydantic.mypy"]
warn_unused_ignores = true
warn_redundant_casts = true

[[tool.mypy.overrides]]
module = ["app.model.*"]
disallow_untyped_defs = true

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true

[tool.importlinter]
root_package = "app"
exclude_type_checking_imports = true

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = ["app.api", "app.service", "app.repository", "app.model"]

[tool.commitizen]
version_provider = "pep621"
tag_format = "$version"
update_changelog_on_bump = true
annotated_tag = true

[tool.pytest.ini_options]
addopts = "-ra -q -m 'not live'"
testpaths = ["tests"]
markers = [
    "live: integration tests that need a real external resource",
]
EOF

  cat >"$project/uv.lock" <<'EOF'
version = 1
revision = 3
requires-python = "==3.14.*"

[[package]]
name = "fastapi"
version = "0.135.0"
source = { registry = "https://pypi.org/simple" }
EOF
  printf '3.14\n' >"$project/.python-version"

  cat >"$project/Makefile" <<'EOF'
.DEFAULT_GOAL := help
.PHONY: help install lock upgrade test lint cov audit run bump push-tag clean docker-build docker-run docker-test
help:  ## List available targets
	@grep -E '^[a-z][a-z0-9-]*:.*##' $(MAKEFILE_LIST)
install: uv.lock  ## Install locked dev environment and hooks
	uv sync --locked
	uv run pre-commit install
uv.lock: pyproject.toml
	uv lock
lock: uv.lock  ## Resolve lockfile
upgrade:  ## Upgrade dependencies
	uv lock --upgrade
test:  ## Run tests
	uv run pytest tests/ -x -q
lint:  ## Run quality gates
	uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run mypy app
cov:  ## Run coverage
	uv run pytest --cov=app
audit:  ## Audit dependencies
	uv export --format requirements-txt | uv run pip-audit --no-deps -r /dev/stdin
run:  ## Run service
	uv run gunicorn app.main:app
bump:  ## Bump version
	uv run cz bump
push-tag:  ## Push version tag
	git push --follow-tags origin main
clean:  ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} \;
docker-build:  ## Build image
	docker build --target api .
docker-run:  ## Run image
	docker run parity-service
docker-test:  ## Run Docker gates
	docker buildx bake test
EOF

  cat >"$project/.pre-commit-config.yaml" <<'EOF'
default_install_hook_types: [pre-commit, commit-msg]
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-toml
      - id: check-yaml
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ["--maxkb=1024"]
        exclude: ^uv\.lock$
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.11.28
    hooks:
      - id: uv-lock
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run --frozen ruff check --fix --force-exclude
        language: unsupported
        types_or: [python, pyi]
        require_serial: true
      - id: ruff-format
        name: ruff format
        entry: uv run --frozen ruff format --force-exclude
        language: unsupported
        types_or: [python, pyi]
        require_serial: true
      - id: import-linter
        entry: uv run --frozen lint-imports
        language: unsupported
        pass_filenames: false
      - id: mypy
        entry: uv run --frozen mypy app
        language: unsupported
        pass_filenames: false
  - repo: https://github.com/zizmorcore/zizmor-pre-commit
    rev: v1.28.0
    hooks:
      - id: zizmor
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.9.1
    hooks:
      - id: commitizen
        stages: [commit-msg]
EOF

  cat >"$project/Dockerfile" <<'EOF'
FROM ghcr.io/astral-sh/uv:0.11.28@sha256:0000000000000000000000000000000000000000000000000000000000000001 AS uv
FROM python:3.14-slim@sha256:0000000000000000000000000000000000000000000000000000000000000002 AS base
COPY --from=uv /uv /uvx /usr/local/bin/
ENV VIRTUAL_ENV=/app/.venv
FROM base AS runtime-deps
RUN uv sync --locked --no-dev --no-install-project
FROM runtime-deps AS dev-deps
RUN uv sync --locked --all-groups --no-install-project
FROM dev-deps AS lint
ARG RUN_LINT_IN_BUILD=1
# pip-audit and zizmor live in the lint stage, not only in CI: when a project runs its checks
# through Bake, the Dockerfile is the only place the security gate can be reached.
RUN if [ "$RUN_LINT_IN_BUILD" = "1" ]; then ruff check . && ruff format --check . && lint-imports && mypy app && pip-audit && zizmor .github/workflows; fi
CMD ["sh", "-c", "ruff check . && ruff format --check . && lint-imports && mypy app && pip-audit && zizmor .github/workflows"]
FROM dev-deps AS test
COPY . .
ARG RUN_TESTS_IN_BUILD=1
RUN if [ "$RUN_TESTS_IN_BUILD" = "1" ]; then python -m pytest --cov=app tests; fi
CMD ["python", "-m", "pytest", "--cov=app", "tests"]
FROM base AS api
COPY --from=runtime-deps /app/.venv /app/.venv
EOF

  cat >"$project/.dockerignore" <<'EOF'
.venv
.coverage
__pycache__
EOF

  cat >"$project/.github/dependabot.yml" <<'EOF'
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    versioning-strategy: lockfile-only
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      python-deps:
        patterns: ["*"]
  - package-ecosystem: docker
    directory: /
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    ignore:
      - dependency-name: "python"
        update-types:
          - "version-update:semver-minor"
          - "version-update:semver-major"
EOF

  cat >"$project/.github/workflows/check.yml" <<'EOF'
name: Check
on:
  push:
    branches: ["**"]
jobs:
  check:
    uses: example-org/shared-github-actions/.github/workflows/check-python.yml@main
    with:
      test_command: "pytest --cov=app tests"
      lint_command: "ruff check . && ruff format --check . && lint-imports && mypy app"
      build_args: |
        RUN_TESTS_IN_BUILD=0
        RUN_LINT_IN_BUILD=0
EOF
}

create_library_parity_project() {
  local project=$1
  mkdir -p "$project/mylib/http" "$project/.github/workflows"
  printf '' >"$project/mylib/__init__.py"
  printf '' >"$project/mylib/http/__init__.py"
  printf '' >"$project/mylib/py.typed"

  cat >"$project/pyproject.toml" <<'EOF'
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mylib"
version = "1.2.3"
requires-python = ">=3.11"
dependencies = ["httpx>=0.27"]

[project.optional-dependencies]
extra = ["pydantic>=2.0"]

[dependency-groups]
dev = [
  "commitizen==4.*",
  "mypy==1.*",
  "pip-audit==2.*",
  "pre-commit==4.*",
  "pytest==9.*",
  "pytest-cov==7.*",
  "pytest-randomly==3.*",
  "ruff==0.*",
]

[tool.hatch.build.targets.wheel]
packages = ["mylib"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = [
  "E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "ASYNC", "S",
  "DTZ", "PT", "LOG", "G", "RET", "PTH", "TID", "FAST", "RUF", "PL",
]
ignore = ["E501"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends"]

[tool.mypy]
python_version = "3.14"
plugins = ["pydantic.mypy"]
warn_unused_ignores = true
warn_redundant_casts = true

[[tool.mypy.overrides]]
module = ["mylib.http.*"]
disallow_untyped_defs = true

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true

[tool.commitizen]
version_provider = "pep621"
tag_format = "$version"
update_changelog_on_bump = true
annotated_tag = true

[tool.pytest.ini_options]
addopts = "-ra -q -m 'not live'"
testpaths = ["tests"]
markers = [
    "live: integration tests that need a real external resource",
]
EOF

  cat >"$project/uv.lock" <<'EOF'
version = 1
revision = 3
requires-python = ">=3.11"

[[package]]
name = "httpx"
version = "0.27.0"
source = { registry = "https://pypi.org/simple" }
EOF
  printf '3.14\n' >"$project/.python-version"

  # A library's Makefile omits the service-only run/docker-build targets.
  cat >"$project/Makefile" <<'EOF'
.DEFAULT_GOAL := help
.PHONY: help install lock upgrade test lint cov audit bump push-tag clean
help:  ## List available targets
	@grep -E '^[a-z][a-z0-9-]*:.*##' $(MAKEFILE_LIST)
install: uv.lock  ## Install locked dev environment and hooks
	uv sync --locked --all-extras
	uv run pre-commit install
uv.lock: pyproject.toml
	uv lock
lock: uv.lock  ## Resolve lockfile
upgrade:  ## Upgrade dependencies
	uv lock --upgrade
test:  ## Run tests
	uv run --frozen pytest tests/ -x -q
lint:  ## Run quality gates
	uv run ruff check . && uv run ruff format --check . && uv run mypy mylib
cov:  ## Run coverage
	uv run pytest --cov=mylib
audit:  ## Audit dependencies
	uv export --format requirements-txt | uv run pip-audit --no-deps -r /dev/stdin
bump:  ## Bump version
	uv run cz bump
push-tag:  ## Push version tag
	git push --follow-tags origin main
clean:  ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} \;
EOF

  # A library uses the current `ruff-check` hook id (not the legacy `ruff` alias)
  # and has no import-linter hook (no layered architecture).
  cat >"$project/.pre-commit-config.yaml" <<'EOF'
default_install_hook_types: [pre-commit, commit-msg]
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-toml
      - id: check-yaml
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ["--maxkb=1024"]
        exclude: ^uv\.lock$
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.11.28
    hooks:
      - id: uv-lock
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run --frozen ruff check --fix --force-exclude
        language: unsupported
        types_or: [python, pyi]
        require_serial: true
      - id: ruff-format
        name: ruff format
        entry: uv run --frozen ruff format --force-exclude
        language: unsupported
        types_or: [python, pyi]
        require_serial: true
      - id: mypy
        entry: uv run --frozen mypy mylib
        language: unsupported
        pass_filenames: false
  - repo: https://github.com/zizmorcore/zizmor-pre-commit
    rev: v1.28.0
    hooks:
      - id: zizmor
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.9.1
    hooks:
      - id: commitizen
        stages: [commit-msg]
EOF

  # Docker Dependabot is not required for a library (it ships no image).
  cat >"$project/.github/dependabot.yml" <<'EOF'
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    versioning-strategy: lockfile-only
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      python-deps:
        patterns: ["*"]
EOF

  cat >"$project/.github/workflows/check.yml" <<'EOF'
name: Check
on:
  push:
    branches: ['**']
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: uv run --frozen ruff check .
      - run: uv run --frozen ruff format --check .
      - run: uv run --frozen mypy mylib
      # The security gate became a preflight invariant after this fixture was written.
      # A library owes it too: it has dependencies to audit and workflows to scan.
      - run: uv export --format requirements-txt | uv run pip-audit --no-deps -r /dev/stdin
      - run: uv run --frozen pre-commit run zizmor --all-files
      - run: uv run --frozen pytest --cov=mylib tests
EOF
}

[[ -x "$SCRIPT" ]] || {
  printf 'Missing executable preflight: %s\n' "$SCRIPT" >&2
  exit 1
}

parity="$TMP_DIR/parity"
create_parity_project "$parity"
# E6 decided that nothing fails on the coverage number. The baseline project therefore measures
# coverage and sets no floor anywhere, and it must pass. Asserted with its own message because
# `set -e` would otherwise kill the run silently and report nothing about coverage.
grep -rq -- '--cov-fail-under' "$parity" && {
  printf 'The baseline fixture must carry no coverage floor; one was found.\n' >&2
  exit 1
}
set +e
parity_output=$($SCRIPT "$parity" 2>&1)
parity_status=$?
set -e
[[ $parity_status -eq 0 ]] || {
  printf 'Expected the no-coverage-floor baseline to exit 0, got %s\n%s\n' "$parity_status" "$parity_output" >&2
  exit 1
}
assert_contains "$parity_output" "PASS: PEP 621 project and dependency groups"
assert_contains "$parity_output" "PASS: layered import contract"
assert_contains "$parity_output" "PASS: Docker Python patch-only updates"
assert_contains "$parity_output" "VERDICT: PARITY"

missing_python_ignore="$TMP_DIR/missing-python-ignore"
cp -R "$parity" "$missing_python_ignore"
sed '/^[[:space:]]*ignore:/,$d' "$parity/.github/dependabot.yml" \
  >"$missing_python_ignore/.github/dependabot.yml"
assert_preflight_rejected \
  "$missing_python_ignore" \
  "FAIL: Docker Python patch-only updates" \
  "Docker updater without the Python rule"

commented_python_types="$TMP_DIR/commented-python-types"
cp -R "$parity" "$commented_python_types"
sed '/version-update:semver-/s/^[[:space:]]*/          # /' \
  "$parity/.github/dependabot.yml" >"$commented_python_types/.github/dependabot.yml"
assert_preflight_rejected \
  "$commented_python_types" \
  "FAIL: Docker Python patch-only updates" \
  "commented Python update types"

blocked_python_patch="$TMP_DIR/blocked-python-patch"
cp -R "$parity" "$blocked_python_patch"
sed '/version-update:semver-major/a\
          - "version-update:semver-patch"' "$parity/.github/dependabot.yml" \
  >"$blocked_python_patch/.github/dependabot.yml"
assert_preflight_rejected \
  "$blocked_python_patch" \
  "FAIL: Docker Python patch-only updates" \
  "Python rule that blocks patch updates"

docker_allow_list="$TMP_DIR/docker-allow-list"
cp -R "$parity" "$docker_allow_list"
sed '/version-update:semver-major/a\
    allow:\
      - dependency-name: "ghcr.io/astral-sh/uv"' "$parity/.github/dependabot.yml" \
  >"$docker_allow_list/.github/dependabot.yml"
assert_preflight_rejected \
  "$docker_allow_list" \
  "FAIL: Docker Python patch-only updates" \
  "Docker allow list"

# A Dependabot multi-ecosystem group may own the Docker update schedule.
multi_ecosystem_updates="$TMP_DIR/multi-ecosystem-updates"
cp -R "$parity" "$multi_ecosystem_updates"
cat >"$multi_ecosystem_updates/.github/dependabot.yml" <<'EOF'
version: 2
multi-ecosystem-groups:
  uv-toolchain:
    schedule:
      interval: weekly
updates:
  - package-ecosystem: uv
    directory: /
    versioning-strategy: lockfile-only
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      python-deps:
        patterns: ["*"]
  - package-ecosystem: docker
    directory: /
    patterns: ["*"]
    multi-ecosystem-group: uv-toolchain
    cooldown:
      default-days: 7
    ignore:
      - dependency-name: "python"
        update-types:
          - "version-update:semver-minor"
          - "version-update:semver-major"
  - package-ecosystem: pre-commit
    directory: /
    patterns: ["astral-sh/uv-pre-commit"]
    multi-ecosystem-group: uv-toolchain
    cooldown:
      default-days: 7
EOF
multi_ecosystem_output=$($SCRIPT "$multi_ecosystem_updates")
assert_contains "$multi_ecosystem_output" "PASS: immutable Docker bases and update path"
assert_contains "$multi_ecosystem_output" "PASS: Docker Python patch-only updates"
assert_contains "$multi_ecosystem_output" "VERDICT: PARITY"

grouped_without_patterns="$TMP_DIR/grouped-without-patterns"
cp -R "$multi_ecosystem_updates" "$grouped_without_patterns"
sed '/package-ecosystem: docker/,/package-ecosystem: pre-commit/{ /patterns:/d; }' \
  "$multi_ecosystem_updates/.github/dependabot.yml" \
  >"$grouped_without_patterns/.github/dependabot.yml"
assert_preflight_rejected \
  "$grouped_without_patterns" \
  "FAIL: Docker Python patch-only updates" \
  "grouped Docker updater without patterns"

narrow_docker_patterns="$TMP_DIR/narrow-docker-patterns"
cp -R "$multi_ecosystem_updates" "$narrow_docker_patterns"
sed 's/patterns: \["\*"\]/patterns: ["astral-sh\/uv"]/' \
  "$multi_ecosystem_updates/.github/dependabot.yml" \
  >"$narrow_docker_patterns/.github/dependabot.yml"
assert_preflight_rejected \
  "$narrow_docker_patterns" \
  "FAIL: Docker Python patch-only updates" \
  "Docker updater patterns that exclude Python"

missing_cooldown="$TMP_DIR/missing-cooldown"
cp -R "$parity" "$missing_cooldown"
cat >"$missing_cooldown/.github/dependabot.yml" <<'EOF'
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    versioning-strategy: lockfile-only
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      python-deps:
        patterns: ["*"]
  - package-ecosystem: docker
    directory: /
    schedule:
      interval: weekly
EOF
set +e
missing_cooldown_output=$($SCRIPT "$missing_cooldown" 2>&1)
missing_cooldown_status=$?
set -e
[[ $missing_cooldown_status -eq 1 ]] || {
  printf 'Expected missing Dependabot cooldown to exit 1, got %s\n%s\n' \
    "$missing_cooldown_status" "$missing_cooldown_output" >&2
  exit 1
}
assert_contains "$missing_cooldown_output" "FAIL: Dependabot update cooldowns"

short_cooldown="$TMP_DIR/short-cooldown"
cp -R "$parity" "$short_cooldown"
sed -i.bak 's/default-days: 7/default-days: 6/g' "$short_cooldown/.github/dependabot.yml"
rm "$short_cooldown/.github/dependabot.yml.bak"
set +e
short_cooldown_output=$($SCRIPT "$short_cooldown" 2>&1)
short_cooldown_status=$?
set -e
[[ $short_cooldown_status -eq 1 ]] || {
  printf 'Expected short Dependabot cooldown to exit 1, got %s\n%s\n' \
    "$short_cooldown_status" "$short_cooldown_output" >&2
  exit 1
}
assert_contains "$short_cooldown_output" "FAIL: Dependabot update cooldowns"

misplaced_cooldown="$TMP_DIR/misplaced-cooldown"
cp -R "$parity" "$misplaced_cooldown"
cat >"$misplaced_cooldown/.github/dependabot.yml" <<'EOF'
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    versioning-strategy: lockfile-only
    schedule:
      interval: weekly
      cooldown:
        default-days: 7
    groups:
      python-deps:
        patterns: ["*"]
  - package-ecosystem: docker
    directory: /
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
EOF
set +e
misplaced_cooldown_output=$($SCRIPT "$misplaced_cooldown" 2>&1)
misplaced_cooldown_status=$?
set -e
[[ $misplaced_cooldown_status -eq 1 ]] || {
  printf 'Expected nested Dependabot cooldown to exit 1, got %s\n%s\n' \
    "$misplaced_cooldown_status" "$misplaced_cooldown_output" >&2
  exit 1
}
assert_contains "$misplaced_cooldown_output" "FAIL: Dependabot update cooldowns"

# --- Library mode -----------------------------------------------------------
# A pure-Python library (a [build-system], no Dockerfile, not package=false)
# reaches PARITY: the service-only Docker invariants become N/A, the Python floor
# is a range, and run/docker-build are not required.
library="$TMP_DIR/library"
create_library_parity_project "$library"
library_output=$($SCRIPT "$library")
assert_contains "$library_output" "PASS: PEP 621 project and dependency groups"
assert_contains "$library_output" "PASS: uv lockfile and Python 3.14 pin"
assert_contains "$library_output" "PASS: quality dependencies and tool configuration"
assert_contains "$library_output" "PASS: minimal self-documented Makefile command surface"
assert_contains "$library_output" "PASS: pre-commit quality chain"
assert_contains "$library_output" "PASS: native Python CI contract"
assert_contains "$library_output" "N/A: uv-native Docker dependency and quality stages (library: ships no container)"
assert_contains "$library_output" "N/A: immutable Docker bases and update path (library: ships no container)"
assert_contains "$library_output" "N/A: Docker Python patch-only updates (library: ships no container)"
assert_contains "$library_output" "N/A: Docker and pre-commit uv versions match (library: ships no container)"
assert_contains "$library_output" "VERDICT: PARITY"

# A [build-system]-less project is not a library: it is classified as a service,
# which then demands package=false / a Dockerfile and diverges.
library_no_build_system="$TMP_DIR/library-no-build-system"
cp -R "$library" "$library_no_build_system"
awk '
  /^\[build-system\]$/ { skip = 1; next }
  skip && /^\[/ { skip = 0 }
  !skip { print }
' "$library_no_build_system/pyproject.toml" >"$library_no_build_system/pyproject.toml.tmp"
mv "$library_no_build_system/pyproject.toml.tmp" "$library_no_build_system/pyproject.toml"
set +e
library_no_build_output=$($SCRIPT "$library_no_build_system" 2>&1)
library_no_build_status=$?
set -e
[[ $library_no_build_status -eq 1 ]] || {
  printf 'Expected build-system-less library to exit 1, got %s\n%s\n' "$library_no_build_status" "$library_no_build_output" >&2
  exit 1
}
assert_contains "$library_no_build_output" "FAIL: PEP 621 project and dependency groups"

# package=false marks a service: a library that sets it (with no Dockerfile) diverges.
library_package_false="$TMP_DIR/library-package-false"
cp -R "$library" "$library_package_false"
cat >>"$library_package_false/pyproject.toml" <<'EOF'

[tool.uv]
package = false
EOF
set +e
library_pf_output=$($SCRIPT "$library_package_false" 2>&1)
library_pf_status=$?
set -e
[[ $library_pf_status -eq 1 ]] || {
  printf 'Expected package=false library to exit 1, got %s\n%s\n' "$library_pf_status" "$library_pf_output" >&2
  exit 1
}
assert_contains "$library_pf_output" "VERDICT: DIVERGENT"

# Explicit `fail_fast: false` is equivalent to the default and remains valid.
explicit_fail_fast_false="$TMP_DIR/explicit-fail-fast-false"
cp -R "$parity" "$explicit_fail_fast_false"
{
  printf 'fail_fast: false\n'
  cat "$explicit_fail_fast_false/.pre-commit-config.yaml"
} >"$explicit_fail_fast_false/.pre-commit-config.yaml.tmp"
mv "$explicit_fail_fast_false/.pre-commit-config.yaml.tmp" "$explicit_fail_fast_false/.pre-commit-config.yaml"
explicit_fail_fast_false_output=$($SCRIPT "$explicit_fail_fast_false")
assert_contains "$explicit_fail_fast_false_output" "PASS: pre-commit quality chain"
assert_contains "$explicit_fail_fast_false_output" "VERDICT: PARITY"
# ----------------------------------------------------------------------------

alternate_dev_pins="$TMP_DIR/alternate-dev-pins"
cp -R "$parity" "$alternate_dev_pins"
awk '
  /^dev = \[/ { in_dev = 1 }
  in_dev { gsub(/==[0-9]+\.\*/, ">=0") }
  { print }
  in_dev && /^\]/ { in_dev = 0 }
' "$alternate_dev_pins/pyproject.toml" >"$alternate_dev_pins/pyproject.toml.tmp"
mv "$alternate_dev_pins/pyproject.toml.tmp" "$alternate_dev_pins/pyproject.toml"
alternate_dev_output=$($SCRIPT "$alternate_dev_pins")
assert_contains "$alternate_dev_output" "VERDICT: PARITY"

bare_runtime_dependency="$TMP_DIR/bare-runtime-dependency"
cp -R "$parity" "$bare_runtime_dependency"
sed -i.bak 's/fastapi==0\.135\.\*/fastapi/' "$bare_runtime_dependency/pyproject.toml"
rm "$bare_runtime_dependency/pyproject.toml.bak"
set +e
bare_runtime_output=$($SCRIPT "$bare_runtime_dependency" 2>&1)
bare_runtime_status=$?
set -e
[[ $bare_runtime_status -eq 1 ]] || {
  printf 'Expected bare runtime dependency to exit 1, got %s\n%s\n' "$bare_runtime_status" "$bare_runtime_output" >&2
  exit 1
}
assert_contains "$bare_runtime_output" "FAIL: PEP 621 project and dependency groups"

truncated_lock="$TMP_DIR/truncated-lock"
cp -R "$parity" "$truncated_lock"
cat >"$truncated_lock/uv.lock" <<'EOF'
version = 1
revision = 3
requires-python = "==3.14.*"
EOF
set +e
truncated_lock_output=$($SCRIPT "$truncated_lock" 2>&1)
truncated_lock_status=$?
set -e
[[ $truncated_lock_status -eq 1 ]] || {
  printf 'Expected metadata-only uv.lock to exit 1, got %s\n%s\n' "$truncated_lock_status" "$truncated_lock_output" >&2
  exit 1
}
assert_contains "$truncated_lock_output" "FAIL: uv lockfile and Python 3.14 pin"

empty_lock="$TMP_DIR/empty-lock"
cp -R "$parity" "$empty_lock"
: >"$empty_lock/uv.lock"
set +e
empty_lock_output=$($SCRIPT "$empty_lock" 2>&1)
empty_lock_status=$?
set -e
[[ $empty_lock_status -eq 1 ]] || {
  printf 'Expected empty uv.lock to exit 1, got %s\n%s\n' "$empty_lock_status" "$empty_lock_output" >&2
  exit 1
}
assert_contains "$empty_lock_output" "FAIL: uv lockfile and Python 3.14 pin"

wrong_python="$TMP_DIR/wrong-python"
cp -R "$parity" "$wrong_python"
printf '3.12\n' >"$wrong_python/.python-version"
sed -i.bak 's/>=3\.14,<3\.15/>=3.12,<3.13/g' "$wrong_python/pyproject.toml" "$wrong_python/uv.lock"
rm "$wrong_python/pyproject.toml.bak" "$wrong_python/uv.lock.bak"
set +e
wrong_python_output=$($SCRIPT "$wrong_python" 2>&1)
wrong_python_status=$?
set -e
[[ $wrong_python_status -eq 1 ]] || {
  printf 'Expected Python 3.12 stack to exit 1, got %s\n%s\n' "$wrong_python_status" "$wrong_python_output" >&2
  exit 1
}
assert_contains "$wrong_python_output" "FAIL: uv lockfile and Python 3.12 pin"

misplaced_project_values="$TMP_DIR/misplaced-project-values"
cp -R "$parity" "$misplaced_project_values"
sed -i.bak '/^dependencies = /d; /^package = false$/d' "$misplaced_project_values/pyproject.toml"
rm "$misplaced_project_values/pyproject.toml.bak"
cat >>"$misplaced_project_values/pyproject.toml" <<'EOF'

[tool.unrelated]
dependencies = ["fastapi==0.135.*"]
package = false
EOF
set +e
misplaced_project_output=$($SCRIPT "$misplaced_project_values" 2>&1)
misplaced_project_status=$?
set -e
[[ $misplaced_project_status -eq 1 ]] || {
  printf 'Expected misplaced project values to exit 1, got %s\n%s\n' "$misplaced_project_status" "$misplaced_project_output" >&2
  exit 1
}
assert_contains "$misplaced_project_output" "FAIL: PEP 621 project and dependency groups"

duplicate_version="$TMP_DIR/duplicate-version"
cp -R "$parity" "$duplicate_version"
awk '
  /^\[tool.commitizen\]$/ { print; print "version = \"0.0.1\""; next }
  { print }
' "$duplicate_version/pyproject.toml" >"$duplicate_version/pyproject.toml.tmp"
mv "$duplicate_version/pyproject.toml.tmp" "$duplicate_version/pyproject.toml"
set +e
duplicate_version_output=$($SCRIPT "$duplicate_version" 2>&1)
duplicate_version_status=$?
set -e
[[ $duplicate_version_status -eq 1 ]] || {
  printf 'Expected duplicate version source to exit 1, got %s\n%s\n' "$duplicate_version_status" "$duplicate_version_output" >&2
  exit 1
}
assert_contains "$duplicate_version_output" "FAIL: single-source PEP 621 versioning"

changelog_disabled="$TMP_DIR/changelog-disabled"
cp -R "$parity" "$changelog_disabled"
sed -i.bak 's/update_changelog_on_bump = true/update_changelog_on_bump = false/' "$changelog_disabled/pyproject.toml"
rm "$changelog_disabled/pyproject.toml.bak"
set +e
changelog_disabled_output=$($SCRIPT "$changelog_disabled" 2>&1)
changelog_disabled_status=$?
set -e
[[ $changelog_disabled_status -eq 1 ]] || {
  printf 'Expected disabled changelog bump to exit 1, got %s\n%s\n' "$changelog_disabled_status" "$changelog_disabled_output" >&2
  exit 1
}
assert_contains "$changelog_disabled_output" "FAIL: single-source PEP 621 versioning"

missing_ruff_rule="$TMP_DIR/missing-ruff-rule"
cp -R "$parity" "$missing_ruff_rule"
sed -i.bak 's/, "PL",/,/' "$missing_ruff_rule/pyproject.toml"
rm "$missing_ruff_rule/pyproject.toml.bak"
set +e
missing_ruff_rule_output=$($SCRIPT "$missing_ruff_rule" 2>&1)
missing_ruff_rule_status=$?
set -e
[[ $missing_ruff_rule_status -eq 1 ]] || {
  printf 'Expected incomplete Ruff selection to exit 1, got %s\n%s\n' "$missing_ruff_rule_status" "$missing_ruff_rule_output" >&2
  exit 1
}
assert_contains "$missing_ruff_rule_output" "FAIL: quality dependencies and tool configuration"

e501_not_ignored="$TMP_DIR/e501-not-ignored"
cp -R "$parity" "$e501_not_ignored"
sed -i.bak 's/"PL",/"PL", "E501",/; s/ignore = \["E501"\]/ignore = []/' "$e501_not_ignored/pyproject.toml"
rm "$e501_not_ignored/pyproject.toml.bak"
set +e
e501_not_ignored_output=$($SCRIPT "$e501_not_ignored" 2>&1)
e501_not_ignored_status=$?
set -e
[[ $e501_not_ignored_status -eq 1 ]] || {
  printf 'Expected E501 outside ignore to exit 1, got %s\n%s\n' "$e501_not_ignored_status" "$e501_not_ignored_output" >&2
  exit 1
}
assert_contains "$e501_not_ignored_output" "FAIL: quality dependencies and tool configuration"

ruff_tc_enabled="$TMP_DIR/ruff-tc-enabled"
cp -R "$parity" "$ruff_tc_enabled"
sed -i.bak 's/"PL",/"PL", "TC",/' "$ruff_tc_enabled/pyproject.toml"
rm "$ruff_tc_enabled/pyproject.toml.bak"
set +e
ruff_tc_output=$($SCRIPT "$ruff_tc_enabled" 2>&1)
ruff_tc_status=$?
set -e
[[ $ruff_tc_status -eq 1 ]] || {
  printf 'Expected Ruff TC selection to exit 1, got %s\n%s\n' "$ruff_tc_status" "$ruff_tc_output" >&2
  exit 1
}
assert_contains "$ruff_tc_output" "FAIL: quality dependencies and tool configuration"

local_coverage_floor="$TMP_DIR/local-coverage-floor"
cp -R "$parity" "$local_coverage_floor"
sed -i.bak "s/not live'/not live' --cov-fail-under=90/" "$local_coverage_floor/pyproject.toml"
rm "$local_coverage_floor/pyproject.toml.bak"
set +e
local_coverage_output=$($SCRIPT "$local_coverage_floor" 2>&1)
local_coverage_status=$?
set -e
[[ $local_coverage_status -eq 1 ]] || {
  printf 'Expected local coverage floor to exit 1, got %s\n%s\n' "$local_coverage_status" "$local_coverage_output" >&2
  exit 1
}
assert_contains "$local_coverage_output" "FAIL: quality dependencies and tool configuration"

empty_mypy="$TMP_DIR/empty-mypy"
cp -R "$parity" "$empty_mypy"
awk '
  /^\[tool.mypy\]$/ { print; skip = 1; next }
  skip && /^\[/ { skip = 0 }
  !skip { print }
' "$empty_mypy/pyproject.toml" >"$empty_mypy/pyproject.toml.tmp"
mv "$empty_mypy/pyproject.toml.tmp" "$empty_mypy/pyproject.toml"
set +e
empty_mypy_output=$($SCRIPT "$empty_mypy" 2>&1)
empty_mypy_status=$?
set -e
[[ $empty_mypy_status -eq 1 ]] || {
  printf 'Expected empty mypy config to exit 1, got %s\n%s\n' "$empty_mypy_status" "$empty_mypy_output" >&2
  exit 1
}
assert_contains "$empty_mypy_output" "FAIL: quality dependencies and tool configuration"

empty_pytest="$TMP_DIR/empty-pytest"
cp -R "$parity" "$empty_pytest"
awk '
  /^\[tool.pytest.ini_options\]$/ { print; skip = 1; next }
  skip && /^\[/ { skip = 0 }
  !skip { print }
' "$empty_pytest/pyproject.toml" >"$empty_pytest/pyproject.toml.tmp"
mv "$empty_pytest/pyproject.toml.tmp" "$empty_pytest/pyproject.toml"
set +e
empty_pytest_output=$($SCRIPT "$empty_pytest" 2>&1)
empty_pytest_status=$?
set -e
[[ $empty_pytest_status -eq 1 ]] || {
  printf 'Expected empty pytest config to exit 1, got %s\n%s\n' "$empty_pytest_status" "$empty_pytest_output" >&2
  exit 1
}
assert_contains "$empty_pytest_output" "FAIL: quality dependencies and tool configuration"

# The retired four-tier vocabulary no longer satisfies the two-level standard.
legacy_tiers="$TMP_DIR/legacy-tiers"
cp -R "$parity" "$legacy_tiers"
sed -i.bak "s|addopts = \"-ra -q -m 'not live'\"|addopts = \"-ra -q -m 'not integration and not e2e'\"|" "$legacy_tiers/pyproject.toml"
rm "$legacy_tiers/pyproject.toml.bak"
set +e
legacy_tiers_output=$($SCRIPT "$legacy_tiers" 2>&1)
legacy_tiers_status=$?
set -e
[[ $legacy_tiers_status -eq 1 ]] || {
  printf 'Expected the retired tier markers to exit 1, got %s\n%s\n' "$legacy_tiers_status" "$legacy_tiers_output" >&2
  exit 1
}
assert_contains "$legacy_tiers_output" "pytest-values"

import_types_not_excluded="$TMP_DIR/import-types-not-excluded"
cp -R "$parity" "$import_types_not_excluded"
sed -i.bak 's/exclude_type_checking_imports = true/exclude_type_checking_imports = false/' "$import_types_not_excluded/pyproject.toml"
rm "$import_types_not_excluded/pyproject.toml.bak"
set +e
import_types_output=$($SCRIPT "$import_types_not_excluded" 2>&1)
import_types_status=$?
set -e
[[ $import_types_status -eq 1 ]] || {
  printf 'Expected import-linter type exclusions false to exit 1, got %s\n%s\n' "$import_types_status" "$import_types_output" >&2
  exit 1
}
assert_contains "$import_types_output" "FAIL: layered import contract"

misplaced_layers="$TMP_DIR/misplaced-layers"
cp -R "$parity" "$misplaced_layers"
sed -i.bak 's/type = "layers"/type = "independence"/' "$misplaced_layers/pyproject.toml"
rm "$misplaced_layers/pyproject.toml.bak"
cat >>"$misplaced_layers/pyproject.toml" <<'EOF'

[tool.unrelated-layers]
type = "layers"
layers = ["app.api", "app.service", "app.repository", "app.model"]
EOF
set +e
misplaced_layers_output=$($SCRIPT "$misplaced_layers" 2>&1)
misplaced_layers_status=$?
set -e
[[ $misplaced_layers_status -eq 1 ]] || {
  printf 'Expected misplaced layer tokens to exit 1, got %s\n%s\n' "$misplaced_layers_status" "$misplaced_layers_output" >&2
  exit 1
}
assert_contains "$misplaced_layers_output" "FAIL: layered import contract"

commented_test_target="$TMP_DIR/commented-test-target"
cp -R "$parity" "$commented_test_target"
sed -i.bak 's|uv run pytest tests/ -x -q|# uv run pytest tests/ -x -q|' "$commented_test_target/Makefile"
rm "$commented_test_target/Makefile.bak"
set +e
commented_test_output=$($SCRIPT "$commented_test_target" 2>&1)
commented_test_status=$?
set -e
[[ $commented_test_status -eq 1 ]] || {
  printf 'Expected commented test recipe to exit 1, got %s\n%s\n' "$commented_test_status" "$commented_test_output" >&2
  exit 1
}
assert_contains "$commented_test_output" "FAIL: minimal self-documented Makefile command surface"

for missing_gate in ruff-check mypy import-linter; do
  broken_docker="$TMP_DIR/docker-missing-$missing_gate"
  cp -R "$parity" "$broken_docker"
  case "$missing_gate" in
    ruff-check) sed -i.bak 's/ruff check \. && //' "$broken_docker/Dockerfile" ;;
    mypy) sed -i.bak 's/ && mypy app//' "$broken_docker/Dockerfile" ;;
    import-linter) sed -i.bak 's/ && lint-imports//' "$broken_docker/Dockerfile" ;;
  esac
  rm "$broken_docker/Dockerfile.bak"
  set +e
  broken_docker_output=$($SCRIPT "$broken_docker" 2>&1)
  broken_docker_status=$?
  set -e
  [[ $broken_docker_status -eq 1 ]] || {
    printf 'Expected Docker missing %s to exit 1, got %s\n%s\n' "$missing_gate" "$broken_docker_status" "$broken_docker_output" >&2
    exit 1
  }
  assert_contains "$broken_docker_output" "FAIL: uv-native Docker dependency and quality stages"
done

inert_docker_lint="$TMP_DIR/inert-docker-lint"
cp -R "$parity" "$inert_docker_lint"
sed -i.bak '/^RUN if \[ "$RUN_LINT_IN_BUILD" = "1" \]/c\
ENV CHECKS="ruff check . && ruff format --check . && lint-imports && mypy app"' "$inert_docker_lint/Dockerfile"
rm "$inert_docker_lint/Dockerfile.bak"
set +e
inert_docker_output=$($SCRIPT "$inert_docker_lint" 2>&1)
inert_docker_status=$?
set -e
[[ $inert_docker_status -eq 1 ]] || {
  printf 'Expected inert Docker lint ENV to exit 1, got %s\n%s\n' "$inert_docker_status" "$inert_docker_output" >&2
  exit 1
}
assert_contains "$inert_docker_output" "FAIL: uv-native Docker dependency and quality stages"

# Nothing fails on the coverage number, so the baseline fixtures carry no floor at all. A project
# that keeps one has deviated for its own reason, which this chapter allows, so it must still pass.
# Only a project that stops measuring is wrong, which the two cases below hold.
kept_coverage_floor="$TMP_DIR/kept-coverage-floor"
cp -R "$parity" "$kept_coverage_floor"
sed -i.bak 's/--cov=app/--cov=app --cov-fail-under=80/g' "$kept_coverage_floor/Dockerfile"
rm "$kept_coverage_floor/Dockerfile.bak"
sed -i.bak 's/--cov=app/--cov=app --cov-fail-under=80/g' "$kept_coverage_floor/.github/workflows/check.yml"
rm "$kept_coverage_floor/.github/workflows/check.yml.bak"
set +e
kept_coverage_floor_output=$($SCRIPT "$kept_coverage_floor" 2>&1)
kept_coverage_floor_status=$?
set -e
[[ $kept_coverage_floor_status -eq 0 ]] || {
  printf 'Expected a project keeping a coverage floor to exit 0, got %s\n%s\n' "$kept_coverage_floor_status" "$kept_coverage_floor_output" >&2
  exit 1
}
assert_contains "$kept_coverage_floor_output" "PASS: uv-native Docker dependency and quality stages"
assert_contains "$kept_coverage_floor_output" "PASS: effective shared Python CI contract"

docker_without_coverage="$TMP_DIR/docker-without-coverage"
cp -R "$parity" "$docker_without_coverage"
sed -i.bak 's/ --cov=app//; s/"--cov=app", //' "$docker_without_coverage/Dockerfile"
rm "$docker_without_coverage/Dockerfile.bak"
set +e
docker_without_coverage_output=$($SCRIPT "$docker_without_coverage" 2>&1)
docker_without_coverage_status=$?
set -e
[[ $docker_without_coverage_status -eq 1 ]] || {
  printf 'Expected Docker test stage without coverage measurement to exit 1, got %s\n%s\n' "$docker_without_coverage_status" "$docker_without_coverage_output" >&2
  exit 1
}
assert_contains "$docker_without_coverage_output" "FAIL: uv-native Docker dependency and quality stages"

mutable_python_base="$TMP_DIR/mutable-python-base"
cp -R "$parity" "$mutable_python_base"
sed -i.bak 's/@sha256:0000000000000000000000000000000000000000000000000000000000000002//' "$mutable_python_base/Dockerfile"
rm "$mutable_python_base/Dockerfile.bak"
set +e
mutable_python_output=$($SCRIPT "$mutable_python_base" 2>&1)
mutable_python_status=$?
set -e
[[ $mutable_python_status -eq 1 ]] || {
  printf 'Expected mutable Python base to exit 1, got %s\n%s\n' "$mutable_python_status" "$mutable_python_output" >&2
  exit 1
}
assert_contains "$mutable_python_output" "FAIL: immutable Docker bases and update path"

missing_docker_updates="$TMP_DIR/missing-docker-updates"
cp -R "$parity" "$missing_docker_updates"
awk '
  /package-ecosystem: docker/ { exit }
  { print }
' "$missing_docker_updates/.github/dependabot.yml" >"$missing_docker_updates/.github/dependabot.yml.tmp"
mv "$missing_docker_updates/.github/dependabot.yml.tmp" "$missing_docker_updates/.github/dependabot.yml"
set +e
missing_docker_updates_output=$($SCRIPT "$missing_docker_updates" 2>&1)
missing_docker_updates_status=$?
set -e
[[ $missing_docker_updates_status -eq 1 ]] || {
  printf 'Expected missing Docker updates to exit 1, got %s\n%s\n' "$missing_docker_updates_status" "$missing_docker_updates_output" >&2
  exit 1
}
assert_contains "$missing_docker_updates_output" "FAIL: immutable Docker bases and update path"

commented_docker_sync="$TMP_DIR/commented-docker-sync"
cp -R "$parity" "$commented_docker_sync"
sed -i.bak 's/^RUN uv sync --locked --no-dev --no-install-project/# RUN uv sync --locked --no-dev --no-install-project/' "$commented_docker_sync/Dockerfile"
rm "$commented_docker_sync/Dockerfile.bak"
set +e
commented_docker_output=$($SCRIPT "$commented_docker_sync" 2>&1)
commented_docker_status=$?
set -e
[[ $commented_docker_status -eq 1 ]] || {
  printf 'Expected commented runtime sync to exit 1, got %s\n%s\n' "$commented_docker_status" "$commented_docker_output" >&2
  exit 1
}
assert_contains "$commented_docker_output" "FAIL: uv-native Docker dependency and quality stages"

misplaced_runtime_copy="$TMP_DIR/misplaced-runtime-copy"
cp -R "$parity" "$misplaced_runtime_copy"
awk '
  /^COPY --from=runtime-deps \/app\/\.venv \/app\/\.venv$/ { next }
  { print }
  /^FROM dev-deps AS lint$/ { print "COPY --from=runtime-deps /app/.venv /app/.venv" }
' "$misplaced_runtime_copy/Dockerfile" >"$misplaced_runtime_copy/Dockerfile.tmp"
mv "$misplaced_runtime_copy/Dockerfile.tmp" "$misplaced_runtime_copy/Dockerfile"
set +e
misplaced_runtime_output=$($SCRIPT "$misplaced_runtime_copy" 2>&1)
misplaced_runtime_status=$?
set -e
[[ $misplaced_runtime_status -eq 1 ]] || {
  printf 'Expected runtime venv copy outside api stage to exit 1, got %s\n%s\n' "$misplaced_runtime_status" "$misplaced_runtime_output" >&2
  exit 1
}
assert_contains "$misplaced_runtime_output" "FAIL: uv-native Docker dependency and quality stages"

runtime_stage="$TMP_DIR/runtime-stage"
cp -R "$parity" "$runtime_stage"
sed -i.bak 's/^FROM base AS api$/FROM base AS runtime/' "$runtime_stage/Dockerfile"
rm "$runtime_stage/Dockerfile.bak"
runtime_stage_output=$($SCRIPT "$runtime_stage" 2>&1)
assert_contains "$runtime_stage_output" "VERDICT: PARITY"

ci_without_push="$TMP_DIR/ci-without-push"
cp -R "$parity" "$ci_without_push"
sed -i.bak '/^  push:/d' "$ci_without_push/.github/workflows/check.yml"
rm "$ci_without_push/.github/workflows/check.yml.bak"
set +e
ci_without_push_output=$($SCRIPT "$ci_without_push" 2>&1)
ci_without_push_status=$?
set -e
[[ $ci_without_push_status -eq 1 ]] || {
  printf 'Expected CI without push to exit 1, got %s\n%s\n' "$ci_without_push_status" "$ci_without_push_output" >&2
  exit 1
}
assert_contains "$ci_without_push_output" "FAIL: uv supply-chain updates and shared Python CI"

ci_resource_mismatch="$TMP_DIR/ci-resource-mismatch"
cp -R "$parity" "$ci_resource_mismatch"
cat >"$ci_resource_mismatch/.github/app.yml" <<'EOF'
app_name: example-service-backend
account: example
EOF
cat >"$ci_resource_mismatch/docker-bake.hcl" <<'EOF'
variable "ECR_API" { default = "example-service-backend" }
EOF
sed -i.bak '/      build_args:/i\
      ssh_deps: "shared-lib"' "$ci_resource_mismatch/.github/workflows/check.yml"
rm "$ci_resource_mismatch/.github/workflows/check.yml.bak"
set +e
ci_resource_mismatch_output=$($SCRIPT "$ci_resource_mismatch" 2>&1)
ci_resource_mismatch_status=$?
set -e
[[ $ci_resource_mismatch_status -eq 1 ]] || {
  printf 'Expected mismatched shared-CI resource identity to exit 1, got %s\n%s\n' "$ci_resource_mismatch_status" "$ci_resource_mismatch_output" >&2
  exit 1
}
assert_contains "$ci_resource_mismatch_output" "FAIL: effective shared Python CI contract"

ci_resource_override="$TMP_DIR/ci-resource-override"
cp -R "$ci_resource_mismatch" "$ci_resource_override"
sed -i.bak '/ssh_deps:/a\
      ecr_repo_override: "example-service-backend"' "$ci_resource_override/.github/workflows/check.yml"
rm "$ci_resource_override/.github/workflows/check.yml.bak"
ci_resource_override_output=$($SCRIPT "$ci_resource_override")
assert_contains "$ci_resource_override_output" "PASS: effective shared Python CI contract"
assert_contains "$ci_resource_override_output" "VERDICT: PARITY"

ci_cache_only_bake="$TMP_DIR/ci-cache-only-bake"
cp -R "$ci_resource_mismatch" "$ci_cache_only_bake"
cat >"$ci_cache_only_bake/docker-bake.hcl" <<'EOF'
variable "ECR_API" { default = "example-service-backend" }
target "lint" { target = "lint" output = ["type=cacheonly"] }
target "test" { target = "test" output = ["type=cacheonly"] }
EOF
cat >"$ci_cache_only_bake/.github/workflows/check.yml" <<'EOF'
name: Check
on:
  push:
    branches: ["**"]
jobs:
  check:
    uses: example-org/shared-github-actions/.github/workflows/check-python-bake.yml@v2
    with:
      bake_targets: lint,test
      ssh_deps: shared-lib
EOF
ci_cache_only_bake_output=$($SCRIPT "$ci_cache_only_bake")
assert_contains "$ci_cache_only_bake_output" "PASS: persistent cache-only Bake CI contract"
assert_contains "$ci_cache_only_bake_output" "VERDICT: PARITY"

ci_cache_only_export="$TMP_DIR/ci-cache-only-export"
cp -R "$ci_cache_only_bake" "$ci_cache_only_export"
sed -i.bak 's|output = \["type=cacheonly"\] }|output = ["type=cacheonly"] cache-to = ["type=registry,ref=registry/check:cache"] }|' "$ci_cache_only_export/docker-bake.hcl"
rm "$ci_cache_only_export/docker-bake.hcl.bak"
set +e
ci_cache_only_export_output=$($SCRIPT "$ci_cache_only_export" 2>&1)
ci_cache_only_export_status=$?
set -e
[[ $ci_cache_only_export_status -eq 1 ]] || {
  printf 'Expected cache-only Bake export to exit 1, got %s\n%s\n' "$ci_cache_only_export_status" "$ci_cache_only_export_output" >&2
  exit 1
}
assert_contains "$ci_cache_only_export_output" "FAIL: persistent cache-only Bake CI contract"

ci_cache_only_mixed_output="$TMP_DIR/ci-cache-only-mixed-output"
cp -R "$ci_cache_only_bake" "$ci_cache_only_mixed_output"
sed -i.bak 's/\["type=cacheonly"\]/["type=cacheonly", "type=docker"]/' "$ci_cache_only_mixed_output/docker-bake.hcl"
rm "$ci_cache_only_mixed_output/docker-bake.hcl.bak"
set +e
ci_cache_only_mixed_output_result=$($SCRIPT "$ci_cache_only_mixed_output" 2>&1)
ci_cache_only_mixed_output_status=$?
set -e
[[ $ci_cache_only_mixed_output_status -eq 1 ]] || {
  printf 'Expected mixed Bake outputs to exit 1, got %s\n%s\n' "$ci_cache_only_mixed_output_status" "$ci_cache_only_mixed_output_result" >&2
  exit 1
}
assert_contains "$ci_cache_only_mixed_output_result" "FAIL: persistent cache-only Bake CI contract"

direct_persistent_bake="$TMP_DIR/direct-persistent-bake"
cp -R "$parity" "$direct_persistent_bake"
cat >"$direct_persistent_bake/docker-bake.hcl" <<'EOF'
target "lint" { target = "lint" output = ["type=cacheonly"] }
target "test" { target = "test" output = ["type=cacheonly"] }
EOF
cat >"$direct_persistent_bake/.github/workflows/check.yml" <<'EOF'
name: Check
on:
  push:
    branches: ["**"]
jobs:
  check:
    runs-on: [self-hosted, linux, x64]
    steps:
      - id: builder
        env:
          REPOSITORY: ${{ github.repository }}
          RUNNER_NAME: ${{ runner.name }}
        run: |
          SCOPE_HASH=$(printf '%s' "${REPOSITORY}-${RUNNER_NAME}" | sha256sum | cut -c1-16)
          echo "name=check-python-${SCOPE_HASH}" >> "$GITHUB_OUTPUT"
      - uses: docker/setup-buildx-action@v4
        with:
          name: ${{ steps.builder.outputs.name }}
          keep-state: true
          buildkitd-config-inline: |
            [worker.oci]
              gc = true
              maxUsedSpace = "12GB"
              minFreeSpace = "20GB"
      - run: docker buildx bake lint test
EOF
direct_persistent_bake_output=$($SCRIPT "$direct_persistent_bake")
assert_contains "$direct_persistent_bake_output" "PASS: persistent cache-only Bake CI contract"
assert_contains "$direct_persistent_bake_output" "VERDICT: PARITY"

direct_bake_without_state="$TMP_DIR/direct-bake-without-state"
cp -R "$direct_persistent_bake" "$direct_bake_without_state"
sed -i.bak '/keep-state:/d' "$direct_bake_without_state/.github/workflows/check.yml"
rm "$direct_bake_without_state/.github/workflows/check.yml.bak"
set +e
direct_bake_without_state_output=$($SCRIPT "$direct_bake_without_state" 2>&1)
direct_bake_without_state_status=$?
set -e
[[ $direct_bake_without_state_status -eq 1 ]] || {
  printf 'Expected direct Bake without persistent state to exit 1, got %s\n%s\n' "$direct_bake_without_state_status" "$direct_bake_without_state_output" >&2
  exit 1
}
assert_contains "$direct_bake_without_state_output" "FAIL: persistent cache-only Bake CI contract"

direct_bake_without_gc="$TMP_DIR/direct-bake-without-gc"
cp -R "$direct_persistent_bake" "$direct_bake_without_gc"
sed -i.bak '/buildkitd-config-inline:/,/minFreeSpace/d' "$direct_bake_without_gc/.github/workflows/check.yml"
rm "$direct_bake_without_gc/.github/workflows/check.yml.bak"
set +e
direct_bake_without_gc_output=$($SCRIPT "$direct_bake_without_gc" 2>&1)
direct_bake_without_gc_status=$?
set -e
[[ $direct_bake_without_gc_status -eq 1 ]] || {
  printf 'Expected direct Bake without bounded GC to exit 1, got %s\n%s\n' "$direct_bake_without_gc_status" "$direct_bake_without_gc_output" >&2
  exit 1
}
assert_contains "$direct_bake_without_gc_output" "FAIL: persistent cache-only Bake CI contract"

direct_bake_without_isolation="$TMP_DIR/direct-bake-without-isolation"
cp -R "$direct_persistent_bake" "$direct_bake_without_isolation"
sed -i.bak 's/sha256sum/cat/' "$direct_bake_without_isolation/.github/workflows/check.yml"
rm "$direct_bake_without_isolation/.github/workflows/check.yml.bak"
set +e
direct_bake_without_isolation_output=$($SCRIPT "$direct_bake_without_isolation" 2>&1)
direct_bake_without_isolation_status=$?
set -e
[[ $direct_bake_without_isolation_status -eq 1 ]] || {
  printf 'Expected direct Bake without collision-resistant isolation to exit 1, got %s\n%s\n' "$direct_bake_without_isolation_status" "$direct_bake_without_isolation_output" >&2
  exit 1
}
assert_contains "$direct_bake_without_isolation_output" "FAIL: persistent cache-only Bake CI contract"

direct_bake_wrong_selection="$TMP_DIR/direct-bake-wrong-selection"
cp -R "$direct_persistent_bake" "$direct_bake_wrong_selection"
sed -i.bak 's/docker buildx bake lint test/docker buildx bake api/' "$direct_bake_wrong_selection/.github/workflows/check.yml"
rm "$direct_bake_wrong_selection/.github/workflows/check.yml.bak"
set +e
direct_bake_wrong_output=$($SCRIPT "$direct_bake_wrong_selection" 2>&1)
direct_bake_wrong_status=$?
set -e
[[ $direct_bake_wrong_status -eq 1 ]] || {
  printf 'Expected direct Bake with wrong targets to exit 1, got %s\n%s\n' "$direct_bake_wrong_status" "$direct_bake_wrong_output" >&2
  exit 1
}
assert_contains "$direct_bake_wrong_output" "FAIL: persistent cache-only Bake CI contract"

classic_duplicate_gate="$TMP_DIR/classic-duplicate-gate"
cp -R "$parity" "$classic_duplicate_gate"
sed -i.bak '/RUN_TESTS_IN_BUILD=0/d; /RUN_LINT_IN_BUILD=0/d' "$classic_duplicate_gate/.github/workflows/check.yml"
rm "$classic_duplicate_gate/.github/workflows/check.yml.bak"
set +e
classic_duplicate_output=$($SCRIPT "$classic_duplicate_gate" 2>&1)
classic_duplicate_status=$?
set -e
[[ $classic_duplicate_status -eq 1 ]] || {
  printf 'Expected classic shared CI with duplicate Docker gates to exit 1, got %s\n%s\n' "$classic_duplicate_status" "$classic_duplicate_output" >&2
  exit 1
}
assert_contains "$classic_duplicate_output" "FAIL: effective shared Python CI contract"

ci_coverage_bypass="$TMP_DIR/ci-coverage-bypass"
cp -R "$parity" "$ci_coverage_bypass"
sed -i.bak 's|test_command: "pytest --cov=app tests"|test_command: "pytest tests"|' "$ci_coverage_bypass/.github/workflows/check.yml"
rm "$ci_coverage_bypass/.github/workflows/check.yml.bak"
set +e
ci_coverage_bypass_output=$($SCRIPT "$ci_coverage_bypass" 2>&1)
ci_coverage_bypass_status=$?
set -e
[[ $ci_coverage_bypass_status -eq 1 ]] || {
  printf 'Expected effective CI coverage bypass to exit 1, got %s\n%s\n' "$ci_coverage_bypass_status" "$ci_coverage_bypass_output" >&2
  exit 1
}
assert_contains "$ci_coverage_bypass_output" "FAIL: effective shared Python CI contract"

ci_coverage_retained="$TMP_DIR/ci-coverage-retained"
cp -R "$ci_coverage_bypass" "$ci_coverage_retained"
sed -i.bak 's|test_command: "pytest tests"|test_command: "pytest --cov=app tests"|' "$ci_coverage_retained/.github/workflows/check.yml"
rm "$ci_coverage_retained/.github/workflows/check.yml.bak"
ci_coverage_retained_output=$($SCRIPT "$ci_coverage_retained")
assert_contains "$ci_coverage_retained_output" "PASS: effective shared Python CI contract"
assert_contains "$ci_coverage_retained_output" "VERDICT: PARITY"

native_check="$TMP_DIR/native-check"
cp -R "$parity" "$native_check"
cat >"$native_check/.github/workflows/check.yml" <<'EOF'
name: Native check
on:
  push:
    branches: ['**']
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: uv run --frozen ruff check .
      - run: uv run --frozen ruff format --check .
      - run: uv run --frozen lint-imports
      - run: uv run --frozen mypy app
      - run: uv run --frozen pytest --cov=app --cov-report=term-missing tests
      # A native CI reaches the security gate directly; there is no Dockerfile to fall back to.
      - run: uv run --frozen pip-audit
      - run: uv run --frozen zizmor .github/workflows
EOF
# `--cov-report=term-missing` contains `-m`: a flag scan must not read it as a marker selection.
native_check_output=$($SCRIPT "$native_check")
assert_contains "$native_check_output" "PASS: native Python CI contract"
assert_contains "$native_check_output" "VERDICT: PARITY"

native_missing_gate="$TMP_DIR/native-missing-gate"
cp -R "$native_check" "$native_missing_gate"
sed -i.bak '/mypy app/d' "$native_missing_gate/.github/workflows/check.yml"
rm "$native_missing_gate/.github/workflows/check.yml.bak"
set +e
native_missing_output=$($SCRIPT "$native_missing_gate" 2>&1)
native_missing_status=$?
set -e
[[ $native_missing_status -eq 1 ]] || {
  printf 'Expected native CI missing mypy to exit 1, got %s\n%s\n' "$native_missing_status" "$native_missing_output" >&2
  exit 1
}
assert_contains "$native_missing_output" "FAIL: native Python CI contract"

# A CI marker override replaces the project's `not live` default, so it must restate it.
native_clears_markers="$TMP_DIR/native-clears-markers"
cp -R "$native_check" "$native_clears_markers"
sed -i.bak 's|pytest --cov=app|pytest -m "" --cov=app|' "$native_clears_markers/.github/workflows/check.yml"
rm "$native_clears_markers/.github/workflows/check.yml.bak"
set +e
native_clears_markers_output=$($SCRIPT "$native_clears_markers" 2>&1)
native_clears_markers_status=$?
set -e
[[ $native_clears_markers_status -eq 1 ]] || {
  printf 'Expected native CI clearing the marker filter to exit 1, got %s\n%s\n' "$native_clears_markers_status" "$native_clears_markers_output" >&2
  exit 1
}
assert_contains "$native_clears_markers_output" "FAIL: native Python CI contract"

native_restates_not_live="$TMP_DIR/native-restates-not-live"
cp -R "$native_clears_markers" "$native_restates_not_live"
sed -i.bak 's|pytest -m ""|pytest -m "not live"|' "$native_restates_not_live/.github/workflows/check.yml"
rm "$native_restates_not_live/.github/workflows/check.yml.bak"
native_restates_not_live_output=$($SCRIPT "$native_restates_not_live")
assert_contains "$native_restates_not_live_output" "PASS: native Python CI contract"
assert_contains "$native_restates_not_live_output" "VERDICT: PARITY"

# `python -m pytest` carries an unrelated `-m`; only pytest's own arguments select markers.
native_module_invocation="$TMP_DIR/native-module-invocation"
cp -R "$native_check" "$native_module_invocation"
sed -i.bak 's|frozen pytest --cov=app|frozen python -m pytest --cov=app|' \
  "$native_module_invocation/.github/workflows/check.yml"
rm "$native_module_invocation/.github/workflows/check.yml.bak"
native_module_invocation_output=$($SCRIPT "$native_module_invocation")
assert_contains "$native_module_invocation_output" "PASS: native Python CI contract"

for forbidden_selection in 'live' 'live or not live'; do
  native_selects_live="$TMP_DIR/native-selects-live"
  rm -rf "$native_selects_live"
  cp -R "$native_check" "$native_selects_live"
  sed -i.bak "s|pytest --cov=app|pytest -m \"$forbidden_selection\" --cov=app|" \
    "$native_selects_live/.github/workflows/check.yml"
  rm "$native_selects_live/.github/workflows/check.yml.bak"
  set +e
  native_selects_live_output=$($SCRIPT "$native_selects_live" 2>&1)
  native_selects_live_status=$?
  set -e
  [[ $native_selects_live_status -eq 1 ]] || {
    printf 'Expected CI selecting "%s" to exit 1, got %s\n%s\n' \
      "$forbidden_selection" "$native_selects_live_status" "$native_selects_live_output" >&2
    exit 1
  }
  assert_contains "$native_selects_live_output" "FAIL: native Python CI contract"
done

pipeline="$TMP_DIR/pipeline"
cp -R "$parity" "$pipeline"
cat >"$pipeline/.github/workflows/check.yml" <<'EOF'
name: Check
on:
  push:
    branches-ignore: [dev, staging, main]
jobs:
  check:
    uses: example-org/shared-github-actions/.github/workflows/check-python.yml@main
    with:
      test_command: "pytest --cov=app tests"
      lint_command: "ruff check . && ruff format --check . && lint-imports && mypy app"
      build_args: |
        RUN_TESTS_IN_BUILD=0
        RUN_LINT_IN_BUILD=0
EOF
cat >"$pipeline/.github/workflows/deploy.yml" <<'EOF'
name: Build and Deploy
on:
  push:
    branches: [dev, staging, main]
jobs:
  deploy:
    uses: example-org/shared-github-actions/.github/workflows/pipeline-ecs.yml@v2
    with:
      use_bake: true
      bake_file: docker-bake.hcl
      bake_target: ci
EOF
cat >"$pipeline/docker-bake.hcl" <<'EOF'
target "lint" { target = "lint" }
target "test" { target = "test" }
target "api" { target = "api" }
group "ci" { targets = ["lint", "test", "api"] }
EOF
pipeline_output=$($SCRIPT "$pipeline")
assert_contains "$pipeline_output" "PASS: uv supply-chain updates and shared Python CI"
assert_contains "$pipeline_output" "PASS: CI validation covers feature and deploy branches"
assert_contains "$pipeline_output" "VERDICT: PARITY"

protected_only_pipeline="$TMP_DIR/protected-only-pipeline"
cp -R "$pipeline" "$protected_only_pipeline"
rm "$protected_only_pipeline/.github/workflows/check.yml"
set +e
protected_only_output=$($SCRIPT "$protected_only_pipeline" 2>&1)
protected_only_status=$?
set -e
[[ $protected_only_status -eq 1 ]] || {
  printf 'Expected protected-only CI to exit 1, got %s\n%s\n' "$protected_only_status" "$protected_only_output" >&2
  exit 1
}
assert_contains "$protected_only_output" "FAIL: CI validation covers feature and deploy branches"

overlapping_check_deploy="$TMP_DIR/overlapping-check-deploy"
cp -R "$pipeline" "$overlapping_check_deploy"
cp "$parity/.github/workflows/check.yml" "$overlapping_check_deploy/.github/workflows/check.yml"
set +e
overlapping_output=$($SCRIPT "$overlapping_check_deploy" 2>&1)
overlapping_status=$?
set -e
[[ $overlapping_status -eq 1 ]] || {
  printf 'Expected overlapping check/deploy triggers to exit 1, got %s\n%s\n' "$overlapping_status" "$overlapping_output" >&2
  exit 1
}
assert_contains "$overlapping_output" "FAIL: disjoint check and deploy push ownership"

alternate_mutable_dockerfile="$TMP_DIR/alternate-mutable-dockerfile"
cp -R "$parity" "$alternate_mutable_dockerfile"
mkdir -p "$alternate_mutable_dockerfile/backend"
cat >"$alternate_mutable_dockerfile/backend/Dockerfile.streaming" <<'EOF'
FROM python:3.14-slim
EOF
set +e
alternate_mutable_output=$($SCRIPT "$alternate_mutable_dockerfile" 2>&1)
alternate_mutable_status=$?
set -e
[[ $alternate_mutable_status -eq 1 ]] || {
  printf 'Expected mutable alternate Dockerfile to exit 1, got %s\n%s\n' "$alternate_mutable_status" "$alternate_mutable_output" >&2
  exit 1
}
assert_contains "$alternate_mutable_output" "FAIL: immutable Docker bases and update path"

ignored_dependency_dockerfile="$TMP_DIR/ignored-dependency-dockerfile"
cp -R "$parity" "$ignored_dependency_dockerfile"
git -C "$ignored_dependency_dockerfile" init -q
printf 'node_modules/\n' >"$ignored_dependency_dockerfile/.gitignore"
mkdir -p "$ignored_dependency_dockerfile/frontend/node_modules/example"
cat >"$ignored_dependency_dockerfile/frontend/node_modules/example/Dockerfile" <<'EOF'
FROM node:latest
EOF
git -C "$ignored_dependency_dockerfile" add .
ignored_dependency_output=$($SCRIPT "$ignored_dependency_dockerfile")
assert_contains "$ignored_dependency_output" "PASS: immutable Docker bases and update path"
assert_contains "$ignored_dependency_output" "VERDICT: PARITY"

cat >"$ignored_dependency_dockerfile/frontend/Dockerfile.preview" <<'EOF'
FROM node:latest
EOF
set +e
untracked_dockerfile_output=$($SCRIPT "$ignored_dependency_dockerfile" 2>&1)
untracked_dockerfile_status=$?
set -e
[[ $untracked_dockerfile_status -eq 1 ]] || {
  printf 'Expected untracked non-ignored Dockerfile to exit 1, got %s\n%s\n' \
    "$untracked_dockerfile_status" "$untracked_dockerfile_output" >&2
  exit 1
}
assert_contains "$untracked_dockerfile_output" "FAIL: immutable Docker bases and update path"

pipeline_duplicate_cache="$TMP_DIR/pipeline-duplicate-cache"
cp -R "$pipeline" "$pipeline_duplicate_cache"
cat >"$pipeline_duplicate_cache/docker-bake.hcl" <<'EOF'
target "_common" {
  cache-to = ["type=registry,ref=registry/service:cache-branch,mode=max"]
}
target "lint" { inherits = ["_common"] target = "lint" }
target "test" { inherits = ["_common"] target = "test" }
target "api" { inherits = ["_common"] target = "api" }
group "ci" { targets = ["lint", "test", "api"] }
EOF
set +e
pipeline_duplicate_cache_output=$($SCRIPT "$pipeline_duplicate_cache" 2>&1)
pipeline_duplicate_cache_status=$?
set -e
[[ $pipeline_duplicate_cache_status -eq 1 ]] || {
  printf 'Expected duplicate Bake cache writers to exit 1, got %s\n%s\n' "$pipeline_duplicate_cache_status" "$pipeline_duplicate_cache_output" >&2
  exit 1
}
assert_contains "$pipeline_duplicate_cache_output" "FAIL: selected Bake cache ownership"

direct_bake_duplicate_cache="$TMP_DIR/direct-bake-duplicate-cache"
cp -R "$pipeline_duplicate_cache" "$direct_bake_duplicate_cache"
rm "$direct_bake_duplicate_cache/.github/workflows/deploy.yml"
cat >"$direct_bake_duplicate_cache/.github/workflows/bake.yml" <<'EOF'
name: Bake
on:
  push:
    branches: [dev, staging, main]
jobs:
  bake:
    runs-on: ubuntu-latest
    steps:
      - uses: example-org/shared-github-actions/actions/build-push-ecr-bake@v2
        with:
          bake_target: ci
EOF
set +e
direct_bake_duplicate_output=$($SCRIPT "$direct_bake_duplicate_cache" 2>&1)
direct_bake_duplicate_status=$?
set -e
[[ $direct_bake_duplicate_status -eq 1 ]] || {
  printf 'Expected direct Bake cache writers to exit 1, got %s\n%s\n' "$direct_bake_duplicate_status" "$direct_bake_duplicate_output" >&2
  exit 1
}
assert_contains "$direct_bake_duplicate_output" "FAIL: selected Bake cache ownership"

pipeline_distinct_caches="$TMP_DIR/pipeline-distinct-caches"
cp -R "$pipeline" "$pipeline_distinct_caches"
cat >"$pipeline_distinct_caches/docker-bake.hcl" <<'EOF'
target "lint" {
  target = "lint"
  cache-to = ["type=registry,ref=registry/service:cache-lint,mode=max"]
}
target "test" {
  target = "test"
  cache-to = ["type=registry,ref=registry/service:cache-test,mode=max"]
}
target "api" {
  target = "api"
  cache-to = ["type=registry,ref=registry/service:cache-api,mode=max"]
}
group "ci" { targets = ["lint", "test", "api"] }
EOF
pipeline_distinct_caches_output=$($SCRIPT "$pipeline_distinct_caches")
assert_contains "$pipeline_distinct_caches_output" "PASS: selected Bake cache ownership"
assert_contains "$pipeline_distinct_caches_output" "VERDICT: PARITY"

private_pipeline="$TMP_DIR/private-pipeline"
cp -R "$pipeline" "$private_pipeline"
sed -i.bak 's|"gunicorn==26.0\.\*"\]|"gunicorn==26.0.*", "private-lib @ git+ssh://git@example.com/team/private-lib.git@1.2.3"]|' "$private_pipeline/pyproject.toml"
rm "$private_pipeline/pyproject.toml.bak"
sed -i.bak 's|RUN uv sync --locked --no-dev --no-install-project|RUN --mount=type=ssh uv sync --locked --no-dev --no-install-project|' "$private_pipeline/Dockerfile"
rm "$private_pipeline/Dockerfile.bak"
sed -i.bak 's|docker build --target api|docker build --ssh default --target api|' "$private_pipeline/Makefile"
rm "$private_pipeline/Makefile.bak"
sed -i.bak 's|docker buildx bake test|docker buildx bake --allow=ssh test|' "$private_pipeline/Makefile"
rm "$private_pipeline/Makefile.bak"
cat >"$private_pipeline/docker-bake.hcl" <<'EOF'
target "_common" {
  ssh = ["default"]
}
target "lint" {
  inherits = ["_common"]
  target = "lint"
}
target "test" {
  inherits = ["_common"]
  target = "test"
}
target "api" {
  inherits = ["_common"]
  target = "api"
}
group "ci" { targets = ["lint", "test", "api"] }
EOF
private_pipeline_output=$($SCRIPT "$private_pipeline")
assert_contains "$private_pipeline_output" "VERDICT: PARITY"

private_without_docker_ssh="$TMP_DIR/private-without-docker-ssh"
cp -R "$private_pipeline" "$private_without_docker_ssh"
sed -i.bak 's/--mount=type=ssh //' "$private_without_docker_ssh/Dockerfile"
rm "$private_without_docker_ssh/Dockerfile.bak"
set +e
private_without_docker_output=$($SCRIPT "$private_without_docker_ssh" 2>&1)
private_without_docker_status=$?
set -e
[[ $private_without_docker_status -eq 1 ]] || {
  printf 'Expected private dependency without Docker SSH to exit 1, got %s\n%s\n' "$private_without_docker_status" "$private_without_docker_output" >&2
  exit 1
}
assert_contains "$private_without_docker_output" "FAIL: uv-native Docker dependency and quality stages"

private_without_bake_ssh="$TMP_DIR/private-without-bake-ssh"
cp -R "$private_pipeline" "$private_without_bake_ssh"
rm "$private_without_bake_ssh/.github/workflows/check.yml"
sed -i.bak '/ssh = \["default"\]/d' "$private_without_bake_ssh/docker-bake.hcl"
rm "$private_without_bake_ssh/docker-bake.hcl.bak"
set +e
private_without_bake_output=$($SCRIPT "$private_without_bake_ssh" 2>&1)
private_without_bake_status=$?
set -e
[[ $private_without_bake_status -eq 1 ]] || {
  printf 'Expected private dependency without Bake SSH to exit 1, got %s\n%s\n' "$private_without_bake_status" "$private_without_bake_output" >&2
  exit 1
}
assert_contains "$private_without_bake_output" "FAIL: uv supply-chain updates and shared Python CI"

private_without_bake_allow="$TMP_DIR/private-without-bake-allow"
cp -R "$private_pipeline" "$private_without_bake_allow"
sed -i.bak 's|docker buildx bake --allow=ssh test|docker buildx bake test|' "$private_without_bake_allow/Makefile"
rm "$private_without_bake_allow/Makefile.bak"
set +e
private_without_bake_allow_output=$($SCRIPT "$private_without_bake_allow" 2>&1)
private_without_bake_allow_status=$?
set -e
[[ $private_without_bake_allow_status -eq 1 ]] || {
  printf 'Expected private dependency without Bake --allow=ssh to exit 1, got %s\n%s\n' "$private_without_bake_allow_status" "$private_without_bake_allow_output" >&2
  exit 1
}
assert_contains "$private_without_bake_allow_output" "FAIL: minimal self-documented Makefile command surface"

pipeline_comment_only="$TMP_DIR/pipeline-comment-only"
cp -R "$pipeline" "$pipeline_comment_only"
rm "$pipeline_comment_only/.github/workflows/check.yml"
sed -i.bak 's/^      use_bake:/      # use_bake:/; s/^      bake_target:/      # bake_target:/' "$pipeline_comment_only/.github/workflows/deploy.yml"
rm "$pipeline_comment_only/.github/workflows/deploy.yml.bak"
set +e
pipeline_comment_output=$($SCRIPT "$pipeline_comment_only" 2>&1)
pipeline_comment_status=$?
set -e
[[ $pipeline_comment_status -eq 1 ]] || {
  printf 'Expected comment-only Bake settings to exit 1, got %s\n%s\n' "$pipeline_comment_status" "$pipeline_comment_output" >&2
  exit 1
}
assert_contains "$pipeline_comment_output" "FAIL: uv supply-chain updates and shared Python CI"

pipeline_commented_members="$TMP_DIR/pipeline-commented-members"
cp -R "$pipeline" "$pipeline_commented_members"
rm "$pipeline_commented_members/.github/workflows/check.yml"
sed -i.bak 's/group "ci" { targets = \["lint", "test", "api"\] }/group "ci" { targets = ["api"] } \/\/ "lint" "test"/' "$pipeline_commented_members/docker-bake.hcl"
rm "$pipeline_commented_members/docker-bake.hcl.bak"
set +e
pipeline_commented_members_output=$($SCRIPT "$pipeline_commented_members" 2>&1)
pipeline_commented_members_status=$?
set -e
[[ $pipeline_commented_members_status -eq 1 ]] || {
  printf 'Expected comment-only Bake members to exit 1, got %s\n%s\n' "$pipeline_commented_members_status" "$pipeline_commented_members_output" >&2
  exit 1
}
assert_contains "$pipeline_commented_members_output" "FAIL: uv supply-chain updates and shared Python CI"

pipeline_without_test_member="$TMP_DIR/pipeline-without-test-member"
cp -R "$pipeline" "$pipeline_without_test_member"
rm "$pipeline_without_test_member/.github/workflows/check.yml"
sed -i.bak 's/"lint", "test", "api"/"lint", "api"/' "$pipeline_without_test_member/docker-bake.hcl"
rm "$pipeline_without_test_member/docker-bake.hcl.bak"
set +e
pipeline_without_test_member_output=$($SCRIPT "$pipeline_without_test_member" 2>&1)
pipeline_without_test_member_status=$?
set -e
[[ $pipeline_without_test_member_status -eq 1 ]] || {
  printf 'Expected bake group without test to exit 1, got %s\n%s\n' "$pipeline_without_test_member_status" "$pipeline_without_test_member_output" >&2
  exit 1
}
assert_contains "$pipeline_without_test_member_output" "FAIL: uv supply-chain updates and shared Python CI"

pipeline_wrong_mapping="$TMP_DIR/pipeline-wrong-mapping"
cp -R "$pipeline" "$pipeline_wrong_mapping"
rm "$pipeline_wrong_mapping/.github/workflows/check.yml"
sed -i.bak 's/target "test" { target = "test" }/target "test" { target = "api" }/' "$pipeline_wrong_mapping/docker-bake.hcl"
rm "$pipeline_wrong_mapping/docker-bake.hcl.bak"
set +e
pipeline_wrong_mapping_output=$($SCRIPT "$pipeline_wrong_mapping" 2>&1)
pipeline_wrong_mapping_status=$?
set -e
[[ $pipeline_wrong_mapping_status -eq 1 ]] || {
  printf 'Expected wrong bake-to-Docker mapping to exit 1, got %s\n%s\n' "$pipeline_wrong_mapping_status" "$pipeline_wrong_mapping_output" >&2
  exit 1
}
assert_contains "$pipeline_wrong_mapping_output" "FAIL: uv supply-chain updates and shared Python CI"

pipeline_multiple_groups="$TMP_DIR/pipeline-multiple-groups"
cp -R "$pipeline" "$pipeline_multiple_groups"
sed -i.bak "s/bake_target: ci/bake_target: \${{ github.ref_name == 'main' \&\& 'ci-main' || 'ci' }}/" "$pipeline_multiple_groups/.github/workflows/deploy.yml"
rm "$pipeline_multiple_groups/.github/workflows/deploy.yml.bak"
cat >>"$pipeline_multiple_groups/docker-bake.hcl" <<'EOF'
target "test-e2e" { target = "test-e2e" }
group "ci-main" { targets = ["lint", "test-e2e", "api"] }
EOF
pipeline_multiple_output=$($SCRIPT "$pipeline_multiple_groups")
assert_contains "$pipeline_multiple_output" "VERDICT: PARITY"

pipeline_bad_main_group="$TMP_DIR/pipeline-bad-main-group"
cp -R "$pipeline_multiple_groups" "$pipeline_bad_main_group"
rm "$pipeline_bad_main_group/.github/workflows/check.yml"
sed -i.bak 's/\["lint", "test-e2e", "api"\]/["lint", "api"]/' "$pipeline_bad_main_group/docker-bake.hcl"
rm "$pipeline_bad_main_group/docker-bake.hcl.bak"
set +e
pipeline_bad_main_output=$($SCRIPT "$pipeline_bad_main_group" 2>&1)
pipeline_bad_main_status=$?
set -e
[[ $pipeline_bad_main_status -eq 1 ]] || {
  printf 'Expected selected ci-main group without tests to exit 1, got %s\n%s\n' "$pipeline_bad_main_status" "$pipeline_bad_main_output" >&2
  exit 1
}
assert_contains "$pipeline_bad_main_output" "FAIL: uv supply-chain updates and shared Python CI"

monorepo="$TMP_DIR/monorepo"
create_parity_project "$monorepo/backend"
mv "$monorepo/backend/.github" "$monorepo/.github"
mv "$monorepo/backend/.pre-commit-config.yaml" "$monorepo/.pre-commit-config.yaml"
mv "$monorepo/backend/.dockerignore" "$monorepo/.dockerignore"
monorepo_output=$($SCRIPT "$monorepo")
assert_contains "$monorepo_output" "VERDICT: PARITY"

missing_basic_hook="$TMP_DIR/missing-basic-hook"
cp -R "$parity" "$missing_basic_hook"
sed -i.bak '/check-yaml/d' "$missing_basic_hook/.pre-commit-config.yaml"
rm "$missing_basic_hook/.pre-commit-config.yaml.bak"
set +e
missing_basic_hook_output=$($SCRIPT "$missing_basic_hook" 2>&1)
missing_basic_hook_status=$?
set -e
[[ $missing_basic_hook_status -eq 1 ]] || {
  printf 'Expected missing basic hook to exit 1, got %s\n%s\n' "$missing_basic_hook_status" "$missing_basic_hook_output" >&2
  exit 1
}
assert_contains "$missing_basic_hook_output" "FAIL: pre-commit quality chain"

missing_ruff_hook="$TMP_DIR/missing-ruff-hook"
cp -R "$parity" "$missing_ruff_hook"
sed -i.bak 's/- id: ruff-check/- id: missing-ruff-check/' "$missing_ruff_hook/.pre-commit-config.yaml"
rm "$missing_ruff_hook/.pre-commit-config.yaml.bak"
set +e
missing_ruff_hook_output=$($SCRIPT "$missing_ruff_hook" 2>&1)
missing_ruff_hook_status=$?
set -e
[[ $missing_ruff_hook_status -eq 1 ]] || {
  printf 'Expected missing Ruff hook to exit 1, got %s\n%s\n' "$missing_ruff_hook_status" "$missing_ruff_hook_output" >&2
  exit 1
}
assert_contains "$missing_ruff_hook_output" "FAIL: pre-commit quality chain"

ruff_without_fix="$TMP_DIR/ruff-without-fix"
cp -R "$parity" "$ruff_without_fix"
sed -i.bak 's/ruff check --fix --force-exclude/ruff check --force-exclude/' "$ruff_without_fix/.pre-commit-config.yaml"
rm "$ruff_without_fix/.pre-commit-config.yaml.bak"
set +e
ruff_without_fix_output=$($SCRIPT "$ruff_without_fix" 2>&1)
ruff_without_fix_status=$?
set -e
[[ $ruff_without_fix_status -eq 1 ]] || {
  printf 'Expected Ruff hook without fix mode to exit 1, got %s\n%s\n' "$ruff_without_fix_status" "$ruff_without_fix_output" >&2
  exit 1
}
assert_contains "$ruff_without_fix_output" "FAIL: pre-commit quality chain"

ruff_mirror="$TMP_DIR/ruff-mirror"
cp -R "$parity" "$ruff_mirror"
sed -i.bak 's|- repo: local|- repo: https://github.com/astral-sh/ruff-pre-commit|' "$ruff_mirror/.pre-commit-config.yaml"
rm "$ruff_mirror/.pre-commit-config.yaml.bak"
assert_preflight_rejected "$ruff_mirror" "ruff-mirror" "Ruff mirror"

ruff_without_frozen="$TMP_DIR/ruff-without-frozen"
cp -R "$parity" "$ruff_without_frozen"
sed -i.bak 's/uv run --frozen ruff/uv run ruff/g' "$ruff_without_frozen/.pre-commit-config.yaml"
rm "$ruff_without_frozen/.pre-commit-config.yaml.bak"
assert_preflight_rejected "$ruff_without_frozen" "ruff-frozen" "non-frozen Ruff hooks"

ruff_without_force_exclude="$TMP_DIR/ruff-without-force-exclude"
cp -R "$parity" "$ruff_without_force_exclude"
sed -i.bak 's/ --force-exclude//g' "$ruff_without_force_exclude/.pre-commit-config.yaml"
rm "$ruff_without_force_exclude/.pre-commit-config.yaml.bak"
assert_preflight_rejected \
  "$ruff_without_force_exclude" "ruff-force-exclude" "Ruff hooks without force-exclude"

legacy_hook_language="$TMP_DIR/legacy-hook-language"
cp -R "$parity" "$legacy_hook_language"
sed -i.bak 's/language: unsupported/language: system/g' "$legacy_hook_language/.pre-commit-config.yaml"
rm "$legacy_hook_language/.pre-commit-config.yaml.bak"
assert_preflight_rejected "$legacy_hook_language" "ruff-language" "legacy hook language"

parallel_ruff="$TMP_DIR/parallel-ruff"
cp -R "$parity" "$parallel_ruff"
sed -i.bak 's/require_serial: true/require_serial: false/g' "$parallel_ruff/.pre-commit-config.yaml"
rm "$parallel_ruff/.pre-commit-config.yaml.bak"
assert_preflight_rejected "$parallel_ruff" "ruff-serial" "parallel Ruff hooks"

wrong_hook_order="$TMP_DIR/wrong-hook-order"
cp -R "$parity" "$wrong_hook_order"
move_uv_repo_after_local "$wrong_hook_order/.pre-commit-config.yaml"
assert_preflight_rejected "$wrong_hook_order" "ruff-order" "wrong uv/Ruff order"

missing_large_file_hook="$TMP_DIR/missing-large-file-hook"
cp -R "$parity" "$missing_large_file_hook"
sed -i.bak 's/check-added-large-files/missing-check-added-large-files/' "$missing_large_file_hook/.pre-commit-config.yaml"
rm "$missing_large_file_hook/.pre-commit-config.yaml.bak"
assert_preflight_rejected \
  "$missing_large_file_hook" "check-added-large-files" "missing large-file hook"

missing_zizmor="$TMP_DIR/missing-zizmor"
cp -R "$parity" "$missing_zizmor"
sed -i.bak 's|zizmorcore/zizmor-pre-commit|zizmorcore/missing-zizmor|' "$missing_zizmor/.pre-commit-config.yaml"
rm "$missing_zizmor/.pre-commit-config.yaml.bak"
assert_preflight_rejected "$missing_zizmor" "zizmor" "missing zizmor hook"

noop_mypy_hook="$TMP_DIR/noop-mypy-hook"
cp -R "$parity" "$noop_mypy_hook"
sed -i.bak 's/entry: uv run --frozen mypy app/entry: true/' "$noop_mypy_hook/.pre-commit-config.yaml"
rm "$noop_mypy_hook/.pre-commit-config.yaml.bak"
set +e
noop_mypy_output=$($SCRIPT "$noop_mypy_hook" 2>&1)
noop_mypy_status=$?
set -e
[[ $noop_mypy_status -eq 1 ]] || {
  printf 'Expected no-op mypy hook to exit 1, got %s\n%s\n' "$noop_mypy_status" "$noop_mypy_output" >&2
  exit 1
}
assert_contains "$noop_mypy_output" "FAIL: pre-commit quality chain"

missing_commit_msg_type="$TMP_DIR/missing-commit-msg-type"
cp -R "$parity" "$missing_commit_msg_type"
sed -i.bak 's/, commit-msg//' "$missing_commit_msg_type/.pre-commit-config.yaml"
rm "$missing_commit_msg_type/.pre-commit-config.yaml.bak"
set +e
missing_commit_msg_type_output=$($SCRIPT "$missing_commit_msg_type" 2>&1)
missing_commit_msg_type_status=$?
set -e
[[ $missing_commit_msg_type_status -eq 1 ]] || {
  printf 'Expected missing commit-msg install type to exit 1, got %s\n%s\n' "$missing_commit_msg_type_status" "$missing_commit_msg_type_output" >&2
  exit 1
}
assert_contains "$missing_commit_msg_type_output" "FAIL: pre-commit quality chain"

commented_commit_msg_type="$TMP_DIR/commented-commit-msg-type"
cp -R "$parity" "$commented_commit_msg_type"
sed -i.bak 's/default_install_hook_types: \[pre-commit, commit-msg\]/default_install_hook_types: [pre-commit] # commit-msg/' "$commented_commit_msg_type/.pre-commit-config.yaml"
rm "$commented_commit_msg_type/.pre-commit-config.yaml.bak"
set +e
commented_commit_msg_output=$($SCRIPT "$commented_commit_msg_type" 2>&1)
commented_commit_msg_status=$?
set -e
[[ $commented_commit_msg_status -eq 1 ]] || {
  printf 'Expected commented commit-msg type to exit 1, got %s\n%s\n' "$commented_commit_msg_status" "$commented_commit_msg_output" >&2
  exit 1
}
assert_contains "$commented_commit_msg_output" "FAIL: pre-commit quality chain"

fail_fast_true="$TMP_DIR/fail-fast-true"
cp -R "$parity" "$fail_fast_true"
{
  printf 'fail_fast: true\n'
  cat "$fail_fast_true/.pre-commit-config.yaml"
} >"$fail_fast_true/.pre-commit-config.yaml.tmp"
mv "$fail_fast_true/.pre-commit-config.yaml.tmp" "$fail_fast_true/.pre-commit-config.yaml"
assert_preflight_rejected "$fail_fast_true" "top-level-fail-fast" "fail_fast true"

mixed_case_fail_fast="$TMP_DIR/mixed-case-fail-fast"
cp -R "$parity" "$mixed_case_fail_fast"
{
  printf 'fail_fast: True\n'
  cat "$mixed_case_fail_fast/.pre-commit-config.yaml"
} >"$mixed_case_fail_fast/.pre-commit-config.yaml.tmp"
mv "$mixed_case_fail_fast/.pre-commit-config.yaml.tmp" "$mixed_case_fail_fast/.pre-commit-config.yaml"
assert_preflight_rejected \
  "$mixed_case_fail_fast" "top-level-fail-fast" "mixed-case fail_fast true"

missing_pytest="$TMP_DIR/missing-pytest"
cp -R "$parity" "$missing_pytest"
sed -i.bak '/"pytest==9\.\*",/d' "$missing_pytest/pyproject.toml"
rm "$missing_pytest/pyproject.toml.bak"
set +e
missing_pytest_output=$($SCRIPT "$missing_pytest" 2>&1)
missing_pytest_status=$?
set -e
[[ $missing_pytest_status -eq 1 ]] || {
  printf 'Expected missing pytest to exit 1, got %s\n%s\n' "$missing_pytest_status" "$missing_pytest_output" >&2
  exit 1
}
assert_contains "$missing_pytest_output" "FAIL: quality dependencies and tool configuration"

missing_pytest_randomly="$TMP_DIR/missing-pytest-randomly"
cp -R "$parity" "$missing_pytest_randomly"
sed -i.bak '/"pytest-randomly==3\.\*",/d' "$missing_pytest_randomly/pyproject.toml"
rm "$missing_pytest_randomly/pyproject.toml.bak"
set +e
missing_randomly_output=$($SCRIPT "$missing_pytest_randomly" 2>&1)
missing_randomly_status=$?
set -e
[[ $missing_randomly_status -eq 1 ]] || {
  printf 'Expected missing pytest-randomly to exit 1, got %s\n%s\n' "$missing_randomly_status" "$missing_randomly_output" >&2
  exit 1
}
assert_contains "$missing_randomly_output" "FAIL: quality dependencies and tool configuration"

misclassified_dev_tools="$TMP_DIR/misclassified-dev-tools"
cp -R "$parity" "$misclassified_dev_tools"
sed -i.bak 's|^dependencies = .*|dependencies = ["fastapi==0.135.*", "gunicorn==26.0.*", "commitizen==4.*", "mypy==1.*", "pip-audit==2.*", "pre-commit==4.*", "pytest==9.*", "pytest-cov==7.*", "ruff==0.*"]|' "$misclassified_dev_tools/pyproject.toml"
rm "$misclassified_dev_tools/pyproject.toml.bak"
awk '
  /^dev = \[/ { print "dev = []"; skip = 1; next }
  skip && /^\]/ { skip = 0; next }
  !skip { print }
' "$misclassified_dev_tools/pyproject.toml" >"$misclassified_dev_tools/pyproject.toml.tmp"
mv "$misclassified_dev_tools/pyproject.toml.tmp" "$misclassified_dev_tools/pyproject.toml"
set +e
misclassified_dev_output=$($SCRIPT "$misclassified_dev_tools" 2>&1)
misclassified_dev_status=$?
set -e
[[ $misclassified_dev_status -eq 1 ]] || {
  printf 'Expected runtime-classified dev tools to exit 1, got %s\n%s\n' "$misclassified_dev_status" "$misclassified_dev_output" >&2
  exit 1
}
assert_contains "$misclassified_dev_output" "FAIL: quality dependencies and tool configuration"

pipeline_without_bake="$TMP_DIR/pipeline-without-bake"
cp -R "$pipeline" "$pipeline_without_bake"
rm "$pipeline_without_bake/.github/workflows/check.yml"
rm "$pipeline_without_bake/docker-bake.hcl"
set +e
pipeline_without_bake_output=$($SCRIPT "$pipeline_without_bake" 2>&1)
pipeline_without_bake_status=$?
set -e
[[ $pipeline_without_bake_status -eq 1 ]] || {
  printf 'Expected missing bake definition to exit 1, got %s\n%s\n' "$pipeline_without_bake_status" "$pipeline_without_bake_output" >&2
  exit 1
}
assert_contains "$pipeline_without_bake_output" "FAIL: uv supply-chain updates and shared Python CI"

ungrouped_dependabot="$TMP_DIR/ungrouped-dependabot"
cp -R "$parity" "$ungrouped_dependabot"
cat >"$ungrouped_dependabot/.github/dependabot.yml" <<'EOF'
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
EOF
set +e
ungrouped_dependabot_output=$($SCRIPT "$ungrouped_dependabot" 2>&1)
ungrouped_dependabot_status=$?
set -e
[[ $ungrouped_dependabot_status -eq 1 ]] || {
  printf 'Expected ungrouped Dependabot updates to exit 1, got %s\n%s\n' "$ungrouped_dependabot_status" "$ungrouped_dependabot_output" >&2
  exit 1
}
assert_contains "$ungrouped_dependabot_output" "FAIL: uv supply-chain updates and shared Python CI"

mixed_dependabot="$TMP_DIR/mixed-dependabot"
cp -R "$parity" "$mixed_dependabot"
cat >"$mixed_dependabot/.github/dependabot.yml" <<'EOF'
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: monthly
  - package-ecosystem: npm
    directory: /
    schedule:
      interval: weekly
    groups:
      frontend-deps:
        patterns: ["*"]
EOF
set +e
mixed_dependabot_output=$($SCRIPT "$mixed_dependabot" 2>&1)
mixed_dependabot_status=$?
set -e
[[ $mixed_dependabot_status -eq 1 ]] || {
  printf 'Expected mixed Dependabot stanzas to exit 1, got %s\n%s\n' "$mixed_dependabot_status" "$mixed_dependabot_output" >&2
  exit 1
}
assert_contains "$mixed_dependabot_output" "FAIL: uv supply-chain updates and shared Python CI"

legacy="$TMP_DIR/legacy"
mkdir -p "$legacy"
printf 'fastapi==0.135.*\n' >"$legacy/requirements.in"
printf '[tool.ruff]\nline-length = 100\n' >"$legacy/pyproject.toml"

set +e
legacy_output=$($SCRIPT "$legacy" 2>&1)
legacy_status=$?
set -e
[[ $legacy_status -eq 1 ]] || {
  printf 'Expected divergent exit 1, got %s\n%s\n' "$legacy_status" "$legacy_output" >&2
  exit 1
}
assert_contains "$legacy_output" "FAIL: PEP 621 project and dependency groups"
assert_contains "$legacy_output" "FAIL: no legacy dependency or VERSION files"
assert_contains "$legacy_output" "VERDICT: DIVERGENT"

legacy_without_pyproject="$TMP_DIR/legacy-without-pyproject"
mkdir -p "$legacy_without_pyproject"
printf 'fastapi==0.135.*\n' >"$legacy_without_pyproject/requirements.in"
set +e
legacy_without_pyproject_output=$($SCRIPT "$legacy_without_pyproject" 2>&1)
legacy_without_pyproject_status=$?
set -e
[[ $legacy_without_pyproject_status -eq 1 ]] || {
  printf 'Expected requirements-only Python project to exit 1, got %s\n%s\n' "$legacy_without_pyproject_status" "$legacy_without_pyproject_output" >&2
  exit 1
}
assert_contains "$legacy_without_pyproject_output" "FAIL: PEP 621 project and dependency groups"
assert_contains "$legacy_without_pyproject_output" "VERDICT: DIVERGENT"

nonlayered_strict="$TMP_DIR/nonlayered-strict"
cp -R "$parity" "$nonlayered_strict"
rm "$nonlayered_strict/app"/*/__init__.py
sed -i.bak 's/app\.model\.\*/core.model.*/' "$nonlayered_strict/pyproject.toml"
rm "$nonlayered_strict/pyproject.toml.bak"
nonlayered_strict_output=$($SCRIPT "$nonlayered_strict")
assert_contains "$nonlayered_strict_output" "N/A: layered import contract"
assert_contains "$nonlayered_strict_output" "VERDICT: PARITY"

nonlayered_no_override="$TMP_DIR/nonlayered-no-override"
cp -R "$nonlayered_strict" "$nonlayered_no_override"
awk '
  /^\[\[tool.mypy.overrides\]\]$/ { skip = 1; next }
  skip && /^\[/ { skip = 0 }
  !skip { print }
' "$nonlayered_no_override/pyproject.toml" >"$nonlayered_no_override/pyproject.toml.tmp"
mv "$nonlayered_no_override/pyproject.toml.tmp" "$nonlayered_no_override/pyproject.toml"
set +e
nonlayered_no_override_output=$($SCRIPT "$nonlayered_no_override" 2>&1)
nonlayered_no_override_status=$?
set -e
[[ $nonlayered_no_override_status -eq 1 ]] || {
  printf 'Expected non-layered project without strict override to exit 1, got %s\n%s\n' "$nonlayered_no_override_status" "$nonlayered_no_override_output" >&2
  exit 1
}
assert_contains "$nonlayered_no_override_output" "FAIL: quality dependencies and tool configuration"
assert_contains "$nonlayered_no_override_output" "mypy-values"

global_strict="$TMP_DIR/global-strict"
cp -R "$parity" "$global_strict"
awk '
  /^\[\[tool.mypy.overrides\]\]$/ { skip = 1; next }
  skip && /^\[/ { skip = 0 }
  !skip {
    print
    if ($0 ~ /^warn_redundant_casts[[:space:]]*=/) {
      print "disallow_untyped_defs = true"
    }
  }
' "$global_strict/pyproject.toml" >"$global_strict/pyproject.toml.tmp"
mv "$global_strict/pyproject.toml.tmp" "$global_strict/pyproject.toml"
global_strict_output=$($SCRIPT "$global_strict")
assert_contains "$global_strict_output" "PASS: quality dependencies and tool configuration"
assert_contains "$global_strict_output" "VERDICT: PARITY"

layered_wrong_override="$TMP_DIR/layered-wrong-override"
cp -R "$parity" "$layered_wrong_override"
sed -i.bak 's/app\.model\.\*/core.model.*/' "$layered_wrong_override/pyproject.toml"
rm "$layered_wrong_override/pyproject.toml.bak"
set +e
layered_wrong_override_output=$($SCRIPT "$layered_wrong_override" 2>&1)
layered_wrong_override_status=$?
set -e
[[ $layered_wrong_override_status -eq 1 ]] || {
  printf 'Expected layered project without app.model override to exit 1, got %s\n%s\n' "$layered_wrong_override_status" "$layered_wrong_override_output" >&2
  exit 1
}
assert_contains "$layered_wrong_override_output" "mypy-values"

uv_pip_wheel="$TMP_DIR/uv-pip-wheel"
cp -R "$parity" "$uv_pip_wheel"
awk '
  { print }
  /^RUN uv sync --locked --no-dev --no-install-project$/ && !done {
    print "RUN uv pip install --python /app/.venv/bin/python /wheels/app.whl"
    print "# migrated from: pip install -r requirements.txt"
    done = 1
  }
' "$uv_pip_wheel/Dockerfile" >"$uv_pip_wheel/Dockerfile.tmp"
mv "$uv_pip_wheel/Dockerfile.tmp" "$uv_pip_wheel/Dockerfile"
uv_pip_wheel_output=$($SCRIPT "$uv_pip_wheel")
assert_contains "$uv_pip_wheel_output" "PASS: uv-native Docker dependency and quality stages"
assert_contains "$uv_pip_wheel_output" "VERDICT: PARITY"

raw_pip_install="$TMP_DIR/raw-pip-install"
cp -R "$parity" "$raw_pip_install"
awk '
  { print }
  /^RUN uv sync --locked --no-dev --no-install-project$/ && !done {
    print "RUN pip install requests"
    done = 1
  }
' "$raw_pip_install/Dockerfile" >"$raw_pip_install/Dockerfile.tmp"
mv "$raw_pip_install/Dockerfile.tmp" "$raw_pip_install/Dockerfile"
set +e
raw_pip_install_output=$($SCRIPT "$raw_pip_install" 2>&1)
raw_pip_install_status=$?
set -e
[[ $raw_pip_install_status -eq 1 ]] || {
  printf 'Expected raw pip install in Dockerfile to exit 1, got %s\n%s\n' "$raw_pip_install_status" "$raw_pip_install_output" >&2
  exit 1
}
assert_contains "$raw_pip_install_output" "pip-or-requirements"

ignored_lockfile="$TMP_DIR/ignored-lockfile"
cp -R "$parity" "$ignored_lockfile"
git -C "$ignored_lockfile" init -q 2>/dev/null
printf '*.lock\n' >"$ignored_lockfile/.gitignore"
set +e
ignored_lockfile_output=$($SCRIPT "$ignored_lockfile" 2>&1)
ignored_lockfile_status=$?
set -e
[[ $ignored_lockfile_status -eq 1 ]] || {
  printf 'Expected git-ignored uv.lock to exit 1, got %s\n%s\n' "$ignored_lockfile_status" "$ignored_lockfile_output" >&2
  exit 1
}
assert_contains "$ignored_lockfile_output" "uv-lock-git-ignored"

missing_python_pin="$TMP_DIR/missing-python-pin"
cp -R "$parity" "$missing_python_pin"
rm "$missing_python_pin/.python-version"
set +e
missing_python_pin_output=$($SCRIPT "$missing_python_pin" 2>&1)
missing_python_pin_status=$?
set -e
[[ $missing_python_pin_status -eq 1 ]] || {
  printf 'Expected missing .python-version to exit 1, got %s\n%s\n' "$missing_python_pin_status" "$missing_python_pin_output" >&2
  exit 1
}
assert_contains "$missing_python_pin_output" "python-version-pin"
assert_not_contains "$missing_python_pin_output" "No such file or directory"

exclude_matches_msg="$TMP_DIR/exclude-matches-msg"
cp -R "$parity" "$exclude_matches_msg"
{
  printf "exclude: '.git|.tox'\n"
  cat "$exclude_matches_msg/.pre-commit-config.yaml"
} >"$exclude_matches_msg/.pre-commit-config.yaml.tmp"
mv "$exclude_matches_msg/.pre-commit-config.yaml.tmp" "$exclude_matches_msg/.pre-commit-config.yaml"
set +e
exclude_matches_msg_output=$($SCRIPT "$exclude_matches_msg" 2>&1)
exclude_matches_msg_status=$?
set -e
[[ $exclude_matches_msg_status -eq 1 ]] || {
  printf 'Expected exclude matching COMMIT_EDITMSG to exit 1, got %s\n%s\n' "$exclude_matches_msg_status" "$exclude_matches_msg_output" >&2
  exit 1
}
assert_contains "$exclude_matches_msg_output" "top-level-exclude"

top_level_exclude="$TMP_DIR/top-level-exclude"
cp -R "$parity" "$top_level_exclude"
{
  printf "exclude: '^(\\\\.tox/|helm/)|\\\\.ipynb\$'\n"
  cat "$top_level_exclude/.pre-commit-config.yaml"
} >"$top_level_exclude/.pre-commit-config.yaml.tmp"
mv "$top_level_exclude/.pre-commit-config.yaml.tmp" "$top_level_exclude/.pre-commit-config.yaml"
assert_preflight_rejected \
  "$top_level_exclude" "top-level-exclude" "top-level exclusion that bypasses all hooks"

empty_top_level_exclude="$TMP_DIR/empty-top-level-exclude"
cp -R "$parity" "$empty_top_level_exclude"
{
  printf "exclude: ''\n"
  cat "$empty_top_level_exclude/.pre-commit-config.yaml"
} >"$empty_top_level_exclude/.pre-commit-config.yaml.tmp"
mv \
  "$empty_top_level_exclude/.pre-commit-config.yaml.tmp" \
  "$empty_top_level_exclude/.pre-commit-config.yaml"
assert_preflight_rejected \
  "$empty_top_level_exclude" "top-level-exclude" "empty top-level exclusion"

docker_context="$TMP_DIR/docker-context"
cp -R "$parity" "$docker_context"
mkdir -p "$docker_context/env-config" "$docker_context/tests/unit"
printf 'PLANT: AAA\n' >"$docker_context/env-config/dev.yaml"
printf 'ENV_CONFIG_DIR = "env-config"\n' >"$docker_context/tests/unit/test_env_config.py"
printf 'env-config\n' >"$docker_context/.dockerignore"
set +e
docker_context_output=$($SCRIPT "$docker_context" 2>&1)
docker_context_status=$?
set -e
[[ $docker_context_status -eq 1 ]] || {
  printf 'Expected excluded Docker test context to exit 1, got %s\n%s\n' "$docker_context_status" "$docker_context_output" >&2
  exit 1
}
assert_contains "$docker_context_output" "test-context-excludes-env-config"

# Only a string literal naming the directory counts. Prose in a docstring does not read a file.
prose_env_config="$TMP_DIR/prose-env-config"
cp -R "$parity" "$prose_env_config"
mkdir -p "$prose_env_config/env-config" "$prose_env_config/tests/unit"
printf 'PLANT: AAA\n' >"$prose_env_config/env-config/dev.yaml"
printf '"""The default env-config state before users provision anything."""\n' \
  >"$prose_env_config/tests/unit/test_env_config.py"
printf 'env-config\n' >>"$prose_env_config/.dockerignore"
prose_env_config_output=$($SCRIPT "$prose_env_config")
assert_not_contains "$prose_env_config_output" "test-context-excludes-env-config"
assert_contains "$prose_env_config_output" "VERDICT: PARITY"

missing_context_exclusions="$TMP_DIR/missing-context-exclusions"
cp -R "$parity" "$missing_context_exclusions"
sed -i.bak '/^\.coverage$/d' "$missing_context_exclusions/.dockerignore"
rm "$missing_context_exclusions/.dockerignore.bak"
set +e
missing_context_output=$($SCRIPT "$missing_context_exclusions" 2>&1)
missing_context_status=$?
set -e
[[ $missing_context_status -eq 1 ]] || {
  printf 'Expected missing Docker context exclusions to exit 1, got %s\n%s\n' "$missing_context_status" "$missing_context_output" >&2
  exit 1
}
assert_contains "$missing_context_output" "FAIL: bounded Docker build context"

native_context="$TMP_DIR/native-context"
cp -R "$parity" "$native_context"
mkdir -p "$native_context/crates/native"
printf '[package]\nname = "native"\nversion = "0.1.0"\n' >"$native_context/crates/native/Cargo.toml"
set +e
native_context_output=$($SCRIPT "$native_context" 2>&1)
native_context_status=$?
set -e
[[ $native_context_status -eq 1 ]] || {
  printf 'Expected native target omission to exit 1, got %s\n%s\n' "$native_context_status" "$native_context_output" >&2
  exit 1
}
assert_contains "$native_context_output" "native-target"
printf 'target\n' >>"$native_context/.dockerignore"
native_context_fixed_output=$($SCRIPT "$native_context")
assert_contains "$native_context_fixed_output" "PASS: bounded Docker build context"
assert_contains "$native_context_fixed_output" "VERDICT: PARITY"

unsupported="$TMP_DIR/unsupported"
mkdir -p "$unsupported"
printf '{"name":"frontend"}\n' >"$unsupported/package.json"

set +e
unsupported_output=$($SCRIPT "$unsupported" 2>&1)
unsupported_status=$?
set -e
[[ $unsupported_status -eq 2 ]] || {
  printf 'Expected unsupported exit 2, got %s\n%s\n' "$unsupported_status" "$unsupported_output" >&2
  exit 1
}
assert_contains "$unsupported_output" "ERROR: no Python project found"

skill_content=$(<"$(dirname "$SCRIPT")/../SKILL.md")
assert_contains "$skill_content" "After all work and verification succeed, scan the entire target"
assert_contains "$skill_content" "Conda and any legacy Python environment, interpreter, dependency, or tool-handling practice"
assert_contains "$skill_content" 'Preserve stack-required `.venv` and `uv` configuration'
assert_contains "$skill_content" "inventory its effective triggers, commands, build arguments, secrets, explicit resource/cache names, and every Dockerfile it can select"
assert_contains "$skill_content" "Classify the CI as native orchestration, a cache-only Bake check, or an image-producing Bake pipeline"
assert_contains "$skill_content" "Detect overlapping feature/deploy push triggers"

stack_content=$(<"$(dirname "$SCRIPT")/../../../shared/conventions/python/stack.md")
assert_contains "$stack_content" 'explicit tag plus manifest digest'
assert_contains "$stack_content" 'each registry cache location has one `cache-to` writer'
assert_contains "$stack_content" 'effective command must preserve the same gate'
assert_contains "$stack_content" 'hashes the full repository/runner scope'
assert_contains "$stack_content" 'bounds worker storage with GC'
assert_contains "$stack_content" 'Native Rust projects exclude local `target/` trees'
assert_contains "$stack_content" '`--force-exclude`'
assert_contains "$stack_content" '`language: unsupported`'

printf 'align-stack Python preflight tests passed\n'
