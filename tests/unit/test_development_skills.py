"""Check the portable workflow skills' entry points and local references."""

import ast
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".devin" / "skills"
WORKFLOW_SKILLS = (
    "using-development-skills",
    "brainstorming",
    "best-practices",
    "create-test",
    "refactor",
    "resolve-merge",
    "staff-review",
    "phone-a-friend",
    "roast-my-code",
    "explain-diff",
    "align-docs",
    "simplify-stuff",
    "handoff",
    "bro",
    "align-stack",
    "align-upstream",
    "update-deps",
    "commit",
    "changelog",
    "integrate-observability",
    "design-audit",
    "visual-design-principles",
    "mui",
    "team-conventions",
    "ai-agent-bench",
    "eval-regression",
    "plugin-feedback",
    "retro",
    "coach",
    "server-inspect",
    "server-delivery-audit",
    "server-deploy",
    "server-backup",
    "kickoff",
    "kickoff-fix",
    "refresh-knowledge",
)


@pytest.mark.parametrize("name", WORKFLOW_SKILLS)
def test_workflow_skill_is_opt_in_and_self_contained(name: str) -> None:
    path = SKILLS / name / "SKILL.md"
    text = path.read_text()
    _, frontmatter, _ = text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)

    assert metadata["name"] == name
    assert metadata["description"]
    assert metadata["triggers"] == ["user"]
    for unsupported in (
        "AskUserQuestion",
        "request_user_input",
        "CLAUDE_PLUGIN_ROOT",
        "development-skills:",
        "Vikunja",
    ):
        assert unsupported not in text
    for document in path.parent.rglob("*.md"):
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text()):
            if not target.startswith(("https://", "http://", "#")):
                assert (document.parent / target.split("#", 1)[0]).is_file(), target


def test_shared_standards_have_local_references() -> None:
    shared = ROOT / ".devin" / "shared"
    assert shared.is_dir()
    for document in shared.rglob("*.md"):
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text()):
            if not target.startswith(("https://", "http://", "#")):
                assert (document.parent / target.split("#", 1)[0]).is_file(), target


def test_stack_preflight_on_disposable_projects() -> None:
    script = SKILLS / "align-stack" / "tests" / "preflight-python.test.sh"
    result = subprocess.run(
        ["bash", str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "align-stack Python preflight tests passed" in result.stdout


@pytest.mark.parametrize("name", ("ai-agent-bench", "eval-regression"))
def test_runner_skills_disclose_unsupported_devin(name: str) -> None:
    text = (SKILLS / name / "SKILL.md").read_text()
    assert "Devin is not supported" in text


@pytest.mark.parametrize("name", ("run_trial.py", "run_evals.py"))
def test_runner_agent_choices_exclude_devin(name: str) -> None:
    path = SKILLS / "ai-agent-bench" / "scripts" / name
    tree = ast.parse(path.read_text())
    choices = [
        ast.literal_eval(keyword.value)
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "add_argument"
        and any(
            isinstance(arg, ast.Constant) and arg.value == "--agent"
            for arg in call.args
        )
        for keyword in call.keywords
        if keyword.arg == "choices"
    ]
    assert choices == [["claude", "codex"]]
    assert "--dangerously-skip-permissions" not in path.read_text()


def test_benchmark_scripts_parse_without_loading_optional_dependencies() -> None:
    scripts = SKILLS / "ai-agent-bench" / "scripts"
    for script in scripts.glob("*.py"):
        ast.parse(script.read_text(), filename=str(script))


def test_benchmark_rejects_devin_before_any_trial(tmp_path: Path) -> None:
    script = SKILLS / "ai-agent-bench" / "scripts" / "run_trial.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(tmp_path),
            "--config",
            str(tmp_path / "missing.toml"),
            "--agent",
            "devin",
            "--run",
            "unsupported",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "invalid choice: 'devin'" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_native_history_queries_are_scoped_read_only_and_follow_the_main_chain(
    tmp_path: Path,
) -> None:
    reference = SKILLS / "retro" / "references" / "native-history.md"
    queries = re.findall(r"```sql\n(.*?)```", reference.read_text(), re.DOTALL)
    assert len(queries) == 2
    database = tmp_path / "sessions.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TABLE sessions (id TEXT, working_directory TEXT, model TEXT, "
            "created_at INTEGER, last_activity_at INTEGER, hidden INTEGER, "
            "main_chain_id INTEGER);"
            "CREATE TABLE message_nodes (row_id INTEGER PRIMARY KEY, session_id TEXT, "
            "node_id INTEGER, parent_node_id INTEGER, chat_message TEXT, "
            "created_at INTEGER DEFAULT 10);"
        )
        connection.executemany(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("selected", "/project", "model", 1, 10, 0, 3),
                ("other", "/elsewhere", "model", 1, 20, 0, 1),
                ("hidden", "/project", "model", 1, 30, 1, 1),
            ],
        )
        for row_id, session, node, parent, role, content in (
            (1, "selected", 1, None, "user", "Initial request"),
            (2, "selected", 2, 1, "tool", "Private tool output"),
            (3, "selected", 3, 2, "assistant", "Visible answer"),
            (4, "selected", 4, 1, "assistant", "Abandoned branch"),
            (5, "other", 1, None, "user", "Other project"),
        ):
            connection.execute(
                "INSERT INTO message_nodes "
                "(row_id, session_id, node_id, parent_node_id, chat_message) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    row_id,
                    session,
                    node,
                    parent,
                    json.dumps(
                        {
                            "role": role,
                            "content": content,
                            "thinking": "Hidden reasoning",
                        }
                    ),
                ),
            )
        connection.execute("UPDATE message_nodes SET created_at=1 WHERE row_id=1")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        sessions = connection.execute(
            queries[0],
            {"workspace": "/project", "since": 0, "until": 20, "session_limit": 5},
        ).fetchall()
        assert [row[0] for row in sessions] == ["selected"]
        messages = connection.execute(
            queries[1],
            {
                "session_id": "selected",
                "max_depth": 100,
                "row_limit": 10,
                "text_limit": 1024,
                "since": 0,
                "until": 20,
            },
        ).fetchall()
        assert messages == [
            (3, "assistant", "Visible answer"),
            (1, "user", "Initial request"),
        ]
        recent = connection.execute(
            queries[1],
            {
                "session_id": "selected",
                "max_depth": 100,
                "row_limit": 10,
                "text_limit": 4,
                "since": 5,
                "until": 20,
            },
        ).fetchall()
        assert recent == [(3, "assistant", "Visi")]
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM message_nodes")
