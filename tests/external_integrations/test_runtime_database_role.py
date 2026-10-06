import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from harness.test import compose, state
from src.backend.config import AppConfig

pytestmark = pytest.mark.external_integrations
ROOT = Path(__file__).resolve().parents[2]


class PackagedImage(BaseModel):
    engine: str
    reference: str
    workspace: Path

    def run_python(self, source: str, *, volume: str | None = None) -> None:
        command = [
            self.engine,
            "run",
            "--rm",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=64m",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--env-file",
            str(self.workspace / "runtime.env"),
        ]
        if volume is not None:
            command.extend(["--volume", f"{volume}:/app/data/uploads"])
        command.extend(
            [self.reference, "uv", "run", "--no-sync", "python", "-c", source]
        )
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr


@pytest.fixture(scope="module")
def packaged_image(tmp_path_factory) -> Iterator[PackagedImage]:
    active = state.read()
    assert active is not None and active.worktree == ROOT
    image = PackagedImage(
        engine=compose._container_engine(),
        reference=f"localhost/rootgdr-package-test:{uuid.uuid4().hex}",
        workspace=tmp_path_factory.mktemp("packaged-runtime"),
    )
    env_file = image.workspace / "runtime.env"
    env_file.write_text(
        "ENV=production\nENV_FILE=/dev/null\nYAML_CONFIG_FILE=/dev/null\n"
        "DATABASE__USER=runtime\nDATABASE__PASSWORD=runtime-test-password\n"
        "DATABASE__DB=runtime_test\nAUTH__JWT_SECRET=runtime-test-secret\n"
    )
    env_file.chmod(0o600)
    built = subprocess.run(
        [
            image.engine,
            "build",
            "--tag",
            image.reference,
            "--build-arg",
            "BUILD_COMMIT=verification",
            "--file",
            "Dockerfile",
            ".",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert built.returncode == 0, built.stderr
    try:
        yield image
    finally:
        subprocess.run(
            [image.engine, "image", "rm", image.reference],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )


async def test_runtime_role_has_no_migration_privileges(
    db_session: AsyncSession, app_config: AppConfig
) -> None:
    current = await db_session.scalar(text("SELECT current_user"))
    assert current == app_config.database.user
    assert (
        await db_session.scalar(
            text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
        )
        is False
    )
    privileges = (
        await db_session.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user"
            )
        )
    ).one()
    assert privileges == (False, False, False)
    assert app_config.migrator is not None
    assert (
        await db_session.scalar(
            text("SELECT pg_has_role(current_user, :migrator, 'MEMBER')"),
            {"migrator": app_config.migrator.user},
        )
        is False
    )
    assert await db_session.scalar(text("SELECT count(*) FROM alembic_version")) == 1


def test_packaged_runtime_starts_without_migration_secrets_or_private_files(
    packaged_image: PackagedImage,
) -> None:
    packaged_image.run_python(
        "import importlib.util, os\n"
        "from pathlib import Path\n"
        "from backend.config import get_app_config\n"
        "from backend.server import create_app\n"
        "from fastapi.testclient import TestClient\n"
        "config = get_app_config()\n"
        "assert os.getuid() == 10001\n"
        "assert config.migrator is None\n"
        "assert config.database.user == 'runtime'\n"
        "assert not any(key.startswith('MIGRATOR__') for key in os.environ)\n"
        "assert importlib.util.find_spec('playwright') is None\n"
        "assert Path('/app/LICENSE').is_file()\n"
        "assert all(not Path('/app', name).exists() for name in "
        "('.env', '.env.example', 'test.env', '.devin', 'node_modules', "
        "'.playwright-browsers', 'harness-artifacts', 'docs', 'tests'))\n"
        "with TestClient(create_app(config)) as client:\n"
        "    assert client.get('/ping').status_code == 200\n"
        "    actual_commit = client.get('/version').json()['commit']\n"
        "    assert actual_commit == 'verification', actual_commit\n"
        "    assert client.post('/auth/dev-login').status_code == 404\n"
        "    assert client.get('/health/ready').status_code == 503\n"
    )


def test_packaged_uploads_survive_container_recreation(
    packaged_image: PackagedImage,
) -> None:
    volume = f"rootgdr-package-test-{uuid.uuid4().hex}"
    subprocess.run(
        [packaged_image.engine, "volume", "create", volume],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        packaged_image.run_python(
            "from backend.filesystem.local import LocalFileSystem\n"
            "storage = LocalFileSystem('/app/data/uploads')\n"
            "storage.write('verification/retained.bin', b'packaged-upload-check')\n",
            volume=volume,
        )
        packaged_image.run_python(
            "from backend.filesystem.local import LocalFileSystem\n"
            "storage = LocalFileSystem('/app/data/uploads')\n"
            "assert storage.read('verification/retained.bin') == b'packaged-upload-check'\n",
            volume=volume,
        )
    finally:
        subprocess.run(
            [packaged_image.engine, "volume", "rm", volume],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )


def test_cached_images_carry_their_own_selected_revision(
    packaged_image: PackagedImage,
) -> None:
    for revision in ("unknown", "a" * 40):
        reference = f"localhost/rootgdr-package-test:{uuid.uuid4().hex}"
        command = [
            packaged_image.engine,
            "build",
            "--tag",
            reference,
            "--file",
            "Dockerfile",
            ".",
        ]
        if revision != "unknown":
            command[2:2] = ["--build-arg", f"BUILD_COMMIT={revision}"]
        built = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=180
        )
        assert built.returncode == 0, built.stderr
        try:
            inspected = subprocess.run(
                [
                    packaged_image.engine,
                    "image",
                    "inspect",
                    reference,
                    "--format",
                    '{{index .Config.Labels "org.opencontainers.image.revision"}}',
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            assert inspected.stdout.strip() == revision
            image = packaged_image.model_copy(update={"reference": reference})
            image.run_python(
                "from backend.health.service import build_info\n"
                f"assert build_info().commit == {revision!r}, build_info().commit\n"
            )
        finally:
            subprocess.run(
                [packaged_image.engine, "image", "rm", reference],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
