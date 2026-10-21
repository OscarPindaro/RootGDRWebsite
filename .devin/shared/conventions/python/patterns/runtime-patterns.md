# Python ASGI runtime patterns

Executable team patterns for [backend](../backend.md), [stack](../stack.md), and
[observability](../observability.md). Adapt paths, ports, timeouts, and the
measured worker count; keep the process boundaries and proof.

## Supported Gunicorn shape

Use the separate `uvicorn-worker`; never the deprecated
`uvicorn.workers.UvicornWorker`.

A production service reproduced
[Gunicorn issue #3661](https://github.com/benoitc/gunicorn/issues/3661), where a
request with `Connection: close` left an active connection counted and made
the native Gunicorn 26 `asgi` worker wait the full graceful timeout. Adopt that
worker only after the upstream fix and the proof below pass.

Split runtime ownership into four small modules.

### Master-safe settings

`app/config/gunicorn_settings.py` imports only Pydantic and the standard
library. It must not import full application settings, the shared library, AWS, Logfire, or
the ASGI app:

```python
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GunicornSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    log_level: str = "INFO"
    gunicorn_port: int = Field(default=80, alias="port")
    gunicorn_workers: int = Field(ge=1)
    gunicorn_worker_class: Literal["app.gunicorn_worker.ConfiguredUvicornWorker"] = (
        "app.gunicorn_worker.ConfiguredUvicornWorker"
    )
    gunicorn_access_logfile: str = "-"
    gunicorn_timeout: int = Field(default=600, ge=1)
    gunicorn_graceful_timeout: int = Field(default=600, ge=1)
    gunicorn_keepalive: int = Field(default=960, ge=1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gunicorn_bind(self) -> str:
        return f"0.0.0.0:{self.gunicorn_port}"
```

Full `Settings` may inherit this class; the launcher instantiates only this
master-safe base.

### Typed launcher

`app/run_gunicorn.py` validates values, then replaces itself so Gunicorn remains
PID 1:

```python
import os
import sys

from app.config.gunicorn_settings import GunicornSettings


def build_gunicorn_command(settings: GunicornSettings) -> list[str]:
    return [
        sys.executable,
        "-m",
        "gunicorn",
        "--config",
        "app/gunicorn_conf.py",
        "--bind",
        settings.gunicorn_bind,
        "--workers",
        str(settings.gunicorn_workers),
        "--worker-class",
        settings.gunicorn_worker_class,
        "--timeout",
        str(settings.gunicorn_timeout),
        "--graceful-timeout",
        str(settings.gunicorn_graceful_timeout),
        "--keep-alive",
        str(settings.gunicorn_keepalive),
        "--log-level",
        settings.log_level.lower(),
        "--access-logfile",
        settings.gunicorn_access_logfile,
        "app.main:app",
    ]


def main() -> None:
    command = build_gunicorn_command(GunicornSettings())
    os.execv(sys.executable, command)  # noqa: S606 - fixed interpreter and arguments


if __name__ == "__main__":
    main()
```

Local, debug, Docker, and documented commands all use
`python -m app.run_gunicorn`.

### Worker adapter

Keep ASGI runtime choices explicit in `app/gunicorn_worker.py`:

```python
from typing import ClassVar

from uvicorn_worker import UvicornWorker  # type: ignore[import-untyped]


class ConfiguredUvicornWorker(UvicornWorker):
    CONFIG_KWARGS: ClassVar[dict[str, str]] = {
        "http": "auto",
        "lifespan": "on",
        "loop": "uvloop",
    }
```

Declare `uvicorn-worker` and `uvloop` directly.

`uvloop` is load-bearing, not a speed tweak. With plain asyncio,
[CPython #140947](https://github.com/python/cpython/issues/140947) can leak the
active OTel context into the connection reader after a body over 64 KB; later
requests on a long keep-alive (e.g. 960 s) can join the wrong Logfire trace.
The same fix is proven live on several production services. Test that the
configured worker keeps `loop="uvloop"` and `lifespan="on"`.

### Worker-local logging

`app/gunicorn_conf.py` contains only hooks whose function bodies import the
application:

```python
import logging.config


def post_worker_init(_worker: object) -> None:
    from app.config.settings import get_settings  # noqa: PLC0415 - post-fork boundary
    from app.log.logging_conf import get_logging_config  # noqa: PLC0415

    logging.config.dictConfig(get_logging_config(get_settings()))
```

The app applies logging and configures Logfire during worker-local import,
before its first log. This hook restores final handlers after server
initialization. Keep `get_settings()` and logging-dictionary construction
worker-local unless the measured warm-up below applies. Always keep AWS,
Logfire configuration, logging installation, and application preload out of
the master.

### Profiled master import warm-up

Keep `preload_app=False`. When repeated production-like measurements show that
duplicated import and configuration parsing prevents a hard startup target,
Gunicorn `on_starting` may warm only that pure graph before workers fork. This
is a measured exception, not the default.

Run the hook in a fresh subprocess that blocks application import,
boto3/botocore session and client construction, `socket.socket`,
`threading.Thread.start`, and `logfire.configure`. Require the intended settings
and logging modules to be cached, with no application, AWS helper, default
session, Logfire client, network, or thread retained. Constructor blockers are
load-bearing: post-state assertions alone miss a short-lived resource created
and closed inside the hook. Keep complete logging installation in
`post_worker_init`.

## Native macOS development

Gunicorn creates a replacement worker with `os.fork()` (`gunicorn/arbiter.py`) and exposes no spawn
setting, so changing Python's start method cannot affect it. Python documents `fork` as unsafe on
macOS once higher-level system APIs are involved, and a replacement worker can abort in Apple's
Objective-C runtime before application startup. Never set
`OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` to make that look healthy: it suppresses the abort and
repairs none of the locks, threads, or framework state the child inherited.

Uvicorn builds its workers from `multiprocessing.get_context("spawn")`
(`uvicorn/_subprocess.py`), so native development runs Uvicorn instead: expose an explicit `run-dev`
target with one worker and reload, and leave `make run` and the container command on the Gunicorn
launcher — which process model a developer is exercising must stay visible, not depend on the host.
Add a second target with supervised spawn workers and no reload when worker replacement itself must
be exercised locally; a launcher offering both rejects reload combined with several workers instead
of letting Uvicorn reinterpret the request. Linux production and every release proof stay on
Gunicorn. Verified on Gunicorn 26.0 and Uvicorn 0.51.

## Container and deployed code identity

The image owns one command and code identity:

```dockerfile
ARG CODE_VERSION=local
ENV CODE_VERSION=${CODE_VERSION}
CMD ["python", "-m", "app.run_gunicorn"]
```

The pipeline passes an immutable deployed identity, such as the image tag or
source revision, as `CODE_VERSION`; application SemVer is only the local
fallback:

```python
code_version: str = Field(default=APP_VERSION, alias="CODE_VERSION", min_length=1)
```

Logfire `service_version` must equal that injected deployed identity.

## Process sizing and long-lived work

Use the measured worker-sizing rule from [stack](../stack.md), never a CPU
formula.

Every worker imports the app and runs lifespan. During a rolling deployment,
old and new tasks overlap, so a lifespan background consumer can run
`tasks * workers` times. Process sizing and singleton leadership are separate
decisions.

For one PostgreSQL `LISTEN` consumer per logical channel:

- derive a stable signed-bigint advisory-lock key;
- borrow a connection and call `pg_try_advisory_lock`;
- the winner keeps that same dedicated connection and registers `LISTEN`;
- a standby returns the connection before waiting and retries with bounded
  delay;
- cleanup removes the listener, unlocks, and releases the connection;
- session death releases the lock so another process can take over.

This prevents duplicate active listeners. It does not make `LISTEN/NOTIFY`
durable or exactly-once; guaranteed delivery needs an outbox and idempotency.

## Production-like proof

Run this proof after changing the process manager, worker, Docker command,
startup/lifespan order, logging handlers, Logfire setup, code-version wiring,
or long-lived listener ownership:

1. Run deterministic gates with the locked environment.
2. Start the documented entrypoint against development.
   Require every worker to complete lifespan and one listener leader per
   channel.
3. Build and run the exact immutable Linux image and its configured `CMD`.
   Host-only startup does not prove the ECS process model.
4. For a startup target, predefine the repetitions and measure embedded process
   timestamps from the process-manager start through lifespan completion for
   every required worker. In the deployed environment, replace the task at
   least three times with the same image digest, worker count, CPU, and memory;
   judge the worst valid run. Report image pull, scheduler delay, target
   registration, and draining separately. A green deployment is not startup
   performance evidence.
5. Resolve the route from OpenAPI. Send uniquely tagged database-backed reads
   and applicable read-only POSTs using current models or fixtures. Get explicit
   approval before any call whose semantics can mutate state. Use
   the team M2M identity designated for verification calls. <!-- TODO(circeus): name it once it exists. -->
6. On one keep-alive connection, send a harmless request body over 64 KB and a
   second request. Use a test-only endpoint when no safe real endpoint accepts
   it. Require separate correct root traces; neither request may join the
   other's trace.
7. In Logfire, require exactly one FastAPI root span and one
   `uvicorn.access` record per non-health probe, with the same trace ID, route,
   status, environment, service name, and injected code version. Check auth
   attributes and credential redaction when auth applies. The shared logging preset intentionally
   filters health, docs, metrics, and OpenAPI paths; do not use them to prove
   access-log emission.
8. Compare access-log attribute and resource-attribute keys with a recent
   staging record. Removed or renamed keys need an approved schema migration.
9. Inspect the built image: `CODE_VERSION`, application settings, and Logfire
   `service.version` must equal the injected deployed identity. When that
   identity is a source revision, require it to match the revision component of
   the immutable image tag, not the full environment-suffixed tag.
10. In the Linux container, terminate one worker. Require replacement startup,
   health 200 throughout, listener takeover when applicable, and clean final
   shutdown with exit code zero.
11. For singleton listeners, use disposable PostgreSQL and a capture-only sink.
   Start two masters with multiple workers, prove one lock owner, one output per
   notification, kill the leader, and prove takeover and a second single output.

On macOS, replacement forks can abort with `objc_initializeAfterForkError` (see
[native macOS development](#native-macos-development)); record that local limitation and use the
Linux image as the release gate.
Gunicorn/Uvicorn may log `Error while closing socket [Errno 9] Bad file
descriptor` during shutdown on macOS or Linux. Accept it only as an INFO record
with no traceback or hang, completed lifespan shutdown for every worker, and
master exit zero. Any AWS occurrence or different context needs investigation.

When integration tests own async pools, clients, or services, create, use, and
close them on compatible pytest event loops; function scope is the safe
default. FastAPI dependency overrides expose only typed parameters that FastAPI
can resolve—an unused untyped parameter becomes a required request parameter
and can cause false 422 responses.
