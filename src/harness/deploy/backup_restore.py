"""Isolated recovery only; deliberately has no existing-container/database path."""

import json
import secrets
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from .backup import (
    HELPER_IMAGE,
    POSTGRES_IMAGE,
    BackupError,
    capture_files,
    command,
    digest,
    file_inventory,
    postgres_state,
    private_directory,
    quote_literal,
    sql,
    sqlite_state,
    verify_bundle,
    write_private,
)
from .backup_schemas import (
    BackupReceipt,
    FileSource,
    PostgreSQLSource,
    PostgreSQLState,
    RestoreResult,
    RestoreSpec,
    StorageSpec,
)
from .backup_storage import hydrate


def restore_bundle(directory: Path, spec: RestoreSpec) -> RestoreResult:
    spec = RestoreSpec.model_validate(spec.model_dump())
    manifest = verify_bundle(directory)
    if spec.target.resolve() != spec.target or spec.target.name != spec.namespace:
        raise BackupError("Noncanonical isolated target")
    containers = command([spec.engine, "ps", "-a", "--format={{.Names}}"])
    if spec.namespace in containers.decode().splitlines():
        raise BackupError("Restore container already exists; refusing to reuse it")
    # Even empty existing targets are refused. A recovery never overwrites data.
    private_directory(spec.target)
    container_created = False
    try:
        files = spec.target / "files"
        files.mkdir(mode=0o700)
        # The archive has already passed link/path/type checks and is restored in
        # a new helper namespace, preserving numeric UID/GID and regular modes.
        script = """
import os,tarfile
with tarfile.open('/bundle/files.tar') as archive:
    archive.extractall('/restore',filter='data')
    for member in archive:
        path='/restore/'+member.name
        os.chmod(path,member.mode & 0o777)
        os.chown(path,member.uid,member.gid)
"""
        command(
            [
                spec.engine,
                "run",
                "--rm",
                "--pull=never",
                "--network=none",
                "--user=0",
                "-v",
                f"{directory}:/bundle:ro,z",
                "-v",
                f"{files}:/restore:rw,z",
                "--entrypoint=python",
                HELPER_IMAGE,
                "-c",
                script,
            ]
        )
        with tempfile.TemporaryDirectory(prefix="rootgdr-restore-files-") as temporary:
            archive = Path(temporary) / "files.tar"
            capture_files(spec.engine, FileSource(directory=files), archive)
            if file_inventory(archive) != manifest.files:
                raise BackupError("Restored file contents or permissions differ")
        shutil.copytree(directory / "config", spec.target / "config")
        database_container = None
        database_port = None
        if isinstance(manifest.database, PostgreSQLState):
            db = manifest.database
            (spec.target / "database").mkdir(mode=0o700)
            # PostgreSQL 18 creates PGDATA below this mount. Its entrypoint only
            # chowns PGDATA, so make the private mount traversable by postgres.
            command(
                [
                    spec.engine,
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network=none",
                    "--user=0",
                    "--entrypoint=sh",
                    "-v",
                    f"{spec.target / 'database'}:/var/lib/postgresql:rw,z",
                    POSTGRES_IMAGE,
                    "-c",
                    "chown postgres:postgres /var/lib/postgresql",
                ]
            )
            env_file = spec.target / "restore.env"
            write_private(
                env_file,
                (
                    "POSTGRES_USER=postgres\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD="
                    + secrets.token_urlsafe(40)
                    + "\n"
                ).encode(),
            )
            network = (
                ["--publish=127.0.0.1::5432"]
                if spec.publish_database
                else ["--network=none"]
            )
            command(
                [
                    spec.engine,
                    "run",
                    "-d",
                    "--pull=never",
                    *network,
                    "--name",
                    spec.namespace,
                    "--env-file",
                    str(env_file),
                    "-v",
                    f"{spec.target / 'database'}:/var/lib/postgresql:rw,z",
                    POSTGRES_IMAGE,
                ]
            )
            container_created = True
            database_container = spec.namespace
            source = PostgreSQLSource(
                container=spec.namespace,
                database="postgres",
                migrator=db.migrator,
                runtime_role=db.runtime_role,
            )
            for attempt in range(60):
                try:
                    sql(spec.engine, source, "SELECT 1;")
                    break
                except BackupError:
                    if attempt == 59:
                        raise BackupError(
                            "Isolated restore database did not become ready"
                        )
                    time.sleep(1)
            if spec.publish_database:
                binding = (
                    command([spec.engine, "port", spec.namespace, "5432/tcp"])
                    .decode()
                    .strip()
                )
                if not binding.startswith("127.0.0.1:"):
                    raise BackupError("Isolated database was not bound to loopback")
                database_port = int(binding.rsplit(":", 1)[1])
            sql(spec.engine, source, (directory / "roles.sql").read_text())
            command(
                [
                    spec.engine,
                    "exec",
                    "-i",
                    spec.namespace,
                    "pg_restore",
                    "-U",
                    "postgres",
                    "-d",
                    "postgres",
                    "--create",
                    "--exit-on-error",
                ],
                input_file=directory / "database.dump",
            )
            source.database = db.database
            actual = postgres_state(spec.engine, source)
            # Patch releases are not schema identity; validate tables, heads and grants.
            if actual.model_copy(update={"server_version": db.server_version}) != db:
                raise BackupError("Restored schema, records or grants differ")
            permissions = json.loads(
                sql(
                    spec.engine,
                    source,
                    f"""
                SELECT json_build_array(
                    has_schema_privilege({quote_literal(db.migrator)}, 'public', 'CREATE'),
                    has_schema_privilege({quote_literal(db.runtime_role)}, 'public', 'USAGE'),
                    has_schema_privilege({quote_literal(db.runtime_role)}, 'public', 'CREATE'));
            """,
                )
            )
            if permissions != [True, True, False]:
                raise BackupError("Restored two-role DDL/DML separation is invalid")
        else:
            target_db = spec.target / "database.sqlite"
            # A second SQLite backup API copy, not a live database-file copy.
            write_private(target_db, b"")
            with sqlite3.connect(
                (directory / "database.dump").as_uri() + "?mode=ro", uri=True
            ) as src:
                with sqlite3.connect(target_db) as dst:
                    src.backup(dst)
            target_db.chmod(0o600)
            if sqlite_state(target_db) != manifest.database:
                raise BackupError("Restored SQLite records or schema differ")
        result = RestoreResult(
            namespace=spec.namespace,
            target=spec.target,
            database_container=database_container,
            database_port=database_port,
            manifest_sha256=digest(directory / "manifest.json"),
        )
        write_private(
            spec.target / "recovery.json", result.model_dump_json(indent=2).encode()
        )
        return result
    except BaseException:
        # Preserve failed recovery for diagnosis; never remove an existing target.
        # Stop only the container positively created by this invocation.
        if container_created:
            command([spec.engine, "stop", "--time=5", spec.namespace])
        raise


def restore_encrypted(
    storage: StorageSpec, receipt: BackupReceipt, spec: RestoreSpec
) -> RestoreResult:
    with tempfile.TemporaryDirectory(prefix="rootgdr-recovery-") as temporary:
        directory = hydrate(storage, receipt, Path(temporary))
        return restore_bundle(directory, spec)
