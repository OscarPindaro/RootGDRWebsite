"""Real container/database/encryption recovery checks, always worktree-isolated."""

import base64
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from src.backend.config import StorageConfig, get_app_config
from src.backend.db.db import DatabaseManager
from src.backend.server import create_app
from harness.deploy.smoke import verify_production

from harness.deploy.backup import (
    HELPER_IMAGE,
    BackupError,
    capture,
    command,
    source_mount,
    sql,
    verify_bundle,
    write_private,
)
from harness.deploy.backup_schemas import (
    CaptureSpec,
    ConfigurationFile,
    FileSource,
    SQLiteSource,
    StorageSpec,
)
from harness.deploy.backup_storage import hydrate, initialize_storage, seal
from harness.test import state
from harness.deploy.backup_restore import restore_bundle, restore_encrypted
from harness.deploy.backup_schemas import PostgreSQLSource, RestoreSpec, RestoreResult

pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_capture(tmp_path):
    active = state.read()
    assert active is not None and active.worktree == state.worktree_root()
    name = f"{active.compose_project}-backup-writer-{uuid4().hex[:8]}"
    source = tmp_path / "sqlite"
    source.mkdir()
    files = tmp_path / "attachments"
    files.mkdir()
    with sqlite3.connect(source / "vikunja.db") as db:
        db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA user_version=260;
            CREATE TABLE tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL);
            INSERT INTO tasks VALUES (1, 'Recovery task');
        """)
    secret = tmp_path / "configuration"
    write_private(secret, b"dedicated-test-signing-secret")
    command(
        [
            "podman",
            "run",
            "-d",
            "--pull=never",
            "--network=none",
            "--name",
            name,
            "--entrypoint=python",
            HELPER_IMAGE,
            "-c",
            "import time; time.sleep(600)",
        ]
    )
    spec = CaptureSpec(
        application="vikunja",
        purpose="predeploy",
        run_id=uuid4(),
        build_commit="a" * 40,
        image_id="sha256:" + "a" * 64,
        writers=[name],
        database=SQLiteSource(
            storage=FileSource(directory=source), filename="vikunja.db"
        ),
        files=FileSource(directory=files),
        configuration=[
            ConfigurationFile(name=name, path=secret)
            for name in ("configuration", "secrets", "compose")
        ],
    )
    try:
        yield spec
    finally:
        command(["podman", "rm", "-f", name])


@pytest.fixture
def encrypted_storage(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir(mode=0o700)
    password = tmp_path / "restic-password"
    write_private(password, secrets.token_urlsafe(32).encode())
    spec = StorageSpec(repository=repository, password_file=password)
    initialize_storage(spec)
    return spec


def postgres_configuration(active):
    paths = {
        "runtime_env": active.config.integration_env,
        "runtime_config": active.config.integration_config,
        "migration_env": active.config.integration_env,
        "migration_config": active.config.integration_config,
        "database_env": active.config.integration_env,
        "compose_env": active.config.integration_env,
        "compose": state.worktree_root() / "deploy" / "production.compose.yaml",
    }
    return [ConfigurationFile(name=name, path=path) for name, path in paths.items()]


def stop_and_capture(spec, tmp_path):
    # A write immediately before shutdown must appear in both coordinated parts.
    (spec.files.directory / "near-capture.png").write_bytes(b"persisted-image")
    command(["podman", "stop", "--time=2", spec.writers[0]])
    directory = tmp_path / "capture"
    manifest = capture(spec, directory)
    return directory, manifest


def test_sqlite_capture_refuses_running_and_paused_writer(sqlite_capture, tmp_path):
    with pytest.raises(BackupError, match="writers must be stopped"):
        capture(sqlite_capture, tmp_path / "running")
    assert not (tmp_path / "running").exists()
    command(["podman", "pause", sqlite_capture.writers[0]])
    try:
        with pytest.raises(BackupError, match="writers must be stopped"):
            capture(sqlite_capture, tmp_path / "paused")
    finally:
        command(["podman", "unpause", sqlite_capture.writers[0]])
    assert not (tmp_path / "paused").exists()


def test_real_sqlite_snapshot_and_encrypted_roundtrip(
    sqlite_capture, encrypted_storage, tmp_path
):
    directory, manifest = stop_and_capture(sqlite_capture, tmp_path)
    assert manifest.database.user_version == 260
    assert manifest.database.tables[0].rows == 1
    assert [f.path for f in manifest.files] == ["near-capture.png"]
    receipt = seal(encrypted_storage, directory)
    decrypted = tmp_path / "decrypted"
    decrypted.mkdir(mode=0o700)
    restored = hydrate(encrypted_storage, receipt, decrypted)
    assert verify_bundle(restored) == manifest
    with sqlite3.connect(restored / "database.dump") as db:
        assert db.execute("SELECT title FROM tasks").fetchall() == [("Recovery task",)]
    assert (
        restored / "config" / "configuration"
    ).read_bytes() == b"dedicated-test-signing-secret"
    # Upstream repository metadata says the restic key is encrypted, not plaintext.
    key = json.loads(
        next((encrypted_storage.repository / "keys").iterdir()).read_text()
    )
    assert "data" in key and "kdf" in key
    for path in encrypted_storage.repository.rglob("*"):
        if path.is_file():
            contents = path.read_bytes()
            assert b"Recovery task" not in contents
            assert b"dedicated-test-signing-secret" not in contents
            assert b"persisted-image" not in contents


def test_corrupt_missing_or_untracked_capture_never_seals(
    sqlite_capture, encrypted_storage, tmp_path
):
    directory, _ = stop_and_capture(sqlite_capture, tmp_path)
    image = directory / "files.tar"
    original = image.read_bytes()
    image.write_bytes(b"broken-transfer")
    with pytest.raises(BackupError, match="checksum"):
        seal(encrypted_storage, directory)
    image.write_bytes(original)
    image.unlink()
    with pytest.raises(BackupError, match="artifacts"):
        seal(encrypted_storage, directory)
    image.write_bytes(original)
    (directory / "extra").write_bytes(b"unexpected")
    with pytest.raises(BackupError, match="artifacts"):
        seal(encrypted_storage, directory)
    assert not any((encrypted_storage.repository / "snapshots").iterdir())


def test_wrong_encryption_password_and_missing_repository_fail_closed(
    sqlite_capture, encrypted_storage, tmp_path
):
    directory, _ = stop_and_capture(sqlite_capture, tmp_path)
    wrong = tmp_path / "wrong-password"
    write_private(wrong, b"wrong-test-password")
    with pytest.raises(BackupError):
        seal(encrypted_storage.model_copy(update={"password_file": wrong}), directory)
    with pytest.raises(BackupError):
        seal(
            encrypted_storage.model_copy(update={"repository": tmp_path / "missing"}),
            directory,
        )
    assert not any((encrypted_storage.repository / "snapshots").iterdir())


def test_failed_sqlite_capture_removes_only_its_own_staging(sqlite_capture, tmp_path):
    command(["podman", "stop", "--time=2", sqlite_capture.writers[0]])
    sqlite_capture.database.filename = "missing.db"
    unrelated = tmp_path / "other"
    unrelated.mkdir()
    (unrelated / "preserve").write_bytes(b"untouched")
    with pytest.raises(BackupError):
        capture(sqlite_capture, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert (unrelated / "preserve").read_bytes() == b"untouched"


def test_sqlite_isolated_restore_recovers_files_and_refuses_existing_targets(
    sqlite_capture,
    encrypted_storage,
    tmp_path,
):
    directory, _ = stop_and_capture(sqlite_capture, tmp_path)
    receipt = seal(encrypted_storage, directory)
    namespace = f"rootgdr-restore-{uuid4().hex}"
    spec = RestoreSpec(namespace=namespace, target=tmp_path / namespace)
    storage_file = tmp_path / "restore-storage.json"
    receipt_file = tmp_path / "restore-receipt.json"
    spec_file = tmp_path / "restore-spec.json"
    for path, model in (
        (storage_file, encrypted_storage),
        (receipt_file, receipt),
        (spec_file, spec),
    ):
        write_private(path, model.model_dump_json().encode())
    variables = tmp_path / "restore-vars.yaml"
    write_private(
        variables,
        yaml.safe_dump(
            {
                "restore_command": [sys.executable, "-m", "harness.deploy.backup_cli"],
                "restore_storage_file": str(storage_file),
                "restore_receipt_file": str(receipt_file),
                "restore_spec_file": str(spec_file),
                "ansible_python_interpreter": sys.executable,
            }
        ).encode(),
    )
    args = [
        "ansible-playbook",
        "-i",
        "localhost,",
        str(state.worktree_root() / "deploy" / "restore.yaml"),
        "-e",
        f"@{variables}",
    ]
    playbook = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert playbook.returncode == 0, playbook.stdout + playbook.stderr
    result = RestoreResult.model_validate_json(
        (spec.target / "recovery.json").read_bytes()
    )
    assert result.verified and result.database_container is None
    recovery_mtime = (spec.target / "recovery.json").stat().st_mtime_ns
    check = subprocess.run(
        [*args, "--check"], capture_output=True, text=True, timeout=60
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert (spec.target / "recovery.json").stat().st_mtime_ns == recovery_mtime
    with sqlite3.connect(spec.target / "database.sqlite") as db:
        assert db.execute("SELECT title FROM tasks").fetchall() == [("Recovery task",)]
    assert (
        spec.target / "files" / "near-capture.png"
    ).read_bytes() == b"persisted-image"
    assert (
        spec.target / "config" / "configuration"
    ).read_bytes() == b"dedicated-test-signing-secret"
    with pytest.raises(BackupError, match="already exists"):
        restore_bundle(directory, spec)
    assert (
        spec.target / "files" / "near-capture.png"
    ).read_bytes() == b"persisted-image"
    namespace2 = f"rootgdr-restore-{uuid4().hex}"
    empty = tmp_path / namespace2
    empty.mkdir()
    with pytest.raises(BackupError, match="already exists"):
        restore_bundle(directory, RestoreSpec(namespace=namespace2, target=empty))


async def test_postgres_encrypted_restore_recovers_login_world_image_and_grants(
    app_config,
    db_manager,
    sqlite_capture,
    encrypted_storage,
    tmp_path,
):
    active = state.read()
    assert active is not None
    email = f"backup-owner-{uuid4().hex}@example.com"
    password = "isolated-recovery-test-password"

    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7xkAAAAASUVORK5CYII="
    )
    runtime = app_config.model_copy(
        update={
            "env": "production",
            "migrator": None,
            "storage": StorageConfig(storage_root=str(sqlite_capture.files.directory)),
            "auth": app_config.auth.model_copy(
                update={
                    "bootstrap_admin_email": email,
                    "cookie_secure": False,
                }
            ),
        }
    )
    source_app = create_app(runtime)
    source_app.state.db_manager = db_manager
    source_app.dependency_overrides[get_app_config] = lambda: runtime
    async with AsyncClient(
        transport=ASGITransport(app=source_app), base_url="http://test"
    ) as client:
        registered = await client.post(
            "/auth/register",
            json={
                "name": "Recovery owner",
                "email": email,
                "password": password,
            },
        )
        assert registered.status_code == 200
        assert (
            await client.post(
                "/auth/login", json={"email": email, "password": password}
            )
        ).status_code == 200
        world = await client.post(
            "/api/worlds/",
            json={
                "name": "Recovery world",
                "description": "Captured before migration",
            },
        )
        assert world.status_code == 201
        world_id = world.json()["id"]
        # Image is saved immediately before capture and read back after restore.
        image = await client.put(
            f"/api/worlds/{world_id}/image",
            files={
                "image": ("recovery.png", image_bytes, "image/png"),
            },
        )
        assert image.status_code == 200
    spec = sqlite_capture.model_copy(
        update={
            "application": "rootgdr",
            "configuration": postgres_configuration(active),
            "database": PostgreSQLSource(
                container=f"{active.compose_project}_db_1",
                database=app_config.database.db,
                migrator=app_config.migrator.user,
                runtime_role=app_config.database.user,
            ),
        }
    )
    command(["podman", "stop", "--time=2", spec.writers[0]])
    directory = tmp_path / "postgres-capture"
    manifest = capture(spec, directory)
    assert manifest.database.revisions
    assert (directory / "roles.sql").stat().st_mode & 0o777 == 0o600
    receipt = seal(encrypted_storage, directory)
    namespace = f"rootgdr-restore-{uuid4().hex}"
    restore_spec = RestoreSpec(
        namespace=namespace, target=tmp_path / namespace, publish_database=True
    )
    restored_manager = None
    try:
        result = restore_encrypted(encrypted_storage, receipt, restore_spec)
        restored_config = runtime.model_copy(
            update={
                "database": runtime.database.model_copy(
                    update={
                        "host": "127.0.0.1",
                        "port": result.database_port,
                    }
                ),
                "storage": StorageConfig(
                    storage_root=str(restore_spec.target / "files")
                ),
            }
        )
        restored_manager = DatabaseManager(restored_config.database)
        restored_app = create_app(restored_config)
        restored_app.state.db_manager = restored_manager
        restored_app.dependency_overrides[get_app_config] = lambda: restored_config
        async with AsyncClient(
            transport=ASGITransport(app=restored_app), base_url="http://restore"
        ) as client:
            assert (await client.get(f"/api/worlds/{world_id}")).status_code == 401
            smoke = await verify_production(
                client, email=email, password=SecretStr(password)
            )
            assert "/api/worlds/" in smoke.checked_paths
            recovered = await client.get(f"/api/worlds/{world_id}")
            assert recovered.status_code == 200
            assert recovered.json()["description"] == "Captured before migration"
            image = await client.get(f"/api/worlds/{world_id}/image")
            assert image.status_code == 200 and image.content == image_bytes
        async with restored_manager.async_session() as session:
            assert (
                await session.scalar(
                    text(
                        "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
                    )
                )
                is False
            )
            with pytest.raises(ProgrammingError, match="permission denied"):
                await session.execute(
                    text("CREATE TABLE forbidden_runtime_ddl (id integer)")
                )
        source = PostgreSQLSource(
            container=namespace,
            database=spec.database.database,
            migrator=spec.database.migrator,
            runtime_role=spec.database.runtime_role,
        )
        assert (
            sql(
                "podman",
                source,
                f"SET ROLE {source.migrator}; CREATE TABLE migrator_ddl (id integer);",
            )
            == ""
        )
        assert (
            sql(
                "podman",
                source,
                f"SET ROLE {source.runtime_role}; INSERT INTO migrator_ddl VALUES (1); SELECT id FROM migrator_ddl;",
            )
            == "1"
        )
        # Reusing a container/target is forbidden, including an otherwise empty directory.
        with pytest.raises(BackupError, match="container already exists"):
            restore_bundle(directory, restore_spec)
    finally:
        if restored_manager is not None:
            await restored_manager.close()
        if (
            namespace
            in command(["podman", "ps", "-a", "--format={{.Names}}"])
            .decode()
            .splitlines()
        ):
            command(["podman", "rm", "-f", namespace])
        if (restore_spec.target / "database").exists():
            # Remove only this run's generated database using its user namespace.
            command(
                [
                    "podman",
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network=none",
                    "--user=0",
                    "-v",
                    f"{restore_spec.target}:/restore:rw,z",
                    "--entrypoint=python",
                    HELPER_IMAGE,
                    "-c",
                    "import shutil; shutil.rmtree('/restore/database')",
                ]
            )
        async with AsyncClient(
            transport=ASGITransport(app=source_app), base_url="http://test"
        ) as client:
            assert (
                await client.post(
                    "/auth/login", json={"email": email, "password": password}
                )
            ).status_code == 200
            assert (await client.delete(f"/api/worlds/{world_id}")).status_code == 204


def test_postgres_dump_failure_removes_stage_and_does_not_encrypt(
    app_config, sqlite_capture, tmp_path
):
    active = state.read()
    assert active is not None
    command(["podman", "stop", "--time=2", sqlite_capture.writers[0]])
    container = f"{active.compose_project}_db_1"
    spec = sqlite_capture.model_copy(
        update={
            "application": "rootgdr",
            "configuration": postgres_configuration(active),
            "database": PostgreSQLSource(
                container=container,
                database=app_config.database.db,
                migrator="migrator_user",
                runtime_role="app_user",
            ),
        }
    )
    # Disable the real dump executable only in our harness container. Catalog
    # queries still work; the pg_dump step itself must fail and close the gate.
    binary = "/usr/lib/postgresql/18/bin/pg_dump"
    command(["podman", "exec", "--user=0", container, "chmod", "000", binary])
    try:
        with pytest.raises(BackupError):
            capture(spec, tmp_path / "failed-dump")
        assert not (tmp_path / "failed-dump").exists()
    finally:
        command(["podman", "exec", "--user=0", container, "chmod", "755", binary])


def run_backup_playbook(spec, storage, tmp_path, *, check=False):
    root = state.worktree_root()
    app_base = tmp_path / "application"
    app_base.mkdir(exist_ok=True)
    storage_file = tmp_path / "storage.json"
    if not storage_file.exists():
        write_private(storage_file, storage.model_dump_json().encode())
    receipt = tmp_path / "receipt.json"
    migration = tmp_path / "migration-ran"
    variables = tmp_path / "backup-vars.yaml"
    variables.write_text(
        yaml.safe_dump(
            {
                "backup_spec": spec.model_dump(mode="json"),
                "backup_application_base": str(app_base),
                "backup_capture_command": [
                    sys.executable,
                    "-m",
                    "harness.deploy.backup_cli",
                ],
                "backup_controller_command": [
                    sys.executable,
                    "-m",
                    "harness.deploy.backup_cli",
                ],
                "backup_storage_file": str(storage_file),
                "backup_receipt_file": str(receipt),
                "ansible_python_interpreter": sys.executable,
            }
        )
    )
    variables.chmod(0o600)
    playbook = tmp_path / "test-backup.yaml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Disposable coordinated backup gate",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "tasks": [
                        {
                            "name": "Run the real recovery role",
                            "ansible.builtin.include_role": {
                                "name": "coordinated_backup"
                            },
                        },
                        {
                            "name": "Require a verified gate",
                            "ansible.builtin.assert": {
                                "that": [
                                    "backup_verified",
                                    "backup_verified_run_id == backup_spec.run_id",
                                ]
                            },
                        },
                        {
                            "name": "Migration sentinel must never run after backup failure",
                            "ansible.builtin.command": {
                                "argv": ["touch", str(migration)]
                            },
                        },
                    ],
                }
            ]
        )
    )
    args = [
        "ansible-playbook",
        "-i",
        "localhost,",
        str(playbook),
        "-e",
        f"@{variables}",
    ]
    if check:
        args.append("--check")
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=240,
        env={**os.environ, "ANSIBLE_ROLES_PATH": str(root / "deploy" / "roles")},
    )
    return result, receipt, migration, app_base


@pytest.mark.parametrize("failure", ["capture", "transfer", "encryption"])
def test_ansible_failed_backup_blocks_migration_and_resumes_unchanged_build(
    failure,
    sqlite_capture,
    encrypted_storage,
    tmp_path,
):
    if failure == "capture":
        sqlite_capture.database.filename = "missing.db"
    elif failure == "transfer":
        transfer_failed = Event()
        stop_observer = Event()

        def interrupt_transfer():
            # Remove this run's source artifact after capture is complete but
            # before Ansible fetch: a real missing transfer, not a mocked command.
            while not stop_observer.is_set():
                for manifest_path in (tmp_path / "application").glob(
                    ".backup-*/bundle/manifest.json"
                ):
                    (manifest_path.parent / "files.tar").unlink()
                    transfer_failed.set()
                    return
                time.sleep(0.02)

        observer = Thread(target=interrupt_transfer, daemon=True)
        observer.start()
    else:
        wrong = tmp_path / "wrong-password"
        write_private(wrong, b"invalid-encryption-password")
        encrypted_storage = encrypted_storage.model_copy(
            update={"password_file": wrong}
        )
    image_before = json.loads(
        command(["podman", "inspect", sqlite_capture.writers[0]])
    )[0]["Image"]
    try:
        result, receipt, migration, app_base = run_backup_playbook(
            sqlite_capture, encrypted_storage, tmp_path
        )
    finally:
        if failure == "transfer":
            stop_observer.set()
            observer.join(timeout=2)
    if failure == "transfer":
        assert transfer_failed.is_set()
    assert result.returncode != 0, result.stdout + result.stderr
    assert "migrations remain blocked" in result.stdout
    assert not receipt.exists() and not migration.exists()
    writer = json.loads(command(["podman", "inspect", sqlite_capture.writers[0]]))[0]
    assert writer["State"]["Running"] is True and writer["Image"] == image_before
    assert not (app_base / ".operation-lock").exists()
    assert not list(app_base.glob(".backup-*"))
    assert (
        b"dedicated-test-signing-secret" not in (result.stdout + result.stderr).encode()
    )


@pytest.mark.parametrize("purpose", ["weekly", "predeploy"])
def test_ansible_successful_backup_opens_gate_and_honors_writer_lifecycle(
    purpose,
    sqlite_capture,
    encrypted_storage,
    tmp_path,
):
    sqlite_capture.purpose = purpose
    result, receipt, migration, app_base = run_backup_playbook(
        sqlite_capture, encrypted_storage, tmp_path
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert receipt.exists() and migration.exists()
    writer = json.loads(command(["podman", "inspect", sqlite_capture.writers[0]]))[0]
    assert writer["State"]["Running"] is (purpose == "weekly")
    assert not (app_base / ".operation-lock").exists()
    assert not list(app_base.glob(".backup-*"))


def test_ansible_stale_lock_and_check_mode_never_stop_writers(
    sqlite_capture, encrypted_storage, tmp_path
):
    app_base = tmp_path / "application"
    app_base.mkdir()
    lock = app_base / ".operation-lock"
    lock.mkdir()
    (lock / "owner").write_text("another-operation")
    result, receipt, migration, _ = run_backup_playbook(
        sqlite_capture, encrypted_storage, tmp_path
    )
    assert result.returncode != 0
    assert not receipt.exists() and not migration.exists()
    assert (lock / "owner").read_text() == "another-operation"
    writer = json.loads(command(["podman", "inspect", sqlite_capture.writers[0]]))[0]
    assert writer["State"]["Running"] is True
    # The wrapper's post-backup gate has no result in check mode; regardless,
    # the role must not acquire locks/capture/write or alter the real container.
    run_backup_playbook(sqlite_capture, encrypted_storage, tmp_path, check=True)
    assert (lock / "owner").read_text() == "another-operation"
    assert not receipt.exists() and not migration.exists()
    assert (
        json.loads(command(["podman", "inspect", sqlite_capture.writers[0]]))[0][
            "State"
        ]["Running"]
        is True
    )


def test_named_volume_capture_and_restore_preserves_numeric_upload_ownership(
    sqlite_capture, tmp_path
):
    active = state.read()
    assert active is not None
    volume = f"{active.compose_project}-backup-volume-{uuid4().hex}"
    namespace = f"rootgdr-restore-{uuid4().hex}"
    target = tmp_path / namespace
    command(["podman", "volume", "create", volume])
    try:
        command(
            [
                "podman",
                "run",
                "--rm",
                "--pull=never",
                "--network=none",
                "--user=0",
                "-v",
                f"{volume}:/files",
                "--entrypoint=python",
                HELPER_IMAGE,
                "-c",
                "import pathlib,os; p=pathlib.Path('/files/owned.png'); p.write_bytes(b'owned-image'); "
                "os.chmod(p,0o640); os.chown(p,10001,10001); os.chown('/files',10001,10001)",
            ]
        )
        sqlite_capture.files = FileSource(volume=volume)
        command(["podman", "stop", "--time=2", sqlite_capture.writers[0]])
        directory = tmp_path / "volume-capture"
        manifest = capture(sqlite_capture, directory)
        assert (
            manifest.files[0].uid,
            manifest.files[0].gid,
            manifest.files[0].mode,
        ) == (10001, 10001, 0o640)
        root_owner = command(
            [
                "podman",
                "run",
                "--rm",
                "--pull=never",
                "--network=none",
                "--user=0",
                "-v",
                source_mount("podman", sqlite_capture.files),
                "--entrypoint=python",
                HELPER_IMAGE,
                "-c",
                "import os,json; s=os.stat('/source'); print(json.dumps([s.st_uid,s.st_gid]))",
            ]
        )
        assert json.loads(root_owner) == [10001, 10001]
        assert restore_bundle(
            directory, RestoreSpec(namespace=namespace, target=target)
        ).verified
        info = json.loads(
            command(
                [
                    "podman",
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network=none",
                    "--user=0",
                    "-v",
                    f"{target / 'files'}:/files:ro,z",
                    "--entrypoint=python",
                    HELPER_IMAGE,
                    "-c",
                    "import os,json; s=os.stat('/files/owned.png'); print(json.dumps([s.st_uid,s.st_gid,s.st_mode & 0o777]))",
                ]
            )
        )
        assert info == [10001, 10001, 0o640]
    finally:
        command(["podman", "volume", "rm", volume])
        if target.exists():
            command(
                [
                    "podman",
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network=none",
                    "--user=0",
                    "-v",
                    f"{target}:/restore:rw,z",
                    "--entrypoint=python",
                    HELPER_IMAGE,
                    "-c",
                    "import shutil; shutil.rmtree('/restore/files')",
                ]
            )


def test_capture_detects_a_writer_restart_during_snapshot(sqlite_capture, tmp_path):
    command(["podman", "stop", "--time=2", sqlite_capture.writers[0]])
    directory = tmp_path / "interrupted-capture"
    restarted = Event()
    stop_observer = Event()

    def restart_during_capture():
        while not stop_observer.is_set():
            if directory.exists():
                command(["podman", "start", sqlite_capture.writers[0]])
                restarted.set()
                return
            time.sleep(0.01)

    observer = Thread(target=restart_during_capture, daemon=True)
    observer.start()
    try:
        with pytest.raises(BackupError):
            capture(sqlite_capture, directory)
    finally:
        stop_observer.set()
        observer.join(timeout=5)
    assert restarted.is_set()
    assert not directory.exists()


def test_sqlite_backup_api_includes_committed_wal_data(sqlite_capture, tmp_path):
    source = (
        sqlite_capture.database.storage.directory / sqlite_capture.database.filename
    )
    connection = sqlite3.connect(source)
    try:
        with connection:
            connection.execute("INSERT INTO tasks VALUES (2, 'Committed WAL task')")
        assert Path(f"{source}-wal").exists()
        directory, manifest = stop_and_capture(sqlite_capture, tmp_path)
        assert manifest.database.tables[0].rows == 2
        with sqlite3.connect(directory / "database.dump") as snapshot:
            assert snapshot.execute(
                "SELECT title FROM tasks ORDER BY id"
            ).fetchall() == [
                ("Recovery task",),
                ("Committed WAL task",),
            ]
    finally:
        connection.close()


def test_initial_empty_postgres_backup_precedes_the_first_migration(
    app_config,
    sqlite_capture,
    tmp_path,
):
    active = state.read()
    assert active is not None
    name = f"backup_empty_{uuid4().hex}"
    source = PostgreSQLSource(
        container=f"{active.compose_project}_db_1",
        database="postgres",
        migrator=app_config.migrator.user,
        runtime_role=app_config.database.user,
    )
    namespace = f"rootgdr-restore-{uuid4().hex}"
    target = tmp_path / namespace
    sql("podman", source, f"CREATE DATABASE {name} OWNER {source.migrator};")
    try:
        source.database = name
        sql(
            "podman",
            source,
            f"""
            ALTER SCHEMA public OWNER TO {source.migrator};
            GRANT USAGE ON SCHEMA public TO {source.runtime_role};
            ALTER DEFAULT PRIVILEGES FOR ROLE {source.migrator} IN SCHEMA public
              GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {source.runtime_role};
        """,
        )
        command(["podman", "stop", "--time=2", sqlite_capture.writers[0]])
        spec = sqlite_capture.model_copy(
            update={
                "application": "rootgdr",
                "database": source,
                "configuration": postgres_configuration(active),
            }
        )
        directory = tmp_path / "initial-capture"
        manifest = capture(spec, directory)
        assert manifest.database.revisions == [] and manifest.database.tables == []
        assert restore_bundle(
            directory, RestoreSpec(namespace=namespace, target=target)
        ).verified
        # A preexisting table without Alembic identity must not be mistaken for bootstrap.
        sql(
            "podman",
            source,
            f"SET ROLE {source.migrator}; CREATE TABLE untracked (id integer);",
        )
        with pytest.raises(BackupError, match="Alembic identity"):
            capture(spec, tmp_path / "untracked-capture")
        assert not (tmp_path / "untracked-capture").exists()
    finally:
        source.database = "postgres"
        sql("podman", source, f"DROP DATABASE {name};")
        if (
            namespace
            in command(["podman", "ps", "-a", "--format={{.Names}}"])
            .decode()
            .splitlines()
        ):
            command(["podman", "rm", "-f", namespace])
        if (target / "database").exists():
            command(
                [
                    "podman",
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network=none",
                    "--user=0",
                    "-v",
                    f"{target}:/restore:rw,z",
                    "--entrypoint=python",
                    HELPER_IMAGE,
                    "-c",
                    "import shutil; shutil.rmtree('/restore/database')",
                ]
            )
