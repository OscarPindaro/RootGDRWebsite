import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

import httpx

from pydantic import BaseModel

from .backup import (
    HELPER_IMAGE,
    BackupError,
    VolumeInfo,
    command,
    digest,
    private_directory,
    write_private,
)
from .backup_schemas import BackupReceipt, CaptureSpec, FileSource
from .rollout import ImageSize, ImageTransfer
from .vikunja_bootstrap import (
    BoardBootstrapResult,
    BoardInfo,
    BoardPage,
    BoardProject,
    BoardUser,
    bootstrap_accounts,
    login,
    request,
)
from .vikunja_schemas import (
    VIKUNJA_IMAGE,
    BoardLanOperation,
    BoardOperation,
    VikunjaAccount,
    VikunjaDeployment,
    VikunjaPlan,
    VikunjaSpec,
    VikunjaTarget,
)


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


def board_compose_contents(source: bytes, address: IPv4Address) -> bytes:
    binding = b"      - '127.0.0.1:${VIKUNJA_PORT:?VIKUNJA_PORT required}:3456'\n"
    if source.count(binding) != 1:
        raise BackupError("Board Compose must have its reviewed loopback binding")
    if address == IPv4Address("127.0.0.1"):
        return source
    return source.replace(
        binding, binding + binding.replace(b"127.0.0.1", str(address).encode())
    )


