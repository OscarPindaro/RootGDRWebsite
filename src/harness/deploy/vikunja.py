import hashlib
from typing import Literal

from pydantic import BaseModel

from .backup import BackupError, digest
from .vikunja_schemas import VikunjaPlan, VikunjaSpec


class BoardServiceConfig(BaseModel):
    publicurl: str
    interface: Literal[":3456"] = ":3456"
    enableregistration: bool = False
    enablelinksharing: Literal[False] = False
    enableemailreminders: Literal[False] = False
    defaultlanguage: Literal["it-IT"] = "it-IT"


class BoardDatabaseConfig(BaseModel):
    type: Literal["sqlite"] = "sqlite"
    path: Literal["/db/vikunja.db"] = "/db/vikunja.db"


class BoardFilesConfig(BaseModel):
    basepath: Literal["/app/vikunja/files"] = "/app/vikunja/files"


class BoardMailerConfig(BaseModel):
    enabled: Literal[False] = False


class BoardConfig(BaseModel):
    service: BoardServiceConfig
    database: BoardDatabaseConfig = BoardDatabaseConfig()
    files: BoardFilesConfig = BoardFilesConfig()
    mailer: BoardMailerConfig = BoardMailerConfig()


def plan_board(spec: VikunjaSpec) -> VikunjaPlan:
    secret = spec.signing_secret_file
    if (
        not secret.is_absolute()
        or secret.resolve() != secret
        or not secret.is_file()
        or secret.stat().st_mode & 0o077
    ):
        raise BackupError(
            "Board signing secret must be an existing private canonical file"
        )
    if secret.stat().st_size < 32:
        raise BackupError(
            "Board signing secret must be dedicated and sufficiently long"
        )
    return VikunjaPlan(
        run_id=spec.run_id,
        target=spec.target,
        deployment_commit=spec.deployment_commit,
        secret_generation=spec.secret_generation,
        signing_secret_file=secret,
        signing_secret_sha256=digest(secret),
    )


def configuration(
    plan: VikunjaPlan, *, controller_port: int, registration: bool = False
) -> BoardConfig:
    if not 1024 <= controller_port <= 65535:
        raise BackupError("The explicit controller tunnel/listener port is invalid")
    return BoardConfig(
        service=BoardServiceConfig(
            publicurl=f"http://127.0.0.1:{controller_port}/",
            enableregistration=registration,
        )
    )


def board_configuration_digest(plan: VikunjaPlan, config: BoardConfig) -> str:
    fingerprint = hashlib.sha256(config.model_dump_json().encode())
    fingerprint.update(str(plan.secret_generation).encode())
    fingerprint.update(plan.signing_secret_sha256.encode())
    return fingerprint.hexdigest()
