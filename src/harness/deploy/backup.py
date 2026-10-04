"""Coordinated capture primitives. Ansible owns locks, downtime and transfer."""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .backup_schemas import (
    Artifact,
    BackupManifest,
    CaptureSpec,
    FileEntry,
    FileSource,
    PostgreSQLSource,
    PostgreSQLState,
    SQLiteState,
    TableState,
    safe_relative,
)

# Pinned helper image (Python 3.14); used only for read-only file/SQLite capture.
HELPER_IMAGE = "docker.io/library/python@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f"
POSTGRES_IMAGE = "docker.io/library/postgres:18.3@sha256:69e8582b781cb44fa4557b98ed586fe68361e320d9b12f9707494335634f4f3d"


class BackupError(RuntimeError):
    pass


class ContainerState(BaseModel):
    running: bool = Field(alias="Running")
    paused: bool = Field(alias="Paused")
    started_at: str = Field(alias="StartedAt")
    finished_at: str = Field(alias="FinishedAt")


class ContainerInfo(BaseModel):
    id: str = Field(alias="Id")
    state: ContainerState = Field(alias="State")


class VolumeInfo(BaseModel):
    mountpoint: Path = Field(alias="Mountpoint")


def stopped_writers(engine: str, writers: list[str]) -> list[ContainerInfo]:
    states = []
    for writer in writers:
        records = json.loads(command([engine, "inspect", writer]))
        if len(records) != 1:
            raise BackupError("Writer identity is ambiguous")
        info = ContainerInfo.model_validate(records[0])
        if info.state.running or info.state.paused:
            raise BackupError("All application writers must be stopped before capture")
        states.append(info)
    return states


def command(
    argv: list[str],
    *,
    input_bytes: bytes | None = None,
    input_file: Path | None = None,
    output: Path | None = None,
) -> bytes:
    """Never report argv, SQL, or stderr: any can contain private recovery data."""
    if input_bytes is not None and input_file is not None:
        raise BackupError("Ambiguous command input")
    try:
        with ExitStack() as stack:
            source = stack.enter_context(input_file.open("rb")) if input_file else None
            target = (
                stack.enter_context(output.open("xb")) if output else subprocess.PIPE
            )
            if output:
                os.chmod(output, 0o600)
            result = subprocess.run(
                argv,
                input=input_bytes,
                stdin=source,
                stdout=target,
                stderr=subprocess.PIPE,
                timeout=600,
            )
        if result.returncode:
            raise BackupError(
                "Recovery command failed; no verified backup was produced"
            )
        return result.stdout if output is None else b""
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BackupError("Recovery command unavailable or timed out") from error


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private_directory(path: Path) -> None:
    """Create a run-owned directory; never reuse existing data or follow symlinks."""
    if not path.is_absolute() or path.resolve() != path or not path.parent.is_dir():
        raise BackupError("Recovery directory requires an existing, canonical parent")
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as error:
        raise BackupError("Recovery directory already exists") from error


