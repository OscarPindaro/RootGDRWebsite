import httpx
from pydantic import BaseModel, SecretStr

from backend.health.schemas import BuildInfo, Readiness
from backend.schemas import PagedResponse
from backend.worlds.schemas import WorldResponse


class ProductionSmokeError(RuntimeError):
    pass


class ProductionSmokeResult(BaseModel):
    build: BuildInfo
    checked_paths: list[str]


async def verify_production(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: SecretStr,
    expected_commit: str | None = None,
) -> ProductionSmokeResult:
    ready = await client.get("/health/ready")
    if (
        ready.status_code != 200
        or Readiness.model_validate(ready.json()).status != "ready"
    ):
        raise ProductionSmokeError("Application dependencies are not ready")
    version_response = await client.get("/version")
    if version_response.status_code != 200:
        raise ProductionSmokeError("Build information is unavailable")
    build = BuildInfo.model_validate(version_response.json())
    if expected_commit is not None and build.commit != expected_commit:
        raise ProductionSmokeError(
            "The running build does not match the selected commit"
        )
    login = await client.post(
        "/auth/login", json={"email": email, "password": password.get_secret_value()}
    )
    if login.status_code != 200:
        raise ProductionSmokeError(f"Password login failed ({login.status_code})")
    paths = ["/health/ready", "/version", "/api/worlds/", "/worlds"]
    worlds_response = await client.get("/api/worlds/")
    if worlds_response.status_code != 200:
        raise ProductionSmokeError("Authenticated world listing failed")
    worlds = PagedResponse[WorldResponse].model_validate(worlds_response.json()).data
    if worlds:
        world = worlds[0]
        paths.extend([f"/api/worlds/{world.id}", f"/worlds/{world.id}"])
        if world.image_url is not None:
            if not world.image_url.startswith("/api/"):
                raise ProductionSmokeError(
                    "World image URL is not an application API path"
                )
            paths.append(world.image_url)
    for path in paths[3:]:
        response = await client.get(path)
        if response.status_code != 200:
            raise ProductionSmokeError(
                f"Authenticated read failed: {path} ({response.status_code})"
            )
    return ProductionSmokeResult(build=build, checked_paths=paths)