def plan_board(spec: VikunjaSpec, compose_file: Path | None = None) -> VikunjaPlan:
    if spec.target.project == "rootgdr-vikunja" and spec.proof is None:
        raise BackupError("Production board bootstrap requires all four passing suites")
    if spec.proof is not None and spec.proof.commit != spec.deployment_commit:
        raise BackupError(
            "Board proof does not identify the selected deployment commit"
        )
    compose_file = (
        compose_file
        or Path(__file__).resolve().parents[3] / "deploy/vikunja.compose.yaml"
    )
    if compose_file.resolve() != compose_file or not compose_file.is_file():
        raise BackupError("Board Compose input must be canonical")
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
    image = ImageSize.model_validate(
        json.loads(command(["podman", "image", "inspect", VIKUNJA_IMAGE]))[0]
    )
    helper = ImageSize.model_validate(
        json.loads(command(["podman", "image", "inspect", HELPER_IMAGE]))[0]
    )
    credentials = spec.owner.model_dump(mode="json")
    credentials["password"] = spec.owner.password.get_secret_value()
    credentials_sha256 = hmac.new(
        secret.read_bytes(),
        json.dumps(
            {"owner": credentials, "tooling": spec.tooling.model_dump(mode="json")},
            sort_keys=True,
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    access_port = spec.access_port or spec.target.port
    public_port = (
        access_port
        if spec.target.bind_address == IPv4Address("127.0.0.1")
        else spec.target.port
    )
    config = BoardConfig(
        service=BoardServiceConfig(
            publicurl=f"http://{spec.target.bind_address}:{public_port}/"
        )
    )
    fingerprint = hashlib.sha256(spec.target.model_dump_json().encode())
    fingerprint.update(config.model_dump_json().encode())
    fingerprint.update(spec.project_title.encode())
    return VikunjaPlan(
        run_id=spec.run_id,
        target=spec.target,
        deployment_commit=spec.deployment_commit,
        secret_generation=spec.secret_generation,
        signing_secret_file=secret,
        signing_secret_sha256=digest(secret),
        credentials_sha256=credentials_sha256,
        configuration_sha256=fingerprint.hexdigest(),
        compose_sha256=hashlib.sha256(
            board_compose_contents(compose_file.read_bytes(), spec.target.bind_address)
        ).hexdigest(),
        image_id=image.image_id,
        helper_image_id=helper.image_id,
        access_port=access_port,
        owner_username=spec.owner.username,
        tooling_username=spec.tooling.username,
        project_title=spec.project_title,
    )


def configuration(
    plan: VikunjaPlan, *, controller_port: int, registration: bool = False
) -> BoardConfig:
    if not 1024 <= controller_port <= 65535:
        raise BackupError("The explicit controller tunnel/listener port is invalid")
    public_port = (
        controller_port
        if plan.target.bind_address == IPv4Address("127.0.0.1")
        else plan.target.port
    )
    return BoardConfig(
        service=BoardServiceConfig(
            publicurl=f"http://{plan.target.bind_address}:{public_port}/",
            enableregistration=registration,
        )
    )


def board_configuration_digest(plan: VikunjaPlan, config: BoardConfig) -> str:
    fingerprint = hashlib.sha256(config.model_dump_json().encode())
    fingerprint.update(str(plan.secret_generation).encode())
    fingerprint.update(plan.signing_secret_sha256.encode())
    return fingerprint.hexdigest()


def board_images(staging: Path) -> list[ImageTransfer]:
    transfers = []
    for image, name in (
        (VIKUNJA_IMAGE, "image.oci.tar"),
        (HELPER_IMAGE, "helper.oci.tar"),
    ):
        info = ImageSize.model_validate(
            json.loads(command(["podman", "image", "inspect", image]))[0]
        )
        archive = staging / name
        if archive.exists() or archive.is_symlink():
            raise BackupError("Board image export destination already exists")
        command(
            [
                "podman",
                "save",
                "--format=oci-archive",
                "--output",
                str(archive),
                info.image_id,
            ]
        )
        archive.chmod(0o600)
        transfers.append(
            ImageTransfer(
                image_id=info.image_id,
                archive_path=archive,
                archive_name=name,
                archive_sha256=digest(archive),
                archive_size=archive.stat().st_size,
                unpacked_size=info.size,
            )
        )
    return transfers


def private_board_file(path: Path) -> bytes:
    if (
        not path.is_absolute()
        or path.resolve() != path
        or not path.is_file()
        or path.stat().st_mode & 0o077
    ):
        raise BackupError(
            "Board metadata or credentials are missing, noncanonical or not private"
        )
    return path.read_bytes()


def preflight_board(plan: VikunjaPlan) -> BoardOperation:
    base = plan.target.base
    if base.resolve() != base or not base.is_dir() or base.stat().st_mode & 0o077:
        raise BackupError(
            "Board operation requires its canonical private application directory"
        )
    current_file = base / "current.json"
    if (base / ".pending-bootstrap").exists() or (base / ".pending-network").exists():
        raise BackupError(
            "Incomplete board operation requires operator review, not account recreation"
        )
    if current_file.exists() or current_file.is_symlink():
        current = VikunjaDeployment.model_validate_json(
            private_board_file(current_file)
        )
        if any(
            (
                current.target != plan.target,
                current.image_id != plan.image_id,
                current.secret_generation != plan.secret_generation,
                current.signing_secret_sha256 != plan.signing_secret_sha256,
                current.credentials_sha256 != plan.credentials_sha256,
                current.configuration_sha256 != plan.configuration_sha256,
                current.compose_sha256 != plan.compose_sha256,
            )
        ):
            raise BackupError(
                "Changed board credentials, image or configuration require a separately reviewed recovery-gated rollout"
            )
        runtime = base / "runtime"
        if (
            digest(runtime / "compose.yaml") != plan.compose_sha256
            or digest(runtime / "signing-secret") != plan.signing_secret_sha256
        ):
            raise BackupError(
                "Existing board deployment files differ from the verified identities"
            )
        if BoardConfig.model_validate_json(
            (runtime / "config.json").read_bytes()
        ) != configuration(plan, controller_port=plan.access_port):
            raise BackupError(
                "Existing board configuration differs from the verified closed-registration profile"
            )
        private_board_file(runtime / "owner.json")
        private_board_file(runtime / "tooling-token")
        private_board_file(runtime / "compose.env")
        if digest(runtime / "compose.env") != current.compose_env_sha256:
            raise BackupError(
                "Existing board mount or image environment differs from the verified deployment"
            )
        return BoardOperation(initialized=False, current=current)
    containers = command(["podman", "ps", "-a", "--format={{.Names}}"])
    volumes = command(["podman", "volume", "ls", "--format={{.Name}}"])
    unit = Path.home() / ".config/systemd/user" / (plan.target.project + ".service")
    if (
        unit.exists()
        or unit.is_symlink()
        or (base / "runtime").exists()
        or f"{plan.target.project}_board_1" in containers.decode().splitlines()
        or any(
            f"{plan.target.project}_{suffix}" in volumes.decode().splitlines()
            for suffix in ("database", "attachments")
        )
    ):
        raise BackupError(
            "Existing board data has no verified manifest; refusing to adopt or reset it"
        )
    return BoardOperation(initialized=True)


def initialize_board(
    plan: VikunjaPlan, spec: VikunjaSpec, compose_file: Path, secret_file: Path
) -> BoardOperation:
    operation = preflight_board(plan)
    if not operation.initialized:
        return operation
    if plan.target.bind_address != IPv4Address("127.0.0.1"):
        raise BackupError(
            "Bootstrap remains loopback-only; enable LAN access after closed-registration verification"
        )
    if (
        spec.target != plan.target
        or spec.owner.username != plan.owner_username
        or spec.tooling.username != plan.tooling_username
        or spec.project_title != plan.project_title
    ):
        raise BackupError("Board bootstrap inputs do not match the validated plan")
    if (
        digest(compose_file) != plan.compose_sha256
        or digest(secret_file) != plan.signing_secret_sha256
    ):
        raise BackupError("Transferred board configuration or signing secret differs")
    credentials = spec.owner.model_dump(mode="json")
    credentials["password"] = spec.owner.password.get_secret_value()
    actual_credentials = hmac.new(
        secret_file.read_bytes(),
        json.dumps(
            {"owner": credentials, "tooling": spec.tooling.model_dump(mode="json")},
            sort_keys=True,
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(actual_credentials, plan.credentials_sha256):
        raise BackupError("Board bootstrap credentials differ from the validated plan")
    if private_board_file(plan.target.base / ".operation-lock/owner").decode() != str(
        plan.run_id
    ):
        raise BackupError("Board bootstrap requires this run's shared operation lock")
    image = ImageSize.model_validate(
        json.loads(command(["podman", "image", "inspect", plan.image_id]))[0]
    )
    if image.image_id.removeprefix("sha256:") != plan.image_id.removeprefix("sha256:"):
        raise BackupError("Loaded board image identity differs")
    write_private(plan.target.base / ".pending-bootstrap", str(plan.run_id).encode())
    runtime = plan.target.base / "runtime"
    private_directory(runtime)
    directories = []
    for suffix in ("database", "attachments"):
        volume = f"{plan.target.project}_{suffix}"
        command(["podman", "volume", "create", volume])
        path = VolumeInfo.model_validate(
            json.loads(command(["podman", "volume", "inspect", volume]))[0]
        ).mountpoint
        if not path.is_absolute() or path.resolve() != path or not path.is_dir():
            raise BackupError("Board volume mountpoint is noncanonical")
        directories.append(path)
    command(
        [
            "podman",
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--user=0:0",
            "--entrypoint=python",
            "-v",
            f"{directories[0]}:/db:z",
            "-v",
            f"{directories[1]}:/files:z",
            plan.helper_image_id,
            "-c",
            "import os; os.chown('/db',1000,1000); os.chown('/files',1000,1000)",
        ]
    )
    for filename, contents, mode in (
        ("compose.yaml", compose_file.read_bytes(), 0o600),
        ("signing-secret", secret_file.read_bytes(), 0o644),
        (
            "config.json",
            configuration(plan, controller_port=plan.access_port, registration=True)
            .model_dump_json()
            .encode(),
            0o644,
        ),
    ):
        write_private(runtime / filename, contents)
        (runtime / filename).chmod(mode)
    owner = spec.owner.model_dump(mode="json")
    owner["password"] = spec.owner.password.get_secret_value()
    write_private(runtime / "owner.json", json.dumps(owner).encode())
    write_private(runtime / "deployment-plan.json", plan.model_dump_json().encode())
    env = f"VIKUNJA_PROJECT={plan.target.project}\nVIKUNJA_PORT={plan.target.port}\nVIKUNJA_IMAGE={plan.image_id}\nVIKUNJA_CONFIG={runtime / 'config.json'}\nVIKUNJA_SIGNING_SECRET={runtime / 'signing-secret'}\nVIKUNJA_DATABASE_DIRECTORY={directories[0]}\nVIKUNJA_FILES_DIRECTORY={directories[1]}\n"
    write_private(runtime / "compose.env", env.encode())
    return operation


def board_compose(plan: VikunjaPlan, provider: str) -> list[str]:
    runtime = plan.target.base / "runtime"
    return [
        provider,
        "--env-file",
        str(runtime / "compose.env"),
        "-f",
        str(runtime / "compose.yaml"),
        "-p",
        plan.target.project,
    ]


def wait_for_board(plan: VikunjaPlan) -> None:
    with httpx.Client(
        base_url=f"http://127.0.0.1:{plan.target.port}",
        timeout=1,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        for attempt in range(60):
            try:
                response = client.get("/api/v2/info")
                if (
                    response.status_code == 200
                    and BoardInfo.model_validate(response.json()).version == "v2.6.0"
                ):
                    return
            except httpx.HTTPError, ValueError:
                pass
            if attempt != 59:
                time.sleep(1)
    raise BackupError("Pinned board did not become ready within the bounded deadline")


def bootstrap_board(plan: VikunjaPlan, spec: VikunjaSpec, provider: str) -> None:
    runtime = plan.target.base / "runtime"
    compose = board_compose(plan, provider)
    if private_board_file(plan.target.base / ".pending-bootstrap").decode() != str(
        plan.run_id
    ):
        raise BackupError("Board bootstrap marker belongs to another operation")
    try:
        command([*compose, "up", "-d", "--no-build", "--pull=never", "board"])
        wait_for_board(plan)
        result = bootstrap_accounts(f"http://127.0.0.1:{plan.target.port}", spec)
        write_private(
            runtime / "identity.json", result.identity.model_dump_json().encode()
        )
        write_private(
            runtime / "tooling-token", result.token.get_secret_value().encode()
        )
    finally:
        try:
            config_file = runtime / "config.json"
            config_file.write_text(
                configuration(plan, controller_port=plan.access_port).model_dump_json()
            )
            config_file.chmod(0o644)
        finally:
            command(["podman", "stop", "--time=30", plan.target.project + "_board_1"])
    command(
        [*compose, "up", "-d", "--no-recreate", "--no-build", "--pull=never", "board"]
    )
    wait_for_board(plan)


def verify_board(plan: VikunjaPlan, spec: VikunjaSpec | None = None) -> None:
    wait_for_board(plan)
    runtime = plan.target.base / "runtime"
    owner = (
        spec.owner
        if spec
        else VikunjaAccount.model_validate_json(
            private_board_file(runtime / "owner.json")
        )
    )
    identity = BoardBootstrapResult.model_validate(
        {
            "identity": json.loads(private_board_file(runtime / "identity.json")),
            "token": private_board_file(runtime / "tooling-token").decode(),
        }
    )
    with httpx.Client(
        base_url=f"http://127.0.0.1:{plan.target.port}",
        timeout=20,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        info = BoardInfo.model_validate(request(client, "GET", "/api/v2/info").json())
        if (
            info.version != "v2.6.0"
            or info.link_sharing_enabled
            or info.email_reminders_enabled
            or info.auth.local.registration_enabled
            or not info.auth.local.enabled
        ):
            raise BackupError("Board public capability settings are unsafe")
        login(client, owner)
        user = BoardUser.model_validate(request(client, "GET", "/api/v2/user").json())
        if (
            user.id != identity.identity.owner_id
            or user.username != plan.owner_username
        ):
            raise BackupError("Board owner login resolves to another account")
        bots = BoardPage[BoardUser].model_validate(
            request(client, "GET", "/api/v2/user/bots").json()
        )
        if bots.total_pages > 1 or not any(
            bot.id == identity.identity.tooling_id
            and bot.username == plan.tooling_username
            and bot.bot_owner_id == user.id
            for bot in bots.items
        ):
            raise BackupError("Board tooling ownership differs")
        client.headers["Authorization"] = "Bearer " + identity.token.get_secret_value()
        projects = BoardPage[BoardProject].model_validate(
            request(client, "GET", "/api/v2/projects").json()
        )
        if projects.total_pages > 1 or {
            project.id for project in projects.items if project.id > 0
        } != {identity.identity.project_id}:
            raise BackupError(
                "Board tooling token no longer resolves only the real backlog"
            )
        if client.get("/api/v2/tokens").status_code not in {401, 403}:
            raise BackupError("Board tooling credential can manage tokens")
    binding = (
        command(["podman", "port", f"{plan.target.project}_board_1", "3456/tcp"])
        .decode()
        .strip()
    )
    expected = {
        f"127.0.0.1:{plan.target.port}",
        f"{plan.target.bind_address}:{plan.target.port}",
    }
    if set(binding.splitlines()) != expected:
        raise BackupError(
            "Board listeners differ from the reviewed loopback/LAN target"
        )
    image_id = (
        command(
            [
                "podman",
                "inspect",
                "--format={{.Image}}",
                plan.target.project + "_board_1",
            ]
        )
        .decode()
        .strip()
    )
    if image_id.removeprefix("sha256:") != plan.image_id.removeprefix("sha256:"):
        raise BackupError(
            "Running board image differs from the verified immutable identity"
        )


def finalize_board(plan: VikunjaPlan, spec: VikunjaSpec) -> VikunjaDeployment:
    verify_board(plan, spec)
    base, runtime = plan.target.base, plan.target.base / "runtime"
    if (base / "current.json").exists():
        return preflight_board(plan).current
    if private_board_file(base / ".pending-bootstrap").decode() != str(plan.run_id):
        raise BackupError("Board verification marker belongs to another operation")
    identity = BoardBootstrapResult.model_validate(
        {
            "identity": json.loads(private_board_file(runtime / "identity.json")),
            "token": private_board_file(runtime / "tooling-token").decode(),
        }
    ).identity
    env = dict(
        line.split("=", 1)
        for line in private_board_file(runtime / "compose.env").decode().splitlines()
    )
    current = VikunjaDeployment(
        target=plan.target,
        deployment_commit=plan.deployment_commit,
        image_id=plan.image_id,
        secret_generation=plan.secret_generation,
        signing_secret_sha256=plan.signing_secret_sha256,
        credentials_sha256=plan.credentials_sha256,
        configuration_sha256=plan.configuration_sha256,
        compose_sha256=plan.compose_sha256,
        compose_env_sha256=digest(runtime / "compose.env"),
        database_directory=env["VIKUNJA_DATABASE_DIRECTORY"],
        files_directory=env["VIKUNJA_FILES_DIRECTORY"],
        identity=identity,
        verified_at=datetime.now(UTC),
    )
    write_private(base / "current.json", current.model_dump_json().encode())
    (base / ".pending-bootstrap").unlink()
    return current


def rebind_board(
    plan: VikunjaPlan,
    address: IPv4Address,
    provider: str,
    compose_file: Path,
    *,
    receipt: BackupReceipt | None = None,
    check: bool = False,
) -> BoardLanOperation:
    current = preflight_board(plan).current
    if current is None:
        raise BackupError("LAN access requires an existing verified board")
    target = VikunjaTarget(
        project=plan.target.project,
        base=plan.target.base,
        port=plan.target.port,
        bind_address=address,
        manage_systemd=plan.target.manage_systemd,
        reserve_bytes=plan.target.reserve_bytes,
    )
    runtime = target.base / "runtime"
    if compose_file.resolve() != compose_file or not compose_file.is_file():
        raise BackupError("LAN Compose source must be canonical")
    source = compose_file.read_bytes()
    if (runtime / "compose.yaml").read_bytes() != board_compose_contents(
        source, current.target.bind_address
    ):
        raise BackupError("LAN updates cannot change unrelated Compose configuration")
    if target == current.target:
        verify_board(plan)
        return BoardLanOperation(changed=False, current=current)
    if check:
        return BoardLanOperation(changed=True, current=current)
    if (
        receipt is None
        or receipt.application != "vikunja"
        or receipt.purpose != "predeploy"
    ):
        raise BackupError("LAN access requires a verified pre-deploy board backup")
    if private_board_file(target.base / ".operation-lock/owner").decode() != str(
        receipt.run_id
    ):
        raise BackupError("LAN access requires the backup run's shared operation lock")
    writer = target.project + "_board_1"
    if (
        command(
            [
                "podman",
                "inspect",
                "--format={{.State.Running}} {{.State.Paused}}",
                writer,
            ]
        ).strip()
        != b"false false"
    ):
        raise BackupError(
            "The backed-up board writer must be stopped before changing listeners"
        )
    updated = plan.model_copy(deep=True)
    updated.run_id = receipt.run_id
    updated.target = target
    config = configuration(updated, controller_port=updated.access_port)
    fingerprint = hashlib.sha256(target.model_dump_json().encode())
    fingerprint.update(config.model_dump_json().encode())
    fingerprint.update(updated.project_title.encode())
    updated.configuration_sha256 = fingerprint.hexdigest()
    compose = board_compose_contents(source, address)
    updated.compose_sha256 = hashlib.sha256(compose).hexdigest()
    changes = [
        (runtime / "compose.yaml", compose),
        (runtime / "config.json", config.model_dump_json().encode()),
        (runtime / "deployment-plan.json", updated.model_dump_json().encode()),
    ]
    originals = [
        (path, path.read_bytes(), path.stat().st_mode & 0o777) for path, _ in changes
    ]
    manifest_file = target.base / "current.json"
    originals.append((manifest_file, private_board_file(manifest_file), 0o600))
    pending = target.base / ".pending-network"
    write_private(pending, str(receipt.run_id).encode())

    def replace_file(path: Path, contents: bytes, mode: int) -> None:
        temporary = path.with_name(f".{path.name}.{receipt.run_id}.tmp")
        write_private(temporary, contents)
        temporary.chmod(mode)
        temporary.replace(path)

    try:
        for path, contents in changes:
            replace_file(path, contents, 0o644 if path.name == "config.json" else 0o600)
        command(
            [
                *board_compose(updated, provider),
                "up",
                "-d",
                "--force-recreate",
                "--no-build",
                "--pull=never",
                "board",
            ]
        )
        verify_board(updated)
        with httpx.Client(
            base_url=f"http://127.0.0.1:{target.port}", timeout=20, trust_env=False
        ) as client:
            html = request(client, "GET", "/").text
            api_url = config.service.publicurl.rstrip("/") + "/api/v1"
            if f"window.API_URL = '{api_url}'" not in html:
                raise BackupError("Board frontend still points at another API endpoint")
        current.target = target
        current.configuration_sha256 = updated.configuration_sha256
        current.compose_sha256 = updated.compose_sha256
        current.verified_at = datetime.now(UTC)
        replace_file(manifest_file, current.model_dump_json().encode(), 0o600)
    except BackupError, OSError, ValueError:
        try:
            for path, contents, mode in originals:
                replace_file(path, contents, mode)
            command(
                [
                    *board_compose(plan, provider),
                    "up",
                    "-d",
                    "--force-recreate",
                    "--no-build",
                    "--pull=never",
                    "board",
                ]
            )
            verify_board(plan)
        except BackupError, OSError, ValueError:
            command(["podman", "stop", "--time=30", writer])
            raise BackupError(
                "LAN rollback failed; board stopped and pending marker retained for operator review"
            ) from None
        pending.unlink()
        raise BackupError(
            "LAN update failed; the verified previous listeners were restored"
        ) from None
    pending.unlink()
    return BoardLanOperation(changed=True, current=current)


def board_recovery_spec(
    plan: VikunjaPlan, purpose: Literal["weekly", "predeploy"] = "weekly"
) -> CaptureSpec:
    current = preflight_board(plan).current
    if current is None:
        raise BackupError("Board recovery requires a verified deployment manifest")
    runtime = plan.target.base / "runtime"
    return CaptureSpec(
        application="vikunja",
        purpose=purpose,
        run_id=plan.run_id,
        build_commit=current.deployment_commit,
        image_id=current.image_id,
        writers=[f"{plan.target.project}_board_1"],
        database={
            "kind": "sqlite",
            "storage": FileSource(volume=f"{plan.target.project}_database"),
            "filename": "vikunja.db",
        },
        files=FileSource(volume=f"{plan.target.project}_attachments"),
        configuration=[
            {"name": name, "path": path}
            for name, path in (
                ("configuration", runtime / "config.json"),
                ("secrets", runtime / "signing-secret"),
                ("compose", runtime / "compose.yaml"),
                ("compose_env", runtime / "compose.env"),
                ("owner_credentials", runtime / "owner.json"),
                ("tooling_token", runtime / "tooling-token"),
                ("identity", runtime / "identity.json"),
                ("deployment", plan.target.base / "current.json"),
                ("deployment_plan", runtime / "deployment-plan.json"),
            )
        ],
        helper_image=plan.helper_image_id,
    )