def write_private(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(content)


def source_mount(engine: str, source: FileSource) -> str:
    if source.directory is not None:
        path = source.directory
        if path.resolve() != path or not path.is_dir():
            raise BackupError("Source directory is missing or noncanonical")
        return f"{path}:/source:ro,z"
    # Avoid Docker/Podman implicitly creating a misspelled empty source volume.
    records = json.loads(command([engine, "volume", "inspect", str(source.volume)]))
    if len(records) != 1:
        raise BackupError("Source volume identity is ambiguous")
    path = VolumeInfo.model_validate(records[0]).mountpoint
    if not path.is_absolute() or path.resolve() != path or not path.is_dir():
        raise BackupError("Source volume mountpoint is missing or noncanonical")
    return f"{path}:/source:ro,z"


def capture_files(
    engine: str, source: FileSource, target: Path, helper_image: str = HELPER_IMAGE
) -> None:
    script = (
        "import sys,tarfile; "
        "t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); "
        "t.add('/source',arcname='.',recursive=True); t.close()"
    )
    command(
        [
            engine,
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--user=0",
            "-v",
            source_mount(engine, source),
            "--entrypoint=python",
            helper_image,
            "-c",
            script,
        ],
        output=target,
    )


def file_inventory(archive: Path) -> list[FileEntry]:
    """Allow regular files/directories only; no links, traversal, devices or duplicates."""
    entries = []
    seen = set()
    try:
        with tarfile.open(archive, "r:") as tar:
            for member in tar:
                if member.name == "." and member.isdir():
                    continue
                name = member.name.removeprefix("./")
                safe_relative(name)
                if name in seen or not (member.isfile() or member.isdir()):
                    raise BackupError("Unsafe file archive member")
                seen.add(name)
                stream = tar.extractfile(member) if member.isfile() else None
                checksum = (
                    hashlib.file_digest(stream, "sha256").hexdigest()
                    if stream
                    else None
                )
                entries.append(
                    FileEntry(
                        path=name,
                        sha256=checksum,
                        size=member.size,
                        mode=member.mode & 0o777,
                        uid=member.uid,
                        gid=member.gid,
                    )
                )
    except (tarfile.TarError, ValueError) as error:
        raise BackupError("Invalid file archive") from error
    return sorted(entries, key=lambda item: item.path)


def sql(engine: str, source: PostgreSQLSource, query: str) -> str:
    return (
        command(
            [
                engine,
                "exec",
                "-i",
                source.container,
                "psql",
                "-X",
                "-qAt",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                source.admin,
                "-d",
                source.database,
            ],
            input_bytes=query.encode(),
        )
        .decode()
        .strip()
    )


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def postgres_state(engine: str, source: PostgreSQLSource) -> PostgreSQLState:
    tables = json.loads(
        sql(
            engine,
            source,
            """
        SELECT coalesce(json_agg(json_build_object('schema_name', schemaname,
          'name', tablename) ORDER BY schemaname, tablename), '[]')
        FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');
    """,
        )
    )
    table_states = []
    for table in tables:
        # Validate the database's catalog data at the boundary too.
        item = TableState(**table, rows=0)
        name = f"{quote_identifier(item.schema_name)}.{quote_identifier(item.name)}"
        item.rows = int(sql(engine, source, f"SELECT count(*) FROM {name};"))
        table_states.append(item)
    permissions = sql(
        engine,
        source,
        """
        SELECT json_build_object(
          'schemas', (SELECT json_agg(json_build_array(nspname,
            pg_get_userbyid(nspowner), nspacl::text) ORDER BY nspname)
            FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'),
          'relations', (SELECT json_agg(json_build_array(n.nspname, c.relname,
            pg_get_userbyid(c.relowner), c.relacl::text) ORDER BY n.nspname, c.relname)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'),
          'defaults', (SELECT json_agg(json_build_array(pg_get_userbyid(d.defaclrole),
            n.nspname, d.defaclobjtype, d.defaclacl::text)
            ORDER BY pg_get_userbyid(d.defaclrole), n.nspname, d.defaclobjtype)
            FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace));
    """,
    )
    if any(
        t.schema_name == "public" and t.name == "alembic_version" for t in table_states
    ):
        revisions = json.loads(
            sql(
                engine,
                source,
                "SELECT coalesce(json_agg(version_num ORDER BY version_num), '[]') FROM public.alembic_version;",
            )
        )
    elif not table_states:
        # First bootstrap still backs up the initialized roles/schema/config,
        # before the very first Alembic migration creates application tables.
        revisions = []
    else:
        raise BackupError("Nonempty application database has no Alembic identity")
    database_identity = json.loads(
        sql(
            engine,
            source,
            """
        SELECT json_build_object('owner', pg_get_userbyid(datdba), 'grants', datacl::text)
        FROM pg_database WHERE datname=current_database();
    """,
        )
    )
    return PostgreSQLState(
        database=source.database,
        migrator=source.migrator,
        runtime_role=source.runtime_role,
        database_owner=database_identity["owner"],
        database_grants=database_identity["grants"],
        tables=table_states,
        permissions=permissions,
        revisions=revisions,
        server_version=sql(engine, source, "SHOW server_version;"),
    )


def sqlite_state(path: Path) -> SQLiteState:
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise BackupError("SQLite integrity check failed")
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        tables = [
            TableState(
                schema_name="main",
                name=name,
                rows=connection.execute(
                    f"SELECT count(*) FROM {quote_identifier(name)}"
                ).fetchone()[0],
            )
            for (name,) in names
        ]
        return SQLiteState(
            tables=tables,
            user_version=connection.execute("PRAGMA user_version").fetchone()[0],
            schema_definition=json.dumps(
                connection.execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
                ).fetchall()
            ),
        )


def verify_bundle(directory: Path) -> BackupManifest:
    try:
        if directory.resolve() != directory or directory.is_symlink():
            raise BackupError("Noncanonical backup directory")
        manifest_path = directory / "manifest.json"
        if manifest_path.is_symlink():
            raise BackupError("Linked manifest")
        manifest = BackupManifest.model_validate_json(manifest_path.read_bytes())
        expected = {"manifest.json", *(item.path for item in manifest.artifacts)}
        actual = set()
        for path in directory.rglob("*"):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise BackupError("Linked or special recovery artifact")
            if path.is_file():
                actual.add(path.relative_to(directory).as_posix())
        if actual != expected:
            raise BackupError("Missing or untracked recovery artifacts")
        for item in manifest.artifacts:
            path = directory / item.path
            if path.stat().st_size != item.size or digest(path) != item.sha256:
                raise BackupError("Recovery artifact checksum mismatch")
        if file_inventory(directory / "files.tar") != manifest.files:
            raise BackupError("Upload inventory mismatch")
        if isinstance(manifest.database, SQLiteState):
            if sqlite_state(directory / "database.dump") != manifest.database:
                raise BackupError("SQLite snapshot verification failed")
        return manifest
    except (OSError, ValueError) as error:
        raise BackupError("Invalid or incomplete backup bundle") from error


