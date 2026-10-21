import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest
from pydantic import BaseModel

pytestmark = [
    pytest.mark.external_integrations,
    pytest.mark.devin_cli_e2e,
    pytest.mark.skipif(
        sys.platform != "linux", reason="Uses the Linux CLI session store."
    ),
]

MODEL = "deepseek-v4-1-flash-1017-high"
MODEL_LABEL = "DeepSeek V4.1 Flash High"
DATA = Path.home() / ".local/share/devin/cli"


class ToolCall(BaseModel):
    function_name: str


class Step(BaseModel):
    model_name: str | None = None
    tool_calls: list[ToolCall] | None = None


class Agent(BaseModel):
    model_name: str


class Export(BaseModel):
    session_id: str
    agent: Agent
    steps: list[Step]


class Session(BaseModel):
    id: str
    model: str
    working_directory: Path


class Cli:
    def __init__(self, executable: str, root: Path) -> None:
        self.executable = executable
        self.root = root
        self.environment = os.environ.copy()
        for name in ("DEVIN_MODEL", "DEVIN_PERMISSION_MODE"):
            self.environment.pop(name, None)
        if not self.environment.get("ACP_BACKEND"):
            self.environment.pop("ACP_BACKEND", None)

    def invoke(
        self,
        arguments: list[str],
        cwd: Path,
        log: Path,
        *,
        invalid_default: bool = False,
    ) -> str:
        environment = self.environment.copy()
        if invalid_default:
            environment["DEVIN_MODEL"] = "invalid-cli-e2e-default"
        with log.open("w") as output:
            process = subprocess.Popen(
                [self.executable, *arguments],
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                pytest.fail(
                    f"Devin CLI timed out; owned process group stopped. Log: {log}"
                )
        assert code == 0, f"Devin CLI exited {code}; inspect {log}"
        return log.read_text()

    def session(self, session_id: str) -> Session:
        with sqlite3.connect(
            (DATA / "sessions.db").as_uri() + "?mode=ro", uri=True, timeout=5
        ) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT id,model,working_directory FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
        assert row is not None
        return Session.model_validate(dict(row))

    def complete(
        self,
        workspace: Path,
        mode: Literal["auto", "dangerous"],
        *,
        resume: Session | None = None,
        flag_only: bool = False,
    ) -> Session:
        runtime = workspace / ".devin" / "cli-e2e"
        runtime.mkdir(parents=True, exist_ok=True)
        prefix = uuid4().hex
        config = {
            "subagents_enabled": False,
            "attribution": False,
            "auto_update": False,
            "permissions": {
                "deny": [
                    "exec",
                    "edit",
                    "write",
                    "read",
                    "grep",
                    "glob",
                    "run_subagent",
                    "code_search",
                    "mcp__*",
                    "Read(**)",
                    "Write(**)",
                ]
            },
        }
        if not flag_only:
            config["agent"] = {"model": MODEL, "subagent_model": MODEL}
        profile = runtime / f"{prefix}.config.json"
        profile.write_text(json.dumps(config))
        marker = f"CLI_MODEL_E2E_{prefix}"
        prompt = runtime / f"{prefix}.prompt.md"
        prompt.write_text(
            f"Do not use tools or change files. Reply exactly {marker}.\n"
        )
        export_path = runtime / f"{prefix}.export.json"
        arguments = [
            "--config",
            str(profile),
            "--model",
            MODEL,
            "--permission-mode",
            mode,
            "--respect-workspace-trust",
            "false",
            "--export",
            str(export_path),
            "--prompt-file",
            str(prompt),
            "-p",
        ]
        if resume:
            arguments += ["--resume", resume.id]
        output = self.invoke(
            arguments,
            workspace,
            runtime / f"{prefix}.stdout.log",
            invalid_default=flag_only,
        )
        assert marker in output
        exported = Export.model_validate_json(export_path.read_text())
        assert exported.agent.model_name == MODEL_LABEL
        assert {s.model_name for s in exported.steps if s.model_name} == {MODEL}
        assert not any(s.tool_calls for s in exported.steps)
        if resume:
            assert exported.session_id == resume.id, "CLI forked rather than resumed."
        session = self.session(exported.session_id)
        assert session.model == MODEL
        assert session.working_directory.resolve() == workspace.resolve()
        statistics = self.invoke(
            [
                "--config",
                str(profile),
                "--model",
                MODEL,
                "--permission-mode",
                mode,
                "--respect-workspace-trust",
                "false",
                "--resume",
                session.id,
                "-p",
                "/session-stats",
            ],
            workspace,
            runtime / f"{prefix}.served-model.log",
        )
        assert re.findall(r"^- Model:\s*(.+)$", statistics, re.M) == [MODEL_LABEL]
        assert self.session(session.id) == session
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        )
        assert status.stdout == "", f"CLI changed fixture files: {status.stdout}"
        (runtime / f"{prefix}.receipt.json").write_text(
            session.model_dump_json(indent=2)
        )
        return session


