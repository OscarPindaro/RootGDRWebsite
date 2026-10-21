#!/usr/bin/env bash
set -uo pipefail

if [[ $# -gt 1 ]]; then
  printf 'Usage: %s [project-or-repository-root]\n' "${0##*/}" >&2
  exit 2
fi

target=${1:-.}
if [[ ! -d "$target" ]]; then
  printf 'ERROR: directory not found: %s\n' "$target" >&2
  exit 2
fi

target=$(cd "$target" && pwd)

is_python_root() {
  local root=$1
  [[ -f "$root/pyproject.toml" || -f "$root/requirements.in" ||
    -f "$root/requirements-dev.in" || -f "$root/requirements.txt" ||
    -f "$root/requirements-dev.txt" ]]
}

if is_python_root "$target"; then
  project_root=$target
elif is_python_root "$target/backend"; then
  project_root="$target/backend"
else
  printf 'ERROR: no Python project found under %s\n' "$target" >&2
  exit 2
fi

repo_root=$project_root
if git_root=$(git -C "$project_root" rev-parse --show-toplevel 2>/dev/null); then
  repo_root=$git_root
elif [[ "${project_root##*/}" == "backend" ]]; then
  repo_root=${project_root%/backend}
fi

pyproject="$project_root/pyproject.toml"
makefile="$project_root/Makefile"
dockerfile="$project_root/Dockerfile"
precommit="$repo_root/.pre-commit-config.yaml"
failures=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; failures=$((failures + 1)); }
na() { printf 'N/A: %s\n' "$1"; }

file_has() {
  local file=$1 pattern=$2
  [[ -f "$file" ]] && grep -Eq "$pattern" "$file"
}

toml_section() {
  local file=$1 section=$2
  awk -v header="[$section]" '
    $0 == header { in_section = 1; next }
    in_section && /^\[/ { exit }
    in_section { print }
  ' "$file" 2>/dev/null
}

toml_value_block() {
  local file=$1 section=$2 key=$3
  awk -v header="[$section]" -v key="$key" '
    $0 == header { in_section = 1; next }
    in_section && /^\[/ { exit }
    in_section && $0 ~ "^" key "[[:space:]]*=" { in_value = 1 }
    in_value { print }
    in_value && /\][[:space:]]*,?[[:space:]]*(#.*)?$/ { exit }
  ' "$file" 2>/dev/null
}

mypy_strict_override() {
  local file=$1 module_pattern=$2
  awk -v module_pattern="$module_pattern" '
    function check_block() {
      if (block ~ module_pattern && block ~ /disallow_untyped_defs[[:space:]]*=[[:space:]]*true/) found = 1
      block = ""
    }
    /^\[\[tool\.mypy\.overrides\]\]$/ { check_block(); in_override = 1; next }
    in_override && /^\[/ { check_block(); in_override = 0 }
    in_override { block = block "\n" $0 }
    END { check_block(); exit(found ? 0 : 1) }
  ' "$file" 2>/dev/null
}

import_layers_contract_ok() {
  awk '
    function check_block() {
      if (block ~ /type[[:space:]]*=[[:space:]]*"layers"/ &&
          block ~ /app\.api/ && block ~ /app\.service/ &&
          block ~ /app\.repository/ && block ~ /app\.model/) found = 1
      block = ""
    }
    /^\[\[tool\.importlinter\.contracts\]\]$/ { check_block(); in_contract = 1; next }
    in_contract && /^\[/ { check_block(); in_contract = 0 }
    in_contract { block = block "\n" $0 }
    END { check_block(); exit(found ? 0 : 1) }
  ' "$1" 2>/dev/null
}

project_config=$(toml_section "$pyproject" project)
uv_config=$(toml_section "$pyproject" tool.uv)
commitizen_config=$(toml_section "$pyproject" tool.commitizen)

# Project kind. A library is a distributable package: it declares a [build-system],
# ships no service Dockerfile, and is not marked package=false. A service ships a
# container and pins one Python. Library mode relaxes the service-only invariants
# (package=false, single-version Python pin, run/docker-build targets, Docker stages).
is_library=false
if [[ ! -f "$dockerfile" ]] &&
  file_has "$pyproject" '^\[build-system\]' &&
  ! grep -Eq '^package[[:space:]]*=[[:space:]]*false' <<<"$uv_config"; then
  is_library=true
fi
project_dependencies=$(toml_value_block "$pyproject" project dependencies)
runtime_dependencies_ok=true
runtime_dependency_count=0
runtime_uses_ssh=false
while IFS= read -r quoted; do
  dependency=${quoted#\"}
  dependency=${dependency%\"}
  runtime_dependency_count=$((runtime_dependency_count + 1))
  if [[ "$dependency" == *' @ '* ]]; then
    [[ "$dependency" =~ @[vV]?[0-9]+\.[0-9]+\.[0-9]+$ ]] || runtime_dependencies_ok=false
    [[ "$dependency" == *'git+ssh://'* ]] && runtime_uses_ssh=true
  elif ! [[ "$dependency" =~ ^[A-Za-z0-9_.-]+(\[[^]]+\])?[[:space:]]*(==|~=|\>=|\<=|!=|\>|\<).+ ]]; then
    runtime_dependencies_ok=false
  fi
done < <(sed 's/[[:space:]]*#.*$//' <<<"$project_dependencies" | grep -oE '"[^"]+"' || true)
[[ $runtime_dependency_count -gt 0 ]] || runtime_dependencies_ok=false
# A library must declare a [build-system] (it is built/installed as a package); a
# service must set [tool.uv] package = false (it is run, not distributed).
if [[ $is_library == true ]]; then
  packaging_ok=$(file_has "$pyproject" '^\[build-system\]' && echo true || echo false)
else
  packaging_ok=$(grep -Eq '^package[[:space:]]*=[[:space:]]*false([[:space:]]*#.*)?$' <<<"$uv_config" && echo true || echo false)
fi
if grep -Eq '^dependencies[[:space:]]*=' <<<"$project_config" &&
  [[ $runtime_dependencies_ok == true ]] &&
  file_has "$pyproject" '^\[dependency-groups\]$' &&
  grep -Eq '^dev[[:space:]]*=' <<<"$(toml_section "$pyproject" dependency-groups)" &&
  [[ $packaging_ok == true ]]; then
  pass 'PEP 621 project and dependency groups'
else
  fail 'PEP 621 project and dependency groups'
fi

python_pin=$(cat "$project_root/.python-version" 2>/dev/null | tr -d '[:space:]')
lock_issues=()
{ [[ -s "$project_root/uv.lock" ]] &&
  file_has "$project_root/uv.lock" '^version[[:space:]]*=' &&
  file_has "$project_root/uv.lock" '^\[\[package\]\]$' &&
  file_has "$project_root/uv.lock" '^source[[:space:]]*='; } || lock_issues+=('resolved-lock')
# The pinned minor is the project's choice (newest stable with full wheel coverage),
# so these checks prove the declarations agree with each other, not that they equal
# a literal version. A hard-coded version here fails every correct project the day
# the pin moves.
if [[ ! "$python_pin" =~ ^3\.[0-9]+$ ]]; then
  lock_issues+=('python-version-pin')
  python_next=''
else
  python_next="3.$((${python_pin#3.} + 1))"
fi
if [[ $is_library == true ]]; then
  # A library declares a floor (>=X.Y) so consumers on older minors can install it;
  # the lock resolves for that same floor. The dev interpreter still pins one minor.
  file_has "$project_root/uv.lock" '^requires-python[[:space:]]*=[[:space:]]*">=3\.[0-9]+' ||
    lock_issues+=('lock-requires-python')
  grep -Eq '^requires-python[[:space:]]*=[[:space:]]*">=3\.[0-9]+' <<<"$project_config" ||
    lock_issues+=('project-requires-python')
elif [[ -n "$python_next" ]]; then
  file_has "$project_root/uv.lock" \
    "^requires-python[[:space:]]*=[[:space:]]*\"(==${python_pin//./\\.}\\.\\*|>=${python_pin//./\\.},<${python_next//./\\.})\"" ||
    lock_issues+=('lock-requires-python')
  grep -Eq "^requires-python[[:space:]]*=[[:space:]]*\">=${python_pin//./\\.},<${python_next//./\\.}\"" <<<"$project_config" ||
    lock_issues+=('project-requires-python')
fi
git -C "$project_root" check-ignore -q uv.lock 2>/dev/null && lock_issues+=('uv-lock-git-ignored')
if [[ ${#lock_issues[@]} -eq 0 ]]; then
  pass "uv lockfile and Python ${python_pin:-?} pin"
else
  fail "uv lockfile and Python ${python_pin:-?} pin (${lock_issues[*]})"
fi

legacy_files=()
for pattern in requirements.in requirements-dev.in requirements.txt requirements-dev.txt VERSION; do
  [[ -e "$project_root/$pattern" ]] && legacy_files+=("$pattern")
done
if [[ ${#legacy_files[@]} -eq 0 ]]; then
  pass 'no legacy dependency or VERSION files'
else
  fail "no legacy dependency or VERSION files (found: ${legacy_files[*]})"
fi

# The hosting tier is declared in the service README at creation, so the choice has a
# record rather than drifting. A library ships no service and declares no tier.
if [[ $is_library == true ]]; then
  na 'hosting tier declared in the README (library: ships no service)'
elif [[ ! -f "$dockerfile" ]]; then
  # Neither a container nor a package: a tooling or test repository deploys nothing,
  # so it has no tier to declare. Treating "not a library" as "must be a service"
  # failed such a repository for a state it cannot reach.
  na 'hosting tier declared in the README (deploys no service)'
elif grep -Eqi '^[[:space:]]*(\*\*)?hosting tier(\*\*)?:[[:space:]]*(velocity|cloud)' \
  "$project_root/README.md" "$repo_root/README.md" 2>/dev/null; then
  pass 'hosting tier declared in the README'
else
  fail 'hosting tier declared in the README'
fi

# Schema ownership. Only meaningful when the project actually talks to PostgreSQL
# through SQLAlchemy — a library or a service with no database is N/A, not failing.
if [[ $is_library == true ]]; then
  na 'schema owned by Alembic (library: owns no deployed schema)'
elif grep -Eqi '"sqlalchemy[><=~\[]' <<<"$project_config"; then
  schema_issues=()
  grep -Eqi '"alembic[><=~\[]' <<<"$project_config" || schema_issues+=('alembic-dependency')
  [[ -f "$project_root/alembic.ini" || -d "$project_root/alembic" ]] || schema_issues+=('alembic-revisions')
  # Idempotent numbered DDL was the previous convention and is now superseded:
  # two mechanisms describing one schema is the drift migrations exist to prevent.
  [[ -n $(find "$project_root" -maxdepth 2 -type d -name ddl 2>/dev/null | head -1) ]] &&
    schema_issues+=('legacy-ddl-directory')
  if [[ ${#schema_issues[@]} -eq 0 ]]; then
    pass 'schema owned by Alembic'
  else
    fail "schema owned by Alembic (${schema_issues[*]})"
  fi
else
  na 'schema owned by Alembic (no SQLAlchemy dependency)'
fi

layered=true
for layer in api service repository model; do
  [[ -n $(find "$project_root/app/$layer" -type f -name '*.py' 2>/dev/null | head -1) ]] || layered=false
done

dev_tools=(commitizen mypy pip-audit pre-commit pytest pytest-cov pytest-randomly ruff)
missing_tools=()
dev_group=$(awk '
  /^\[dependency-groups\][[:space:]]*$/ { in_groups = 1; next }
  /^\[/ { in_groups = 0 }
  in_groups && /^dev[[:space:]]*=/ { in_dev = 1 }
  in_dev { print }
  in_dev && /\][[:space:]]*,?[[:space:]]*(#.*)?$/ { exit }
' "$pyproject" 2>/dev/null)
for tool in "${dev_tools[@]}"; do
  grep -Eq "\"${tool}(\[[^]]+\])?[[:space:]]*(==|~=|>=|<=|!=|>|<|@)" <<<"$dev_group" ||
    missing_tools+=("$tool")
done
ruff_config=$(toml_section "$pyproject" tool.ruff)
ruff_lint=$(toml_section "$pyproject" tool.ruff.lint)
ruff_select=$(toml_value_block "$pyproject" tool.ruff.lint select)
ruff_ignore=$(toml_value_block "$pyproject" tool.ruff.lint ignore)
ruff_bugbear=$(toml_section "$pyproject" tool.ruff.lint.flake8-bugbear)
mypy_config=$(toml_section "$pyproject" tool.mypy)
pydantic_mypy=$(toml_section "$pyproject" tool.pydantic-mypy)
pytest_config=$(toml_section "$pyproject" tool.pytest.ini_options)
ruff_rules=(E W F I N UP B C4 SIM ASYNC S DTZ PT LOG G RET PTH TID FAST RUF PL)
missing_ruff=()
for rule in "${ruff_rules[@]}"; do
  grep -Eq "\"${rule}\"" <<<"$ruff_select" || missing_ruff+=("$rule")
done
ruff_values_ok=true
grep -Eq '^line-length[[:space:]]*=[[:space:]]*100([[:space:]]*#.*)?$' <<<"$ruff_config" || ruff_values_ok=false
grep -Eq '"E501"' <<<"$ruff_ignore" || ruff_values_ok=false
grep -Eq '"fastapi\.Depends"' <<<"$ruff_bugbear" || ruff_values_ok=false
grep -Eq '"TC([0-9]+)?"' <<<"$ruff_select" && ruff_values_ok=false
grep -Eq '^target-version[[:space:]]*=' <<<"$ruff_config" && ruff_values_ok=false
mypy_values_ok=true
# mypy must parse as the interpreter the project actually pins; pinning it lower makes
# mypy read newer installed stubs as the older version and abort.
grep -Eq "^python_version[[:space:]]*=[[:space:]]*\"${python_pin//./\\.}\"" <<<"$mypy_config" || mypy_values_ok=false
grep -Eq '^plugins[[:space:]]*=.*"pydantic\.mypy"' <<<"$mypy_config" || mypy_values_ok=false
grep -Eq '^warn_unused_ignores[[:space:]]*=[[:space:]]*true' <<<"$mypy_config" || mypy_values_ok=false
grep -Eq '^warn_redundant_casts[[:space:]]*=[[:space:]]*true' <<<"$mypy_config" || mypy_values_ok=false
if ! grep -Eq '^disallow_untyped_defs[[:space:]]*=[[:space:]]*true' <<<"$mypy_config"; then
  if [[ $layered == true ]]; then
    mypy_strict_override "$pyproject" 'app[.]model' || mypy_values_ok=false
  else
    mypy_strict_override "$pyproject" 'module[[:space:]]*=' || mypy_values_ok=false
  fi
fi
for key in init_forbid_extra init_typed warn_required_dynamic_aliases; do
  grep -Eq "^${key}[[:space:]]*=[[:space:]]*true" <<<"$pydantic_mypy" || mypy_values_ok=false
done
pytest_values_ok=true
grep -Eq '^addopts[[:space:]]*=.*not live' <<<"$pytest_config" || pytest_values_ok=false
grep -Eq "['\"]live:" <<<"$(toml_value_block "$pyproject" tool.pytest.ini_options markers)" ||
  pytest_values_ok=false
grep -Eq -- '--cov-fail-under' <<<"$pytest_config" && pytest_values_ok=false
grep -Eq '^testpaths[[:space:]]*=' <<<"$pytest_config" || pytest_values_ok=false
grep -Eq '"tests"' <<<"$pytest_config" || pytest_values_ok=false
quality_issues=()
[[ ${#missing_tools[@]} -eq 0 ]] || quality_issues+=("missing-tools: ${missing_tools[*]}")
[[ ${#missing_ruff[@]} -eq 0 ]] || quality_issues+=("missing-ruff-rules: ${missing_ruff[*]}")
[[ $ruff_values_ok == true ]] || quality_issues+=('ruff-values')
[[ $mypy_values_ok == true ]] || quality_issues+=('mypy-values')
[[ $pytest_values_ok == true ]] || quality_issues+=('pytest-values')
if [[ ${#quality_issues[@]} -eq 0 ]]; then
  pass 'quality dependencies and tool configuration'
else
  fail "quality dependencies and tool configuration ($(IFS=';'; printf '%s' "${quality_issues[*]}"))"
fi

if [[ $layered == true ]]; then
  importlinter_config=$(toml_section "$pyproject" tool.importlinter)
  if grep -Eq '^root_package[[:space:]]*=[[:space:]]*"app"' <<<"$importlinter_config" &&
    grep -Eq '^exclude_type_checking_imports[[:space:]]*=[[:space:]]*true' <<<"$importlinter_config" &&
    grep -Eq '"import-linter(\[[^]]+\])?[[:space:]]*(==|~=|>=|<=|!=|>|<|@)' <<<"$dev_group" &&
    import_layers_contract_ok "$pyproject"; then
    pass 'layered import contract'
  else
    fail 'layered import contract'
  fi
else
  na 'layered import contract (project does not expose all canonical layers)'
fi

target_recipe() {
  local file=$1 target_name=$2
  awk -v target_name="$target_name" '
    $0 ~ "^" target_name ":[^=]*" { in_target = 1; next }
    in_target && /^[^[:space:]#][^=]*:/ { exit }
    in_target { print }
  ' "$file" 2>/dev/null
}

target_recipe_has() {
  local file=$1 target_name=$2 pattern=$3
  target_recipe "$file" "$target_name" |
    awk '
      /^\t/ {
        line = $0
        sub(/^\t+[[:space:]]*/, "", line)
        if (line == "" || line ~ /^#/) next
        while (line ~ /^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+[[:space:]]+/) {
          sub(/^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+[[:space:]]+/, "", line)
        }
        if (line ~ /^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=/) next
        print line
      }
    ' |
    grep -Eq -- "$pattern"
}

# A library has nothing to run and ships no image: run/docker-build are service-only.
make_targets=(help install lock upgrade test lint cov audit bump push-tag clean)
[[ $is_library == false ]] && make_targets+=(run docker-build)
make_issues=()
for target_name in "${make_targets[@]}"; do
  file_has "$makefile" "^${target_name}:.*##" || make_issues+=("$target_name docs")
done
target_recipe_has "$makefile" help 'grep[[:space:]]+-E' || make_issues+=('help recipe')
target_recipe_has "$makefile" install 'uv sync --locked' || make_issues+=('install sync')
target_recipe_has "$makefile" install 'pre-commit install' || make_issues+=('install hooks')
file_has "$makefile" '^lock:[^#]*uv\.lock' || make_issues+=('lock dependency')
target_recipe_has "$makefile" 'uv\.lock' 'uv lock' || make_issues+=('lock recipe')
target_recipe_has "$makefile" upgrade 'uv lock --upgrade' || make_issues+=('upgrade recipe')
target_recipe_has "$makefile" test 'uv run .*pytest' || make_issues+=('test recipe')
target_recipe_has "$makefile" lint 'ruff check' || make_issues+=('lint ruff')
target_recipe_has "$makefile" lint 'ruff format --check' || make_issues+=('lint format')
target_recipe_has "$makefile" lint 'mypy' || make_issues+=('lint mypy')
if [[ $layered == true ]] && ! target_recipe_has "$makefile" lint 'lint-imports'; then
  make_issues+=('lint imports')
fi
target_recipe_has "$makefile" cov 'pytest.*--cov' || make_issues+=('coverage recipe')
target_recipe_has "$makefile" audit 'uv export' || make_issues+=('audit export')
target_recipe_has "$makefile" audit 'pip-audit' || make_issues+=('audit command')
[[ $is_library == true ]] ||
  target_recipe_has "$makefile" run 'uv run' || make_issues+=('run recipe')
target_recipe_has "$makefile" bump 'uv run .*cz bump' || make_issues+=('bump recipe')
target_recipe_has "$makefile" push-tag 'git push .*--follow-tags' || make_issues+=('push-tag recipe')
target_recipe_has "$makefile" clean 'find ' || make_issues+=('clean recipe')
if [[ $is_library == false ]]; then
  target_recipe_has "$makefile" docker-build 'docker (build|buildx)' || make_issues+=('docker-build recipe')
  if [[ $runtime_uses_ssh == true ]] && ! target_recipe_has "$makefile" docker-build '--ssh'; then
    make_issues+=('docker-build ssh')
  fi
fi
# A local Bake gate forwarding the agent (ssh=["default"]) needs --allow=ssh:
# Buildx >=0.17 blocks agent forwarding in non-interactive bake runs otherwise.
if [[ $runtime_uses_ssh == true ]] &&
  file_has "$makefile" '^docker-test:' &&
  target_recipe_has "$makefile" docker-test 'buildx bake' &&
  ! target_recipe_has "$makefile" docker-test '--allow[= ]ssh'; then
  make_issues+=('docker-test bake ssh entitlement')
fi
if [[ ${#make_issues[@]} -eq 0 ]] &&
  file_has "$makefile" '^\.DEFAULT_GOAL[[:space:]]*:=[[:space:]]*help'; then
  pass 'minimal self-documented Makefile command surface'
else
  fail "minimal self-documented Makefile command surface (missing: ${make_issues[*]:-default help})"
fi

yaml_repo_blocks() {
  local file=$1 needle=$2
  awk -v needle="$needle" '
    /^[[:space:]]*-[[:space:]]+repo:/ { in_repo = index($0, needle) > 0 }
    in_repo { print }
  ' "$file" 2>/dev/null
}

yaml_hook_block() {
  local id=$1
  awk -v id="$id" '
    /^[[:space:]]*-[[:space:]]+id:/ {
      if (in_hook) exit
      if ($0 ~ "id:[[:space:]]+" id "[[:space:]]*(#.*)?$") in_hook = 1
    }
    in_hook { print }
  '
}

yaml_hook_line_number() {
  local file=$1 id=$2
  awk -v id="$id" '
    /^[[:space:]]*-[[:space:]]+id:/ &&
      $0 ~ "id:[[:space:]]+" id "[[:space:]]*(#.*)?$" {
      print NR
      exit
    }
  ' "$file" 2>/dev/null
}

precommit_issues=()
grep -Eiq '^fail_fast:[[:space:]]*true[[:space:]]*(#.*)?$' "$precommit" 2>/dev/null &&
  precommit_issues+=(top-level-fail-fast)
grep -Eq '^exclude:' "$precommit" 2>/dev/null &&
  precommit_issues+=(top-level-exclude)
install_hook_types=$(awk '
  /^default_install_hook_types:/ { in_types = 1 }
  in_types && !/^default_install_hook_types:/ && /^[A-Za-z_]/ { exit }
  in_types { print }
' "$precommit" 2>/dev/null)
install_hook_types=$(sed 's/[[:space:]]*#.*$//' <<<"$install_hook_types")
install_hook_tokens=$(tr '[],' '\n' <<<"$install_hook_types" |
  sed -E 's/^default_install_hook_types:[[:space:]]*//; s/^[[:space:]]*-[[:space:]]*//; s/^[[:space:]]+//; s/[[:space:]]+$//' |
  sed '/^$/d')
grep -Fxq 'pre-commit' <<<"$install_hook_tokens" ||
  precommit_issues+=(pre-commit-install-type)
grep -Fxq 'commit-msg' <<<"$install_hook_tokens" ||
  precommit_issues+=(commit-msg-install-type)
[[ $(wc -l <<<"$install_hook_tokens" | tr -d ' ') -eq 2 ]] ||
  precommit_issues+=(unexpected-install-type)
basic_repo=$(yaml_repo_blocks "$precommit" pre-commit/pre-commit-hooks)
for hook_id in trailing-whitespace end-of-file-fixer check-toml check-yaml check-merge-conflict; do
  [[ -n $(yaml_hook_block "$hook_id" <<<"$basic_repo") ]] ||
    precommit_issues+=("$hook_id")
done
large_file_hook=$(yaml_hook_block check-added-large-files <<<"$basic_repo")
[[ -n "$large_file_hook" ]] || precommit_issues+=(check-added-large-files)
grep -Eq 'args:[[:space:]]*\[[^]]*--maxkb=1024[^]]*\]' <<<"$large_file_hook" ||
  precommit_issues+=(large-file-limit)
grep -Fq 'uv\.lock' <<<"$large_file_hook" ||
  precommit_issues+=(large-file-lock-exclude)
uv_repo=$(yaml_repo_blocks "$precommit" astral-sh/uv-pre-commit)
[[ -n $(yaml_hook_block uv-lock <<<"$uv_repo") ]] || precommit_issues+=(uv-lock)
commitizen_repo=$(yaml_repo_blocks "$precommit" commitizen-tools/commitizen)
commitizen_hook=$(yaml_hook_block commitizen <<<"$commitizen_repo")
[[ -n "$commitizen_hook" ]] || precommit_issues+=(commitizen)
grep -Eq 'stages:[[:space:]]*\[[[:space:]]*commit-msg[[:space:]]*\]' <<<"$commitizen_hook" ||
  precommit_issues+=(commitizen-stage)
ruff_mirror_repo=$(yaml_repo_blocks "$precommit" ruff-pre-commit)
if [[ -n $(yaml_hook_block ruff-check <<<"$ruff_mirror_repo") ||
  -n $(yaml_hook_block ruff <<<"$ruff_mirror_repo") ||
  -n $(yaml_hook_block ruff-format <<<"$ruff_mirror_repo") ]]; then
  precommit_issues+=(ruff-mirror)
fi
local_repos=$(yaml_repo_blocks "$precommit" 'repo: local')
ruff_check_hook=$(yaml_hook_block ruff-check <<<"$local_repos")
ruff_format_hook=$(yaml_hook_block ruff-format <<<"$local_repos")
ruff_check_entry=$(sed -nE 's/^[[:space:]]*entry:[[:space:]]*//p' <<<"$ruff_check_hook" | head -1)
ruff_format_entry=$(sed -nE 's/^[[:space:]]*entry:[[:space:]]*//p' <<<"$ruff_format_hook" | head -1)
[[ -n "$ruff_check_hook" ]] || precommit_issues+=(ruff)
[[ -n "$ruff_format_hook" ]] || precommit_issues+=(ruff-format)
[[ "$ruff_check_entry" == *'uv run --frozen ruff check'* &&
  "$ruff_format_entry" == *'uv run --frozen ruff format'* ]] ||
  precommit_issues+=(ruff-frozen)
[[ "$ruff_check_entry" == *'--fix'* ]] || precommit_issues+=(ruff-fix)
[[ "$ruff_check_entry" == *'--force-exclude'* &&
  "$ruff_format_entry" == *'--force-exclude'* ]] ||
  precommit_issues+=(ruff-force-exclude)
grep -Eq 'language:[[:space:]]*unsupported' <<<"$ruff_check_hook" &&
  grep -Eq 'language:[[:space:]]*unsupported' <<<"$ruff_format_hook" ||
  precommit_issues+=(ruff-language)
grep -Eq 'require_serial:[[:space:]]*true' <<<"$ruff_check_hook" &&
  grep -Eq 'require_serial:[[:space:]]*true' <<<"$ruff_format_hook" ||
  precommit_issues+=(ruff-serial)
uv_lock_line=$(yaml_hook_line_number "$precommit" uv-lock)
ruff_check_line=$(yaml_hook_line_number "$precommit" ruff-check)
ruff_format_line=$(yaml_hook_line_number "$precommit" ruff-format)
[[ -n "$uv_lock_line" && -n "$ruff_check_line" && -n "$ruff_format_line" &&
  "$uv_lock_line" -lt "$ruff_check_line" && "$ruff_check_line" -lt "$ruff_format_line" ]] ||
  precommit_issues+=(ruff-order)
mypy_hook=$(yaml_hook_block mypy <<<"$local_repos")
grep -Eq 'entry:[[:space:]].*uv run --frozen mypy([[:space:]]|$)' <<<"$mypy_hook" ||
  precommit_issues+=(mypy-entry)
grep -Eq 'language:[[:space:]]*unsupported' <<<"$mypy_hook" ||
  precommit_issues+=(mypy-language)
grep -Eq 'pass_filenames:[[:space:]]*false' <<<"$mypy_hook" ||
  precommit_issues+=(mypy-filenames)
if [[ $layered == true ]]; then
  import_hook=$(yaml_hook_block import-linter <<<"$local_repos")
  import_entry=$(sed -nE 's/^[[:space:]]*entry:[[:space:]]*//p' <<<"$import_hook" | head -1)
  [[ "$import_entry" == *'uv run --frozen lint-imports'* ]] ||
    precommit_issues+=(import-linter-entry)
  grep -Eq 'language:[[:space:]]*unsupported' <<<"$import_hook" ||
    precommit_issues+=(import-linter-language)
  grep -Eq 'pass_filenames:[[:space:]]*false' <<<"$import_hook" ||
    precommit_issues+=(import-linter-filenames)
fi
if [[ -n $(find "$repo_root/.github/workflows" -maxdepth 1 -type f \
  \( -name '*.yml' -o -name '*.yaml' \) -print -quit 2>/dev/null) ]]; then
  zizmor_repo=$(yaml_repo_blocks "$precommit" zizmorcore/zizmor-pre-commit)
  [[ -n $(yaml_hook_block zizmor <<<"$zizmor_repo") ]] ||
    precommit_issues+=(zizmor)
fi
if [[ ${#precommit_issues[@]} -eq 0 ]]; then
  pass 'pre-commit quality chain'
else
  fail "pre-commit quality chain (issues: ${precommit_issues[*]})"
fi

docker_stage() {
  local file=$1 stage=$2
  awk -v wanted="$stage" '
    /^FROM[[:space:]]/ {
      if (in_stage) exit
      for (i = 1; i < NF; i++) {
        if (toupper($i) == "AS" && tolower($(i + 1)) == tolower(wanted)) {
          in_stage = 1
          break
        }
      }
    }
    in_stage { print }
  ' "$file" 2>/dev/null
}

docker_stage_commands() {
  docker_stage "$1" "$2" | sed 's/[[:space:]]*#.*$//' | sed '/^[[:space:]]*$/d'
}

docker_run_instructions() {
  docker_stage_commands "$1" "$2" | awk '
    /^RUN[[:space:]]/ {
      instruction = $0
      in_run = $0 ~ /\\[[:space:]]*$/
      if (!in_run) print instruction
      next
    }
    in_run {
      instruction = instruction "\n" $0
      in_run = $0 ~ /\\[[:space:]]*$/
      if (!in_run) print instruction
    }
  '
}

# Coverage is measured, never gated: nothing fails on the number, so only --cov is required.
docker_stage_measures_coverage() {
  local file=$1 stage=$2 block
  block=$(docker_run_instructions "$file" "$stage")
  grep -Eq 'pytest' <<<"$block" &&
    grep -Eq -- '--cov(=|[[:space:]])' <<<"$block"
}

docker_stage_runs_gate() {
  local file=$1 stage=$2 pattern=$3
  docker_run_instructions "$file" "$stage" | grep -Eq "$pattern"
}

docker_external_bases_pinned() {
  local file=$1 line source source_lower alias alias_lower token index internal
  local from_count=0
  local -a aliases=() tokens=()

  while IFS= read -r line; do
    from_count=$((from_count + 1))
    read -ra tokens <<<"$line"
    index=1
    while [[ ${tokens[$index]:-} == --* ]]; do
      index=$((index + 1))
    done
    source=${tokens[$index]:-}
    [[ -n "$source" ]] || return 1
    source_lower=$(tr '[:upper:]' '[:lower:]' <<<"$source")

    internal=false
    if [[ "$source" == scratch ]]; then
      internal=true
    else
      for alias in "${aliases[@]-}"; do
        [[ -n "$alias" ]] || continue
        alias_lower=$(tr '[:upper:]' '[:lower:]' <<<"$alias")
        if [[ "$source_lower" == "$alias_lower" ]]; then
          internal=true
          break
        fi
      done
    fi
    if [[ $internal == false ]] &&
      ! [[ "$source" =~ ^[^@[:space:]]+@sha256:[0-9a-fA-F]{64}$ ]]; then
      return 1
    fi

    alias=""
    for ((index = index + 1; index < ${#tokens[@]}; index++)); do
      token=${tokens[$index]}
      if [[ "$token" == [Aa][Ss] ]] && ((index + 1 < ${#tokens[@]})); then
        alias=${tokens[$((index + 1))]}
        break
      fi
    done
    [[ -z "$alias" ]] || aliases+=("$alias")
  done < <(sed 's/[[:space:]]*#.*$//' "$file" 2>/dev/null | grep -Ei '^FROM[[:space:]]' || true)

  [[ $from_count -gt 0 ]]
}

docker_runtime=$(docker_run_instructions "$dockerfile" runtime-deps)
docker_dev=$(docker_run_instructions "$dockerfile" dev-deps)
docker_lint=$(docker_run_instructions "$dockerfile" lint)
docker_test=$(docker_stage_commands "$dockerfile" test)
docker_runtime_stage=api
docker_api=$(docker_stage_commands "$dockerfile" "$docker_runtime_stage")
if [[ -z "$docker_api" ]]; then
  docker_runtime_stage=runtime
  docker_api=$(docker_stage_commands "$dockerfile" "$docker_runtime_stage")
fi
docker_active=$(sed 's/[[:space:]]*#.*$//' "$dockerfile" 2>/dev/null |
  sed -E 's/uv[[:space:]]+pip[[:space:]]+install//g')
docker_issues=()
file_has "$dockerfile" '^FROM[[:space:]]+ghcr\.io/astral-sh/uv:[^[:space:]]+[[:space:]]+AS[[:space:]]+uv' ||
  docker_issues+=('uv-binary-stage')
file_has "$dockerfile" '^[[:space:]]*ENV[[:space:]]+VIRTUAL_ENV=/app/\.venv' || docker_issues+=('venv-env')
grep -Fq 'uv sync --locked --no-dev --no-install-project' <<<"$docker_runtime" || docker_issues+=('runtime-sync')
grep -Fq 'uv sync --locked --all-groups --no-install-project' <<<"$docker_dev" || docker_issues+=('dev-sync')
grep -Eq '^COPY[[:space:]]+--from=runtime-deps[[:space:]]+/app/\.venv[[:space:]]+/app/\.venv' <<<"$docker_api" ||
  docker_issues+=('api-venv-copy')
{ grep -Fq 'ruff check' <<<"$docker_lint" &&
  grep -Fq 'ruff format --check' <<<"$docker_lint" &&
  grep -Fq 'mypy' <<<"$docker_lint"; } || docker_issues+=('lint-chain')
docker_stage_measures_coverage "$dockerfile" test || docker_issues+=('test-coverage-measurement')
dockerignore="$repo_root/.dockerignore"
if [[ -d "$project_root/env-config" && -f "$dockerignore" ]] &&
  grep -Eq '^[[:space:]]*env-config/?[[:space:]]*(#.*)?$' "$dockerignore" &&
  grep -Eq '^COPY[[:space:]]+\.[[:space:]]+\.[[:space:]]*$' <<<"$docker_test" &&
  grep -rlqE --include='*.py' "['\"]env-config(/[^'\"]*)?['\"]" "$project_root/tests" >/dev/null 2>&1; then
  docker_issues+=('test-context-excludes-env-config')
fi
grep -Eq 'pip[[:space:]]+install|requirements[^[:space:]]*\.txt' <<<"$docker_active" &&
  docker_issues+=('pip-or-requirements')
if [[ $layered == true ]] && ! grep -Fq 'lint-imports' <<<"$docker_lint"; then
  docker_issues+=('lint-imports')
fi
if [[ $runtime_uses_ssh == true ]] && ! grep -Fq -- '--mount=type=ssh' <<<"$docker_runtime"; then
  docker_issues+=('runtime-ssh-mount')
fi
if [[ $is_library == true ]]; then
  na 'uv-native Docker dependency and quality stages (library: ships no container)'
elif [[ ! -f "$dockerfile" ]]; then
  na 'uv-native Docker dependency and quality stages (deploys no service)'
elif [[ ${#docker_issues[@]} -eq 0 ]]; then
  pass 'uv-native Docker dependency and quality stages'
else
  fail "uv-native Docker dependency and quality stages (${docker_issues[*]})"
fi

docker_context_issues=()
if file_has "$dockerfile" '^COPY[[:space:]]+\.[[:space:]]+\.'; then
  [[ -f "$dockerignore" ]] || docker_context_issues+=('missing-.dockerignore')
  file_has "$dockerignore" '^[[:space:]]*(\.venv|\*\*/\.venv)/?[[:space:]]*(#.*)?$' ||
    docker_context_issues+=('venv')
  file_has "$dockerignore" '^[[:space:]]*(\.coverage|\.coverage\.\*|\*\*/\.coverage)/?[[:space:]]*(#.*)?$' ||
    docker_context_issues+=('coverage')
  if [[ -n $(find "$project_root" -name Cargo.toml -type f -print -quit 2>/dev/null) ]]; then
    file_has "$dockerignore" '^[[:space:]]*(target|\*\*/target|crates/\*\*/target)/?[[:space:]]*(#.*)?$' ||
      docker_context_issues+=('native-target')
  fi
fi
if [[ $is_library == true ]]; then
  na 'bounded Docker build context (library: ships no container)'
elif [[ ! -f "$dockerfile" ]]; then
  na 'bounded Docker build context (deploys no service)'
elif [[ ${#docker_context_issues[@]} -eq 0 ]]; then
  pass 'bounded Docker build context'
else
  fail "bounded Docker build context (missing exclusions: ${docker_context_issues[*]})"
fi

docker_bases_pinned=true
dockerfile_count=0
repository_files() {
  if git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$repo_root" ls-files -z --cached --others --exclude-standard
  else
    find "$repo_root" -type f \
      -not -path '*/.git/*' \
      -not -path '*/.venv/*' \
      -not -path '*/.worktree-regression/*' -print0 2>/dev/null
  fi
}
while IFS= read -r -d '' candidate; do
  [[ -n "$candidate" ]] || continue
  [[ ${candidate##*/} == Dockerfile* ]] || continue
  [[ "$candidate" == /* ]] || candidate="$repo_root/$candidate"
  dockerfile_count=$((dockerfile_count + 1))
  docker_external_bases_pinned "$candidate" || docker_bases_pinned=false
done < <(repository_files)
[[ $dockerfile_count -gt 0 ]] || docker_bases_pinned=false

workflow_has_push() {
  local file=$1
  file_has "$file" '^on:[[:space:]]*$' && file_has "$file" '^[[:space:]]{2}push:'
}

workflow_push_section() {
  awk '
    /^  push:[[:space:]]*(#.*)?$/ { in_push = 1; print; next }
    in_push && /^  [A-Za-z0-9_-]+:/ { exit }
    in_push { print }
  ' "$1" 2>/dev/null
}

workflow_push_list() {
  local file=$1 key=$2
  workflow_push_section "$file" | awk -v key="$key" '
    $0 ~ "^    " key ":[[:space:]]*" {
      in_list = 1
      sub("^    " key ":[[:space:]]*", "")
      print
      next
    }
    in_list && /^    [A-Za-z0-9_-]+:/ { exit }
    in_list { print }
  '
}

workflow_push_allows_branch() {
  local file=$1 branch=$2 includes excludes normalized
  includes=$(workflow_push_list "$file" branches)
  excludes=$(workflow_push_list "$file" branches-ignore)
  normalized=$(tr "[],'\"" '     ' <<<"$excludes" | tr ',' ' ')
  grep -Eq "(^|[[:space:]-])${branch}([[:space:]#]|$)" <<<"$normalized" && return 1
  [[ -z "$includes" ]] && return 0
  normalized=$(tr "[],'\"" '     ' <<<"$includes" | tr ',' ' ')
  grep -Eq "(^|[[:space:]-])(${branch}|\\*|\\*\\*)([[:space:]#]|$)" <<<"$normalized"
}

hcl_block() {
  local file=$1 kind=$2 name=$3
  awk -v kind="$kind" -v name="$name" '
    $0 ~ "^[[:space:]]*" kind "[[:space:]]+\"" name "\"" { in_block = 1 }
    in_block { print }
    in_block && /}[[:space:]]*(#.*|\/\/.*)?$/ { exit }
  ' "$file" 2>/dev/null
}

hcl_active_block() {
  hcl_block "$1" "$2" "$3" | sed -E 's|//.*$||; s/[[:space:]]*#.*$//' | sed '/^[[:space:]]*$/d'
}

hcl_array_values() {
  local key=$1
  awk -v key="$key" '
    !in_value && $0 ~ key "[[:space:]]*=" {
      in_value = 1
      sub("^.*" key "[[:space:]]*=[[:space:]]*", "")
    }
    in_value { print }
    in_value && /\]/ { exit }
  ' | sed 's/].*/]/' | grep -oE '"[^"]*"' | tr -d '"'
}

hcl_default_value() {
  local file=$1 kind=$2 name=$3
  hcl_active_block "$file" "$kind" "$name" |
    sed -nE 's/.*default[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' |
    head -1
}

bake_target_cache_refs() {
  local file=$1 target=$2 block inherited parent
  block=$(hcl_active_block "$file" target "$target")
  hcl_array_values cache-to <<<"$block" | grep '^type=' || true
  while IFS= read -r inherited; do
    [[ -n "$inherited" ]] || continue
    parent=$(hcl_active_block "$file" target "$inherited")
    hcl_array_values cache-to <<<"$parent" | grep '^type=' || true
  done < <(hcl_array_values inherits <<<"$block")
}

bake_target_has_ssh() {
  local file=$1 target=$2 block inherited parent
  block=$(hcl_active_block "$file" target "$target")
  grep -Eq 'ssh[[:space:]]*=' <<<"$block" && return 0
  while IFS= read -r inherited; do
    [[ -n "$inherited" ]] || continue
    parent=$(hcl_active_block "$file" target "$inherited")
    grep -Eq 'ssh[[:space:]]*=' <<<"$parent" && return 0
  done < <(hcl_array_values inherits <<<"$block")
  return 1
}

bake_target_has_cacheonly_output() {
  local file=$1 target=$2 block inherited parent output outputs="" found=false
  block=$(hcl_active_block "$file" target "$target")
  outputs=$(hcl_array_values output <<<"$block")
  while IFS= read -r inherited; do
    [[ -n "$inherited" ]] || continue
    parent=$(hcl_active_block "$file" target "$inherited")
    outputs="${outputs}${outputs:+$'\n'}$(hcl_array_values output <<<"$parent")"
  done < <(hcl_array_values inherits <<<"$block")
  while IFS= read -r output; do
    [[ -n "$output" ]] || continue
    found=true
    [[ "$output" == 'type=cacheonly' ]] || return 1
  done <<<"$outputs"
  [[ $found == true ]]
}

bake_selection_members() {
  local file=$1 selectors=$2 selector block members
  while IFS= read -r selector; do
    selector=$(sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' <<<"$selector")
    [[ -n "$selector" ]] || continue
    block=$(hcl_active_block "$file" target "$selector")
    if [[ -n "$block" ]]; then
      printf '%s\n' "$selector"
      continue
    fi
    block=$(hcl_active_block "$file" group "$selector")
    [[ -n "$block" ]] || return 1
    members=$(hcl_array_values targets <<<"$block")
    [[ -n "$members" ]] || return 1
    printf '%s\n' "$members"
  done < <(tr ',' '\n' <<<"$selectors")
}

workflow_job_from_uses() {
  local file=$1 needle=$2
  awk -v needle="$needle" '
    found && /^[[:space:]]{2}[^[:space:]]/ { exit }
    $0 ~ /^[[:space:]]{4}uses:/ && index($0, needle) { found = 1 }
    found { print }
  ' "$file" 2>/dev/null
}

workflow_step_from_uses() {
  local file=$1 needle=$2
  awk -v needle="$needle" '
    found {
      current_indent = match($0, /[^[:space:]]/) - 1
      if ($0 ~ /^[[:space:]]*-[[:space:]]+(uses|name|run):/ && current_indent == step_indent) exit
      print
      next
    }
    $0 ~ /^[[:space:]]*-[[:space:]]+uses:/ && index($0, needle) {
      found = 1
      step_indent = match($0, /[^[:space:]]/) - 1
      print
    }
  ' "$file" 2>/dev/null
}

workflow_with_values() {
  awk '
    !in_with && /^[[:space:]]+with:[[:space:]]*$/ {
      in_with = 1
      with_indent = match($0, /[^[:space:]]/) - 1
      next
    }
    in_with && NF {
      current_indent = match($0, /[^[:space:]]/) - 1
      if (current_indent <= with_indent) exit
    }
    in_with { print }
  ' | sed 's/[[:space:]]*#.*$//' | sed '/^[[:space:]]*$/d'
}

workflow_input_value() {
  local values=$1 key=$2
  sed -nE "s/^[[:space:]]+${key}:[[:space:]]*['\"]?([^'\"[:space:]#]+)['\"]?[[:space:]]*(#.*)?$/\\1/p" <<<"$values" |
    head -1
}

project_cache_ecr_repo() {
  local root=$1 bakefile=$2 value workflow
  value=$(hcl_default_value "$bakefile" variable ECR_API)
  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
    return
  fi
  for workflow in "$root/.github/workflows/"*.yml "$root/.github/workflows/"*.yaml; do
    [[ -f "$workflow" ]] || continue
    value=$(sed -nE 's/^[[:space:]]+ecr_repo_override:[[:space:]]*["'"'"']?([^"'"'"'[:space:]#]+).*/\1/p' "$workflow" | head -1)
    if [[ -n "$value" && "$value" != *'${{'* ]]; then
      printf '%s\n' "$value"
      return
    fi
  done
}

derived_ecr_repo() {
  local root=$1 app_file app_name prefix repo_name
  app_file="$root/.github/app.yml"
  app_name=$(sed -nE 's/^app_name:[[:space:]]*["'"'"']?([^"'"'"'[:space:]#]+).*/\1/p' "$app_file" 2>/dev/null | head -1)
  prefix=$(sed -nE 's/^account:[[:space:]]*["'"'"']?([^"'"'"'[:space:]#]+).*/\1/p' "$app_file" 2>/dev/null | head -1)
  if [[ -z "$prefix" ]]; then
    repo_name=${root##*/}
    # TODO(circeus): map repo-name prefixes to AWS account prefixes here once the
    # naming convention exists, e.g.  myorg-*) prefix=myorg ;;
    case "$repo_name" in
      *) ;;
    esac
  fi
  [[ -n "$app_name" && -n "$prefix" ]] && printf '%s-%s\n' "$prefix" "$app_name"
}

check_python_contract_ok() {
  local values=$1 root=$2 default_dockerfile=$3 bakefile=$4 selected_file selected_path
  local test_command lint_command test_target lint_target resource_requested=false
  local declared_ecr derived_ecr override_ecr

  selected_file=$(workflow_input_value "$values" dockerfile)
  selected_file=${selected_file:-Dockerfile}
  if [[ "$selected_file" == /* ]]; then
    selected_path=$selected_file
  else
    selected_path="$root/$selected_file"
  fi
  [[ -f "$selected_path" ]] || selected_path=$default_dockerfile
  [[ -f "$selected_path" ]] || return 1
  test_target=$(workflow_input_value "$values" test_target)
  test_target=${test_target:-test}
  lint_target=$(workflow_input_value "$values" lint_target)
  lint_target=${lint_target:-lint}

  if [[ $(workflow_input_value "$values" skip_test) != true ]] &&
    docker_stage_runs_gate "$selected_path" "$test_target" 'pytest'; then
    grep -Eq 'RUN_TESTS_IN_BUILD[[:space:]]*=[[:space:]]*0' <<<"$values" || return 1
    grep -Eq 'RUN_TESTS_IN_BUILD' <<<"$(docker_stage_commands "$selected_path" "$test_target")" || return 1
    test_command=$(grep -E '^[[:space:]]+test_command:' <<<"$values" | head -1)
    grep -Eq -- '--cov(=|[[:space:]])' <<<"$test_command" || return 1
  fi

  if [[ $(workflow_input_value "$values" skip_lint) != true ]] &&
    docker_stage_runs_gate "$selected_path" "$lint_target" 'ruff[[:space:]]+check|mypy|lint-imports'; then
    grep -Eq 'RUN_LINT_IN_BUILD[[:space:]]*=[[:space:]]*0' <<<"$values" || return 1
    grep -Eq 'RUN_LINT_IN_BUILD' <<<"$(docker_stage_commands "$selected_path" "$lint_target")" || return 1
    lint_command=$(grep -E '^[[:space:]]+lint_command:' <<<"$values" | head -1)
    grep -Eq 'ruff[[:space:]]+check' <<<"$lint_command" || return 1
    grep -Eq 'ruff[[:space:]]+format[[:space:]]+--check' <<<"$lint_command" || return 1
    grep -Eq 'mypy' <<<"$lint_command" || return 1
    if [[ $layered == true ]]; then
      grep -Eq 'lint-imports' <<<"$lint_command" || return 1
    fi
  fi

  [[ $(workflow_input_value "$values" enable_ecr_cache) == true ]] && resource_requested=true
  [[ -n $(workflow_input_value "$values" ssh_deps) ]] && resource_requested=true
  [[ -n $(workflow_input_value "$values" aws_build_secrets) ]] && resource_requested=true
  [[ $resource_requested == true ]] || return 0

  declared_ecr=$(project_cache_ecr_repo "$root" "$bakefile")
  [[ -n "$declared_ecr" ]] || return 0
  derived_ecr=$(derived_ecr_repo "$root")
  override_ecr=$(workflow_input_value "$values" ecr_repo_override)
  if [[ -n "$derived_ecr" && "$declared_ecr" == "$derived_ecr" ]]; then
    [[ -z "$override_ecr" || "$override_ecr" == "$declared_ecr" ]]
  else
    [[ "$override_ecr" == "$declared_ecr" ]]
  fi
}

# The unquoted marker expression of a pytest command line; empty when it selects no marker.
pytest_marker_expression() {
  sed -nE "s/.*(^|[[:space:]])(-m|--markers)[[:space:]=]+('[^']*'|\"[^\"]*\"|[^[:space:]]+).*/\3/p" <<<"$1" |
    sed -E "s/^['\"]//; s/['\"]\$//"
}

native_python_check_ok() {
  local workflow=$1 active pytest_line pytest_args selection
  active=$(sed 's/[[:space:]]*#.*$//' "$workflow" | sed '/^[[:space:]]*$/d')
  grep -Eq 'uv[[:space:]]+run[[:space:]]+--frozen[^#]*pytest' <<<"$active" || return 1
  grep -Eq 'ruff[[:space:]]+check' <<<"$active" || return 1
  grep -Eq 'ruff[[:space:]]+format[[:space:]]+--check' <<<"$active" || return 1
  grep -Eq 'mypy' <<<"$active" || return 1
  grep -Eq -- '--cov(=|[[:space:]])' <<<"$active" || return 1
  if [[ $layered == true ]]; then
    grep -Eq 'lint-imports' <<<"$active" || return 1
  fi
  # A `-m` argument replaces the project's default filter, so any override must restate
  # `not live`: a CI runner owns no real external resource, and `-m ''` selects live tests.
  if grep -Eq '^addopts[[:space:]]*=.*not live' <<<"$pytest_config"; then
    while IFS= read -r pytest_line; do
      # Read only pytest's own arguments: `python -m pytest` carries an unrelated `-m`.
      pytest_args=${pytest_line#*pytest}
      grep -Eq -- '(^|[[:space:]])(-m|--markers)([[:space:]]|=)' <<<"$pytest_args" || continue
      selection=$(pytest_marker_expression "$pytest_args")
      grep -Eq '(^|[^A-Za-z0-9_])not[[:space:]]+live([^A-Za-z0-9_]|$)' <<<"$selection" || return 1
      # `live or not live` restates the exclusion and still selects every live test.
      if grep -Eq '(^|[^A-Za-z0-9_])live([^A-Za-z0-9_]|$)' \
        <<<"$(sed -E 's/not[[:space:]]+live//g' <<<"$selection")"; then
        return 1
      fi
    done < <(grep -E 'pytest' <<<"$active")
  fi
}

cache_only_bake_ok() {
  local values=$1 root=$2 default_bakefile=$3 selected_file selected_path selectors members member
  local target_block docker_target lint_count=0 test_count=0

  selected_file=$(workflow_input_value "$values" bake_file)
  selected_file=${selected_file:-docker-bake.hcl}
  if [[ "$selected_file" == /* ]]; then
    selected_path=$selected_file
  else
    selected_path="$root/$selected_file"
  fi
  [[ -f "$selected_path" ]] || selected_path=$default_bakefile
  [[ -f "$selected_path" ]] || return 1

  selectors=$(workflow_input_value "$values" bake_targets)
  selectors=${selectors:-lint,test}
  members=$(bake_selection_members "$selected_path" "$selectors") || return 1
  [[ -n "$members" ]] || return 1
  grep -Eq 'RUN_TESTS_IN_BUILD[[:space:]]*=[[:space:]]*0' <<<"$values" && return 1

  while IFS= read -r member; do
    [[ -n "$member" ]] || continue
    target_block=$(hcl_active_block "$selected_path" target "$member")
    [[ -n "$target_block" ]] || return 1
    bake_target_has_cacheonly_output "$selected_path" "$member" || return 1
    [[ -z $(bake_target_cache_refs "$selected_path" "$member") ]] || return 1
    if [[ $runtime_uses_ssh == true ]]; then
      bake_target_has_ssh "$selected_path" "$member" || return 1
    fi

    docker_target=$(sed -nE 's/.*target[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' <<<"$target_block" | head -1)
    docker_target=${docker_target:-$member}
    if [[ "$docker_target" == lint ]]; then
      lint_count=$((lint_count + 1))
    elif [[ "$docker_target" == test || "$docker_target" == test-e2e ]]; then
      test_count=$((test_count + 1))
      docker_stage_measures_coverage "$dockerfile" "$docker_target" || return 1
    else
      return 1
    fi
  done <<<"$members"

  [[ $lint_count -gt 0 && $test_count -gt 0 ]]
}

direct_persistent_bake_ok() {
  local workflow=$1 root=$2 bakefile=$3 setup_step setup_with selectors values
  grep -Eq '^[[:space:]]+runs-on:[[:space:]].*self-hosted' "$workflow" || return 1
  grep -Eq '(github[.]repository|GITHUB_REPOSITORY)' "$workflow" || return 1
  grep -Eq '(runner[.]name|RUNNER_NAME)' "$workflow" || return 1
  grep -Eq '(sha256sum|shasum[^#]*-a[[:space:]]+256)' "$workflow" || return 1
  setup_step=$(workflow_step_from_uses "$workflow" 'docker/setup-buildx-action@')
  [[ -n "$setup_step" ]] || return 1
  setup_with=$(workflow_with_values <<<"$setup_step")
  [[ $(workflow_input_value "$setup_with" keep-state) == true ]] || return 1
  grep -Eq 'buildkitd-config-inline:' <<<"$setup_step" || return 1
  grep -Eq 'gc[[:space:]]*=[[:space:]]*true' <<<"$setup_step" || return 1
  grep -Eq 'maxUsedSpace[[:space:]]*=' <<<"$setup_step" || return 1
  grep -Eq 'minFreeSpace[[:space:]]*=' <<<"$setup_step" || return 1
  workflow_has_direct_bake "$workflow" || return 1
  if [[ $runtime_uses_ssh == true ]]; then
    grep -Eq '^[[:space:]]+(-[[:space:]]+)?(run:[[:space:]]*)?docker[[:space:]]+buildx[[:space:]]+bake[^#]*(--allow[= ]ssh)' "$workflow" || return 1
  fi
  selectors=$(workflow_direct_bake_selectors "$workflow")
  [[ -n "$selectors" ]] || return 1
  values=$(printf '  bake_file: docker-bake.hcl\n  bake_targets: %s\n' "$selectors")
  cache_only_bake_ok "$values" "$root" "$bakefile"
}

workflow_has_direct_bake() {
  grep -Eq '^[[:space:]]+(-[[:space:]]+)?(run:[[:space:]]*)?docker[[:space:]]+buildx[[:space:]]+bake' "$1"
}

workflow_direct_bake_selectors() {
  local file=$1 line token skip_next=false selectors=""
  local -a tokens=()
  line=$(sed -nE 's/^[[:space:]]*(-[[:space:]]+)?(run:[[:space:]]*)?docker[[:space:]]+buildx[[:space:]]+bake[[:space:]]*(.*)$/\3/p' "$file" | head -1)
  read -ra tokens <<<"$line"
  for token in "${tokens[@]-}"; do
    if [[ $skip_next == true ]]; then
      skip_next=false
      continue
    fi
    case "$token" in
      -f | --file | --set) skip_next=true ;;
      --* | \\) ;;
      \#*) break ;;
      *) selectors="${selectors}${selectors:+,}${token}" ;;
    esac
  done
  printf '%s\n' "$selectors"
}

selected_bake_cache_ownership_ok() {
  local workflow_with=$1 bakefile=$2 bake_target_lines group group_block group_members member ref written_refs
  local selected=0
  [[ -f "$bakefile" ]] || return 1
  bake_target_lines=$(grep -E '^[[:space:]]+bake_target:' <<<"$workflow_with")
  [[ -n "$bake_target_lines" ]] || return 1

  while IFS= read -r group; do
    [[ -n "$group" ]] || continue
    grep -Eq "(^|[^A-Za-z0-9_-])${group}([^A-Za-z0-9_-]|$)" <<<"$bake_target_lines" || continue
    selected=$((selected + 1))
    written_refs=""
    group_block=$(hcl_active_block "$bakefile" group "$group")
    group_members=$(hcl_array_values targets <<<"$group_block")
    while IFS= read -r member; do
      [[ -n "$member" ]] || continue
      while IFS= read -r ref; do
        [[ -n "$ref" ]] || continue
        grep -Fqx -- "$ref" <<<"$written_refs" && return 1
        written_refs="${written_refs}${written_refs:+$'\n'}${ref}"
      done < <(bake_target_cache_refs "$bakefile" "$member")
    done <<<"$group_members"
  done < <(sed -nE 's/^[[:space:]]*group[[:space:]]+"([^"]+)".*/\1/p' "$bakefile")

  [[ $selected -gt 0 ]]
}

pipeline_bake_ok() {
  local workflow_with=$1 bakefile=$2 bake_target_lines group group_block group_members target_block test_target member
  local selected=0 test_count
  [[ -f "$bakefile" ]] || return 1
  grep -Eq '^[[:space:]]+use_bake:[[:space:]]*true[[:space:]]*$' <<<"$workflow_with" || return 1
  bake_target_lines=$(grep -E '^[[:space:]]+bake_target:' <<<"$workflow_with")
  [[ -n "$bake_target_lines" ]] || return 1

  while IFS= read -r group; do
    [[ -n "$group" ]] || continue
    if ! grep -Eq "(^|[^A-Za-z0-9_-])${group}([^A-Za-z0-9_-]|$)" <<<"$bake_target_lines"; then
      continue
    fi
    selected=$((selected + 1))
    group_block=$(hcl_active_block "$bakefile" group "$group")
    group_members=$(hcl_array_values targets <<<"$group_block")
    grep -Fxq 'lint' <<<"$group_members" || return 1
    target_block=$(hcl_active_block "$bakefile" target lint)
    grep -Eq 'target[[:space:]]*=[[:space:]]*"lint"' <<<"$target_block" || return 1

    test_count=0
    while IFS= read -r test_target; do
      [[ -n "$test_target" ]] || continue
      [[ "$test_target" == test || "$test_target" == test-e2e ]] || continue
      test_count=$((test_count + 1))
      target_block=$(hcl_active_block "$bakefile" target "$test_target")
      grep -Eq "target[[:space:]]*=[[:space:]]*\"${test_target}\"" <<<"$target_block" || return 1
      docker_stage_measures_coverage "$dockerfile" "$test_target" || return 1
    done <<<"$group_members"
    [[ $test_count -gt 0 ]] || return 1
    if [[ $runtime_uses_ssh == true ]]; then
      while IFS= read -r member; do
        [[ -n "$member" ]] || continue
        bake_target_has_ssh "$bakefile" "$member" || return 1
      done <<<"$group_members"
    fi
  done < <(sed -nE 's/^[[:space:]]*group[[:space:]]+"([^"]+)".*/\1/p' "$bakefile")

  [[ $selected -gt 0 ]]
}

dependabot="$repo_root/.github/dependabot.yml"
ci_ok=false
check_contract_seen=false
check_contract_ok=true
bake_cache_contract_seen=false
bake_cache_contract_ok=true
persistent_bake_contract_seen=false
persistent_bake_contract_ok=true
native_contract_seen=false
native_contract_ok=true
trigger_contract_ok=true
branch_validation_ok=true
check_workflows=()
deploy_workflows=()
bakefile="$repo_root/docker-bake.hcl"
[[ -f "$bakefile" ]] || bakefile="$project_root/docker-bake.hcl"
for workflow in "$repo_root/.github/workflows/"*.yml "$repo_root/.github/workflows/"*.yaml; do
  [[ -f "$workflow" ]] || continue
  workflow_has_push "$workflow" || continue
  check_job=$(workflow_job_from_uses "$workflow" 'check-python.yml@')
  if [[ -n "$check_job" ]]; then
    ci_ok=true
    check_contract_seen=true
    check_workflows+=("$workflow")
    check_with=$(workflow_with_values <<<"$check_job")
    check_python_contract_ok "$check_with" "$repo_root" "$dockerfile" "$bakefile" || check_contract_ok=false
  fi
  cache_bake_job=$(workflow_job_from_uses "$workflow" 'check-python-bake.yml@')
  if [[ -n "$cache_bake_job" ]]; then
    ci_ok=true
    persistent_bake_contract_seen=true
    check_workflows+=("$workflow")
    cache_bake_with=$(workflow_with_values <<<"$cache_bake_job")
    cache_only_bake_ok "$cache_bake_with" "$repo_root" "$bakefile" || persistent_bake_contract_ok=false
  fi
  if workflow_has_direct_bake "$workflow"; then
    ci_ok=true
    persistent_bake_contract_seen=true
    check_workflows+=("$workflow")
    direct_persistent_bake_ok "$workflow" "$repo_root" "$bakefile" || persistent_bake_contract_ok=false
  fi
  if [[ ${workflow##*/} == check*.y*ml ]] && grep -Eq 'uv[[:space:]]+run[[:space:]]+--frozen[^#]*pytest' "$workflow"; then
    ci_ok=true
    native_contract_seen=true
    check_workflows+=("$workflow")
    native_python_check_ok "$workflow" || native_contract_ok=false
  fi
  pipeline_job=$(workflow_job_from_uses "$workflow" 'pipeline-ecs.yml@')
  pipeline_with=$(workflow_with_values <<<"$pipeline_job")
  if [[ -n "$pipeline_job" ]]; then
    deploy_workflows+=("$workflow")
  fi
  if [[ -n "$pipeline_job" ]] && pipeline_bake_ok "$pipeline_with" "$bakefile"; then
    ci_ok=true
    bake_cache_contract_seen=true
    selected_bake_cache_ownership_ok "$pipeline_with" "$bakefile" || bake_cache_contract_ok=false
  fi
  bake_step=$(workflow_step_from_uses "$workflow" 'build-push-ecr-bake@')
  bake_step_with=$(workflow_with_values <<<"$bake_step")
  if [[ -n "$bake_step" && -n $(workflow_input_value "$bake_step_with" bake_target) ]]; then
    deploy_workflows+=("$workflow")
    bake_cache_contract_seen=true
    selected_bake_cache_ownership_ok "$bake_step_with" "$bakefile" || bake_cache_contract_ok=false
  fi
done

for check_workflow in "${check_workflows[@]-}"; do
  [[ -n "$check_workflow" ]] || continue
  for deploy_workflow in "${deploy_workflows[@]-}"; do
    [[ -n "$deploy_workflow" && "$check_workflow" != "$deploy_workflow" ]] || continue
    for protected_branch in dev staging main master production prod; do
      if workflow_push_allows_branch "$check_workflow" "$protected_branch" &&
        workflow_push_allows_branch "$deploy_workflow" "$protected_branch"; then
        trigger_contract_ok=false
      fi
    done
  done
done

for branch_probe in dev staging main feature/preflight-probe; do
  branch_covered=false
  for validation_workflow in "${check_workflows[@]-}" "${deploy_workflows[@]-}"; do
    [[ -n "$validation_workflow" ]] || continue
    if workflow_push_allows_branch "$validation_workflow" "$branch_probe"; then
      branch_covered=true
      break
    fi
  done
  [[ $branch_covered == true ]] || branch_validation_ok=false
done
dependabot_ecosystem_block() {
  local file=$1 ecosystem=$2
  awk -v ecosystem="$ecosystem" '
  /^[[:space:]]*-[[:space:]]+package-ecosystem:/ {
    if (in_ecosystem) exit
    pattern = "package-ecosystem:[[:space:]]*\\\"?" ecosystem "\\\"?([[:space:]]*#.*)?$"
    if ($0 ~ pattern) in_ecosystem = 1
  }
  in_ecosystem { print }
  ' "$file" 2>/dev/null
}

dependabot_multi_group_block() {
  local file=$1 group=$2
  awk -v group="$group" '
    /^multi-ecosystem-groups:/ { in_groups = 1; next }
    in_groups && /^[^[:space:]]/ { exit }
    in_groups && /^  [A-Za-z0-9_-]+:/ {
      if (in_group) exit
      name = $0
      sub(/^  /, "", name)
      sub(/:.*/, "", name)
      in_group = name == group
    }
    in_group { print }
  ' "$file" 2>/dev/null
}

dependabot_ecosystem_is_weekly() {
  local file=$1 block=$2 group group_block
  grep -Eq 'interval:[[:space:]]*"?weekly"?' <<<"$block" && return 0
  group=$(sed -nE \
    's/^[[:space:]]+multi-ecosystem-group:[[:space:]]*"?([^"[:space:]#]+)"?.*$/\1/p' \
    <<<"$block" | head -1)
  [[ -n "$group" ]] || return 1
  group_block=$(dependabot_multi_group_block "$file" "$group")
  grep -Eq 'interval:[[:space:]]*"?weekly"?' <<<"$group_block"
}

dependabot_update_cooldowns_ok() {
  local file=$1
  awk '
    function finish_update() {
      if (!in_update) return
      updates++
      if (cooldown_days < 7) invalid = 1
    }
    /^[[:space:]]*-[[:space:]]+package-ecosystem:/ {
      finish_update()
      match($0, /^[[:space:]]*/)
      updater_indent = RLENGTH
      in_update = 1
      direct_indent = -1
      in_cooldown = 0
      cooldown_indent = -1
      cooldown_field_indent = -1
      cooldown_days = -1
      next
    }
    in_update {
      if ($0 ~ /^[[:space:]]*(#.*)?$/) next
      match($0, /^[[:space:]]*/)
      indent = RLENGTH
      if (indent <= updater_indent) {
        finish_update()
        in_update = 0
        next
      }
      if (direct_indent < 0) direct_indent = indent
      if ($0 ~ /^[[:space:]]+cooldown:[[:space:]]*(#.*)?$/ &&
          indent == direct_indent) {
        cooldown_indent = indent
        cooldown_field_indent = -1
        in_cooldown = 1
        next
      }
      if (in_cooldown && indent <= cooldown_indent) {
        in_cooldown = 0
      } else if (in_cooldown) {
        if (cooldown_field_indent < 0) cooldown_field_indent = indent
      }
      if (in_cooldown && indent == cooldown_field_indent &&
          $0 ~ /^[[:space:]]+default-days:[[:space:]]*"?[0-9]+"?[[:space:]]*(#.*)?$/) {
        value = $0
        sub(/^.*default-days:[[:space:]]*"?/, "", value)
        sub(/"?[[:space:]]*(#.*)?$/, "", value)
        cooldown_days = value + 0
      }
    }
    END {
      finish_update()
      exit(updates > 0 && !invalid ? 0 : 1)
    }
  ' "$file" 2>/dev/null
}

dependabot_docker_covers_python() {
  local block=$1
  [[ -n "$block" ]] || return 1
  ! grep -Eq '^[[:space:]]+allow:' <<<"$block" || return 1
  if grep -Eq '^[[:space:]]+(multi-ecosystem-group|patterns):' <<<"$block"; then
    grep -Eq '^[[:space:]]+patterns:[[:space:]]*\[[[:space:]]*"\*"[[:space:]]*\]' <<<"$block"
  fi
}

dependabot_python_ignore_block() {
  local block=$1
  awk '
    /^[[:space:]]*-[[:space:]]+dependency-name:/ {
      if (found) exit
      found = $0 ~ /dependency-name:[[:space:]]*"?python"?([[:space:]]*#.*)?$/
    }
    found { print }
  ' <<<"$block"
}

dependabot_uv=$(dependabot_ecosystem_block "$dependabot" uv)
dependabot_docker=$(dependabot_ecosystem_block "$dependabot" docker)
if dependabot_update_cooldowns_ok "$dependabot"; then
  pass 'Dependabot update cooldowns'
else
  fail 'Dependabot update cooldowns (every updater needs default-days >= 7)'
fi
if grep -Eq 'interval:[[:space:]]*"?weekly"?' <<<"$dependabot_uv" &&
  grep -Eq '^[[:space:]]+versioning-strategy:[[:space:]]*"?lockfile-only"?[[:space:]]*(#.*)?$' <<<"$dependabot_uv" &&
  grep -Eq '^[[:space:]]+groups:[[:space:]]*(#.*)?$' <<<"$dependabot_uv" &&
  grep -Eq '^[[:space:]]+patterns:[[:space:]]*\[[[:space:]]*"\*"[[:space:]]*\]' <<<"$dependabot_uv" &&
  [[ $ci_ok == true ]]; then
  pass 'uv supply-chain updates and shared Python CI'
else
  fail 'uv supply-chain updates and shared Python CI'
fi

if [[ $check_contract_seen == false ]]; then
  na 'effective shared Python CI contract (pipeline Bake owns CI)'
elif [[ $check_contract_ok == true ]]; then
  pass 'effective shared Python CI contract'
else
  fail 'effective shared Python CI contract'
fi

if [[ $persistent_bake_contract_seen == false ]]; then
  na 'persistent cache-only Bake CI contract (no Bake check)'
elif [[ $persistent_bake_contract_ok == true ]]; then
  pass 'persistent cache-only Bake CI contract'
else
  fail 'persistent cache-only Bake CI contract'
fi

if [[ $native_contract_seen == false ]]; then
  na 'native Python CI contract (no native check)'
elif [[ $native_contract_ok == true ]]; then
  pass 'native Python CI contract'
else
  fail 'native Python CI contract'
fi

if [[ $branch_validation_ok == true ]]; then
  pass 'CI validation covers feature and deploy branches'
else
  fail 'CI validation covers feature and deploy branches'
fi

if [[ $trigger_contract_ok == true ]]; then
  pass 'disjoint check and deploy push ownership'
else
  fail 'disjoint check and deploy push ownership'
fi

if [[ $bake_cache_contract_seen == false ]]; then
  na 'selected Bake cache ownership (no CI-selected Bake group)'
elif [[ $bake_cache_contract_ok == true ]]; then
  pass 'selected Bake cache ownership'
else
  fail 'selected Bake cache ownership'
fi

if [[ $is_library == true ]]; then
  na 'immutable Docker bases and update path (library: ships no container)'
elif [[ ! -f "$dockerfile" ]]; then
  na 'immutable Docker bases and update path (deploys no service)'
elif [[ $docker_bases_pinned == true ]] &&
  dependabot_ecosystem_is_weekly "$dependabot" "$dependabot_docker"; then
  pass 'immutable Docker bases and update path'
else
  fail 'immutable Docker bases and update path'
fi

dependabot_docker_active=$(sed 's/[[:space:]]*#.*$//' <<<"$dependabot_docker")
dependabot_python_ignore=$(dependabot_python_ignore_block "$dependabot_docker_active")
if [[ $is_library == true ]]; then
  na 'Docker Python patch-only updates (library: ships no container)'
elif [[ ! -f "$dockerfile" ]]; then
  na 'Docker Python patch-only updates (deploys no service)'
elif dependabot_docker_covers_python "$dependabot_docker_active" &&
  grep -Fq 'version-update:semver-minor' <<<"$dependabot_python_ignore" &&
  grep -Fq 'version-update:semver-major' <<<"$dependabot_python_ignore" &&
  ! grep -Fq 'version-update:semver-patch' <<<"$dependabot_python_ignore"; then
  pass 'Docker Python patch-only updates'
else
  fail 'Docker Python patch-only updates'
fi

if grep -Eq '^version[[:space:]]*=' <<<"$project_config" &&
  grep -Eq '^version_provider[[:space:]]*=[[:space:]]*"pep621"' <<<"$commitizen_config" &&
  grep -Eq '^update_changelog_on_bump[[:space:]]*=[[:space:]]*true' <<<"$commitizen_config" &&
  grep -Eq '^annotated_tag[[:space:]]*=[[:space:]]*true' <<<"$commitizen_config" &&
  ! grep -Eq '^version[[:space:]]*=' <<<"$commitizen_config"; then
  pass 'single-source PEP 621 versioning'
else
  fail 'single-source PEP 621 versioning'
fi

# Required CI gates beyond lint/types/tests: a security gate on every push, and the
# eval suite wherever the code calls a model. Read the workflows' active content only.
ci_active=''
ci_readable_push=false
ci_delegated=false
for ci_workflow in "$repo_root/.github/workflows/"*.yml "$repo_root/.github/workflows/"*.yaml; do
  [[ -f "$ci_workflow" ]] || continue
  # "Every branch push runs ..." — a scheduled or manually dispatched job is not that gate.
  workflow_has_push "$ci_workflow" || continue
  ci_active+=$(sed 's/[[:space:]]*#.*$//' "$ci_workflow")$'\n'
  # A caller of a shared reusable workflow carries its gates in a file this script
  # cannot read. Other push workflows are still readable and still owe the gates.
  if grep -Eq '^[[:space:]]*uses:[[:space:]]*[^./[:space:]][^[:space:]]*/\.github/workflows/' "$ci_workflow"; then
    ci_delegated=true
  else
    ci_readable_push=true
  fi
done

if [[ -z "$ci_active" ]]; then
  na 'required CI security gate (no push workflows)'
  na 'required CI eval gate (no push workflows)'
elif [[ $ci_delegated == true && $ci_readable_push == false ]]; then
  na 'required CI security gate (gates live in a shared reusable workflow)'
  na 'required CI eval gate (gates live in a shared reusable workflow)'
else
  # A gate counts only when CI reaches it. Presence in the Makefile proves nothing
  # about the push: that target may never be invoked.
  ci_reaches() {
    local tool=$1 target
    grep -Eq "(^|[[:space:]])$tool" <<<"$ci_active" && return 0
    # A make target CI invokes, whose recipe runs the tool.
    while read -r target; do
      target_recipe_has "$makefile" "$target" "$tool" && return 0
    done < <(grep -Eo 'make[[:space:]]+[a-zA-Z][a-zA-Z0-9_-]*' <<<"$ci_active" |
      awk '{print $2}' | sort -u)
    # A container build CI runs, whose Dockerfile gate runs the tool.
    grep -Eq '(docker[[:space:]]+(build|buildx)|bake)' <<<"$ci_active" &&
      grep -Eq "(^|[[:space:]])$tool" "$dockerfile" 2>/dev/null && return 0
    return 1
  }

  security_gate_issues=()
  ci_reaches 'pip-audit' || security_gate_issues+=('dependency-audit')
  # zizmor also counts through the pre-commit hook this script verifies, when CI
  # runs pre-commit.
  if ! ci_reaches 'zizmor' &&
    ! { grep -Eq 'pre-commit[[:space:]]+run' <<<"$ci_active" && grep -Eq 'zizmor' "$precommit" 2>/dev/null; }; then
    security_gate_issues+=('workflow-audit')
  fi
  if [[ ${#security_gate_issues[@]} -eq 0 ]]; then
    pass 'required CI security gate'
  else
    fail "required CI security gate (${security_gate_issues[*]})"
  fi

  # Only a project that actually calls a model owes an eval gate.
  if grep -Eqi '"(anthropic|openai|pydantic-ai(-slim)?|langgraph|litellm|google-genai)[><=~[]' <<<"$project_config"; then
    # Match an invocation, not the letters. `retrieval` contains `eval`, and a RAG
    # repository is exactly the population this gate exists to catch.
    if grep -Eqi '(make[[:space:]]+eval[a-z-]*|pytest[^|;&]*[[:space:]/]evals?([[:space:]/]|$)|run_evals|(^|[[:space:]])evals?:([[:space:]]|$)|name:[[:space:]]*["'"'"']?evals?([[:space:]"'"'"']|$))' <<<"$ci_active"; then
      pass 'required CI eval gate'
    else
      fail 'required CI eval gate (model client declared, no eval run in CI)'
    fi
  else
    na 'required CI eval gate (no model client declared)'
  fi
fi

docker_uv=$(sed -nE 's|.*ghcr\.io/astral-sh/uv:([^@[:space:]]+).*|\1|p' "$dockerfile" 2>/dev/null | head -1)
precommit_uv=$(awk '
  /astral-sh\/uv-pre-commit/ { in_uv = 1; next }
  in_uv && /^[[:space:]]*rev:/ { sub(/^[[:space:]]*rev:[[:space:]]*/, ""); gsub(/["'\'' ]/, ""); print; exit }
' "$precommit" 2>/dev/null)
precommit_uv=${precommit_uv#v}
if [[ $is_library == true ]]; then
  na 'Docker and pre-commit uv versions match (library: ships no container)'
elif [[ ! -f "$dockerfile" ]]; then
  na 'Docker and pre-commit uv versions match (deploys no service)'
elif [[ -n "$docker_uv" ]] && [[ "$docker_uv" == "$precommit_uv" ]]; then
  pass 'Docker and pre-commit uv versions match'
else
  fail 'Docker and pre-commit uv versions match'
fi

if [[ $failures -eq 0 ]]; then
  printf 'VERDICT: PARITY\n'
  exit 0
fi

printf 'VERDICT: DIVERGENT (%d failed invariants)\n' "$failures"
exit 1
