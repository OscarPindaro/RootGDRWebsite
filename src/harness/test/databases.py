"""Idempotent creation and reset of the two isolated test databases.

Entry-point init scripts only run on an empty volume, so the harness ensures
both test databases exist on every startup through the container's Postgres
superuser. Database names reach SQL only after validation against a strict
pattern; role names and passwords travel as quoted psql variables.
"""

import re
from typing import Callable

_NAME = re.compile(r"^[a-z][a-z0-9_]*_test$")

DEFAULT_INTEGRATION_DB = "backend_integration_test"
DEFAULT_E2E_DB = "backend_e2e_test"

# One psql invocation: (database to connect to, sql, psql variables).
SqlCall = tuple[str, str, dict[str, str]]
Psql = Callable[[str, str, dict[str, str]], str]


class DatabaseError(RuntimeError):
    """Raised when test database names are missing or unsafe."""


def resolve_names(values: dict[str, str | None]) -> tuple[str, str]:
    """Return the (integration, e2e) database names from the test env values."""
    integration = values.get("TEST_INTEGRATION_DB") or DEFAULT_INTEGRATION_DB
    e2e = values.get("TEST_E2E_DB") or DEFAULT_E2E_DB
    for name in (integration, e2e):
        if not _NAME.fullmatch(name):
            raise DatabaseError(f"Refusing unsafe test database name: {name!r}")
    if integration == e2e:
        raise DatabaseError("Integration and E2E test databases must differ.")
    return integration, e2e


def ensure_commands(
    databases: list[str],
    values: dict[str, str | None],
    *,
    reset: list[str] | None = None,
) -> list[SqlCall]:
    """Build the idempotent calls that create roles and the given databases.

    With ``reset``, a database is dropped (terminating connections) before
    being recreated; grants are applied in every case.
    """
    reset = reset or []
    roles = {
        "migrator_user": values.get("MIGRATOR__USER") or "migrator_user",
        "migrator_password": values.get("MIGRATOR__PASSWORD") or "migrator_password",
        "app_user": values.get("DATABASE__USER") or "app_user",
        "app_password": values.get("DATABASE__PASSWORD") or "app_password",
    }
    calls: list[SqlCall] = [("postgres", _ROLES_SQL, roles)]
    for database in databases:
        if database in reset:
            calls.append(("postgres", _DROP_SQL, {"database": database}))
        calls.append(("postgres", _CREATE_SQL, {"database": database, **roles}))
        calls.append(("postgres", _GRANT_SQL, {"database": database, **roles}))
        calls.append((database, _SCHEMA_SQL, roles))
    return calls


def apply(psql: Psql, calls: list[SqlCall]) -> None:
    for database, sql, variables in calls:
        psql(database, sql, variables)


_ROLES_SQL = "\n".join(
    (
        "SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'migrator_user', :'migrator_password')",
        "WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'migrator_user')\\gexec",
        "SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')",
        "WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')\\gexec",
    )
)

_CREATE_SQL = (
    "SELECT format('CREATE DATABASE %I OWNER %I', :'database', :'migrator_user')\n"
    "WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'database')\\gexec"
)

_DROP_SQL = (
    "SELECT format('DROP DATABASE %I WITH (FORCE)', :'database')\n"
    "WHERE EXISTS (SELECT FROM pg_database WHERE datname = :'database')\\gexec"
)

_GRANT_SQL = 'GRANT CONNECT ON DATABASE :"database" TO :"app_user";'

_SCHEMA_SQL = "\n".join(
    (
        'ALTER SCHEMA public OWNER TO :"migrator_user";',
        'GRANT USAGE, CREATE ON SCHEMA public TO :"migrator_user";',
        'GRANT USAGE ON SCHEMA public TO :"app_user";',
        'ALTER DEFAULT PRIVILEGES FOR ROLE :"migrator_user" IN SCHEMA public',
        '  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";',
        'ALTER DEFAULT PRIVILEGES FOR ROLE :"migrator_user" IN SCHEMA public',
        '  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"app_user";',
    )
)