@pytest.fixture(scope="session")
def cli(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> Cli:
    if not request.config.getoption(
        "--run-devin-cli-e2e", default=False
    ) or os.environ.get("CI"):
        pytest.skip("Live Devin CLI calls require explicit local opt-in.")
    executable = shutil.which("devin")
    assert executable, "Install and authenticate Devin CLI before opting in."
    root = tmp_path_factory.mktemp("devin-cli-e2e")
    client = Cli(executable, root)
    client.invoke(["auth", "status"], root, root / "authentication.log")
    assert (DATA / "sessions.db").is_file(), "The native CLI session store is missing."
    repository = root / "repository"
    repository.mkdir()
    (repository / ".gitignore").write_text(".devin/\n")
    (repository / "fixture.txt").write_text("CLI model selection fixture.\n")
    git_environment = os.environ.copy()
    git_environment.update(
        GIT_AUTHOR_NAME="CLI test",
        GIT_AUTHOR_EMAIL="cli-test@example.invalid",
        GIT_COMMITTER_NAME="CLI test",
        GIT_COMMITTER_EMAIL="cli-test@example.invalid",
    )
    for command in (
        ["git", "init", "-q", "--initial-branch=main"],
        ["git", "add", "--", ".gitignore", "fixture.txt"],
        ["git", "commit", "-q", "-m", "Create isolated CLI fixture"],
    ):
        subprocess.run(command, cwd=repository, env=git_environment, check=True)
    return client


@pytest.fixture
def workspace(cli: Cli) -> Path:
    target = cli.root / f"worker-{uuid4().hex[:8]}"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(target), "HEAD"],
        cwd=cli.root / "repository",
        capture_output=True,
        text=True,
        check=True,
    )
    return target


@pytest.mark.parametrize("mode", ["auto", "dangerous"])
def test_new_worker_and_resume_keep_model_session_and_workspace(cli, workspace, mode):
    first = cli.complete(workspace, mode)
    resumed = cli.complete(workspace, mode, resume=first)
    assert resumed == first


def test_model_flag_overrides_an_invalid_environment_default(cli, workspace):
    cli.complete(workspace, "dangerous", flag_only=True)


def test_parallel_workers_have_distinct_sessions_and_worktrees(cli, workspace):
    other = cli.root / f"parallel-{uuid4().hex[:8]}"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(other), "HEAD"],
        cwd=cli.root / "repository",
        capture_output=True,
        text=True,
        check=True,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cli.complete, workspace, "dangerous")
        second = pool.submit(cli.complete, other, "dangerous")
        left, right = first.result(), second.result()
    assert left.id != right.id
    assert left.working_directory.resolve() != right.working_directory.resolve()


def test_cross_worktree_resume_keeps_model_and_id_but_relocates_workspace(
    cli, workspace
):
    first = cli.complete(workspace, "dangerous")
    other = cli.root / f"resume-{uuid4().hex[:8]}"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(other), "HEAD"],
        cwd=cli.root / "repository",
        capture_output=True,
        text=True,
        check=True,
    )
    resumed = cli.complete(other, "dangerous", resume=first)
    assert resumed.id == first.id
    assert resumed.working_directory.resolve() == other.resolve()