def capture(spec: CaptureSpec, directory: Path) -> BackupManifest:
    """Capture only after every declared writer is fully stopped, never paused."""
    spec = CaptureSpec.model_validate(spec.model_dump())
    writer_states = stopped_writers(spec.engine, spec.writers)
    private_directory(directory)
    try:
        if isinstance(spec.database, PostgreSQLSource):
            db = spec.database
            # Reject privileged runtime/migration roles before recording reproducible setup.
            roles = json.loads(
                sql(
                    spec.engine,
                    db,
                    f"""
                SELECT coalesce(json_agg(rolname ORDER BY rolname), '[]') FROM pg_roles
                WHERE rolname IN ({quote_literal(db.migrator)}, {quote_literal(db.runtime_role)})
                  AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
                  AND NOT rolreplication AND NOT rolbypassrls
                  AND rolinherit AND rolconnlimit=-1 AND rolvaliduntil IS NULL AND rolconfig IS NULL;
            """,
                )
            )
            if sorted(roles) != sorted([db.migrator, db.runtime_role]):
                raise BackupError(
                    "Application roles are missing or excessively privileged"
                )
            memberships = sql(
                spec.engine,
                db,
                f"""
                SELECT count(*) FROM pg_auth_members m JOIN pg_roles r
                ON r.oid=m.member OR r.oid=m.roleid WHERE r.rolname IN
                ({quote_literal(db.migrator)}, {quote_literal(db.runtime_role)});
            """,
            )
            if memberships != "0":
                raise BackupError(
                    "Custom role memberships require a reviewed recovery procedure"
                )
            role_sql = sql(
                spec.engine,
                db,
                f"""
                SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                  'NOREPLICATION NOBYPASSRLS PASSWORD %L;', rolname, rolpassword)
                FROM pg_authid WHERE rolname IN
                  ({quote_literal(db.migrator)}, {quote_literal(db.runtime_role)}) ORDER BY rolname;
            """,
            )
            write_private(directory / "roles.sql", role_sql.encode())
            state = postgres_state(spec.engine, db)
            command(
                [
                    spec.engine,
                    "exec",
                    db.container,
                    "pg_dump",
                    "-U",
                    db.admin,
                    "-d",
                    db.database,
                    "--format=custom",
                    "--create",
                ],
                output=directory / "database.dump",
            )
            # A truncated dump must fail while still on the capture host.
            command(
                [spec.engine, "exec", "-i", db.container, "pg_restore", "--list"],
                input_file=directory / "database.dump",
            )
        else:
            db = spec.database
            script = """
import pathlib,shutil,sqlite3,sys,tempfile
source=pathlib.Path('/source') / sys.argv[1]
if source.resolve() != source or not source.is_file():
    raise RuntimeError('Unsafe SQLite source')
with tempfile.TemporaryDirectory() as directory:
    target=pathlib.Path(directory)/'snapshot.db'
    target.touch(mode=0o600)
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('SQLite integrity failure')
    with target.open('rb') as stream:
        shutil.copyfileobj(stream,sys.stdout.buffer)
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
                    source_mount(spec.engine, db.storage),
                    "--entrypoint=python",
                    spec.helper_image or HELPER_IMAGE,
                    "-c",
                    script,
                    db.filename,
                ],
                output=directory / "database.dump",
            )
            state = sqlite_state(directory / "database.dump")
        capture_files(
            spec.engine,
            spec.files,
            directory / "files.tar",
            spec.helper_image or HELPER_IMAGE,
        )
        files = file_inventory(directory / "files.tar")
        (directory / "config").mkdir(mode=0o700)
        for item in spec.configuration:
            if item.path.resolve() != item.path or not item.path.is_file():
                raise BackupError("Recovery configuration is missing or linked")
            write_private(directory / "config" / item.name, item.path.read_bytes())
        if stopped_writers(spec.engine, spec.writers) != writer_states:
            raise BackupError(
                "Writer identity or lifecycle changed during coordinated capture"
            )
        artifacts = [
            Artifact(
                path=p.relative_to(directory).as_posix(),
                sha256=digest(p),
                size=p.stat().st_size,
            )
            for p in sorted(directory.rglob("*"))
            if p.is_file()
        ]
        manifest = BackupManifest(
            application=spec.application,
            purpose=spec.purpose,
            run_id=spec.run_id,
            captured_at=datetime.now(UTC),
            build_commit=spec.build_commit,
            image_id=spec.image_id,
            writers=spec.writers,
            database=state,
            artifacts=artifacts,
            files=files,
        )
        write_private(
            directory / "manifest.json", manifest.model_dump_json(indent=2).encode()
        )
        return verify_bundle(directory)
    except BaseException:
        # Only this run's newly created staging is removed, including on interruption.
        shutil.rmtree(directory)
        raise
