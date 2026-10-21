# Python observability patterns

Executable patterns for the [observability contract](../observability.md). Adapt
module paths and logger names to the target; keep the behavior.

Import paths below are the real ones from the shared library named in the
[Python index](../index.md). The application
declares `asgi-correlation-id`, `python-json-logger`, `boto3`, `botocore`, and
the Logfire extras it imports. `boto3-stubs[secretsmanager]` belongs in the dev
group when the bounded secret helper is used.

## Logging configuration

One function builds both the mandatory console foundation and the Logfire
variant:

```python
from circlex.logging import builder, presets


def get_logging_config(settings: Settings, *, with_logfire: bool = False) -> dict[str, object]:
    handlers = ["console", *(["logfire"] if with_logfire else [])]
    extra_handlers = (
        {
            "logfire": {
                "class": "logfire.LogfireLoggingHandler",
                "level": settings.log_level,
                "filters": ["correlation_id", "endpoint", "request_data", "gunicorn_error"],
            }
        }
        if with_logfire
        else None
    )
    base = presets.standard_console_config(
        debug_mode=settings.debug_mode,
        root_log_level=settings.log_level,
        extra_handlers=extra_handlers,
        app_specific_loggers=[
            ("app", settings.log_level, handlers),
            ("circlex", settings.log_level, handlers),
        ],
    )
    log_builder = builder.LoggingConfigBuilder(base_config_dict=base)
    log_builder.with_logger(
        "uvicorn.access",
        level=settings.log_level,
        handlers=handlers,
        replace_handlers=True,
    )
    log_builder.with_logger(
        "httpx",
        level="WARNING",
        handlers=handlers,
        replace_handlers=True,
    )
    return log_builder.build()
```

The shared preset already defines root, Gunicorn, Uvicorn, and FastAPI loggers
and adds the four standard filters to every handler. List every
application/library namespace that must survive its
`disable_existing_loggers=True`. The auth library's namespace is required when
auth is installed. An omission fails
silently: a logger created at import time and left out of the configuration is
disabled, the request still answers correctly, and only its records disappear
from Logfire. Assert the complete registry in a test instead of trusting a
visible terminal log. Together with
`RequestMiddleware`, `RequestDataFilter` enriches records emitted during a
request with redacted `http.request.*`, `http.response.*`, timing, and
correlation data.

Gunicorn must not construct this dictionary or import full settings in the
master. Follow the shared
[runtime pattern](runtime-patterns.md#worker-local-logging): the ASGI
application configures Logfire during worker-local import, and
`post_worker_init` reapplies the complete dictionary after the server has
initialized its handlers. Use `with_logfire=False` until the service selects
Logfire. Workers and CLIs call `logging.config.dictConfig(...)` before their
first log. An existing programmatic Uvicorn entrypoint passes the same
dictionary through `log_config`; do not create a wrapper only for this.

For a brownfield service that intentionally runs bare
`uvicorn app.main:app`, applying `dictConfig` during the application import is a
valid fallback: Uvicorn has already run `configure_logging()`, so the
application config wins. Keep it before the application's first log. Changing
that config while `--reload` is active still needs a full process restart.

For brownfield logging, verify the result instead of preserving overrides
blindly:

- `uvicorn.access`, `uvicorn.error`, and `fastapi` must reach both console and
  Logfire;
- an INFO-suppression or `to_logfire` promotion filter must exempt those server
  loggers, otherwise the unmarked access record disappears;
- a batch/CLI may reuse the same builder and apply it with `dictConfig`; omit
  only request/server loggers that truly do not exist in that process.

The missing-access-record failure occurred in multiple real integrations:
application logs looked healthy while the canonical per-request record never
reached Logfire.

## Bounded secret read

The example below reads a cloud secret manager. Platform-managed environment
variables satisfy the same seam with no client at all; what is fixed is the
bounded read and the explicit failure states, not the backend.

Until the shared library exposes a bounded client, keep this adapter
application-owned:

```python
import json
from functools import cache
from typing import TYPE_CHECKING, cast

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from mypy_boto3_secretsmanager.client import SecretsManagerClient

_BOUNDED_CONFIG = Config(
    connect_timeout=5,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
)


@cache
def _get_session() -> boto3.session.Session:
    return boto3.session.Session()


@cache
def _get_client(region_name: str) -> SecretsManagerClient:
    return _get_session().client(
        "secretsmanager",
        region_name=region_name,
        config=_BOUNDED_CONFIG,
    )


def get_secret_bounded(secret_name: str, region_name: str) -> dict[str, object]:
    response = _get_client(region_name).get_secret_value(SecretId=secret_name)
    return cast(dict[str, object], json.loads(response["SecretString"]))
```

The caches are per process. Tests assert the three `Config` limits, session and
per-region client reuse, JSON parsing, and propagation of timeout/client errors.

## Logfire setup and token states

Add the setting when Logfire is selected:

```python
logfire_token_secret_name: str = Field(default="")
```

An empty default is the deliberate `provisioning pending` state. After an
administrator creates the secret and gives the project its identifier, configure
the field with that exact value. The team convention is
`logfire/<service>/write`. Do not
copy a non-empty default into a new service before provisioning: it would declare
a missing secret and correctly turn deployed startup into `misconfigured`.

```python
from functools import lru_cache

import logfire

SAFE_AUTH_FIELDS = {
    "auth.result",
    "auth.mode",
    "auth.enforced",
    "auth.type",
    "auth.subject",
    "auth.display_name",
    "auth.email",
    "auth.roles",
    "auth.scopes",
    "auth.audience",
    "auth.issuer",
    "auth.app_id",
}


def keep_safe_auth(match: logfire.ScrubMatch) -> object | None:
    return match.value if match.path and match.path[-1] in SAFE_AUTH_FIELDS else None


@lru_cache(maxsize=1)
def get_logfire_client() -> logfire.Logfire:
    settings = get_settings()
    secret_name = settings.logfire_token_secret_name
    logfire_environment = "staging" if settings.env == "stg" else settings.env
    scrubbing = logfire.ScrubbingOptions(callback=keep_safe_auth)
    if not secret_name:
        return logfire.configure(send_to_logfire=False, scrubbing=scrubbing)

    try:
        payload = get_secret_bounded(secret_name, settings.aws_region)
        token = payload["LOGFIRE_WRITE_TOKEN"]
        if not isinstance(token, str) or not token:
            raise ValueError("empty LOGFIRE_WRITE_TOKEN")
    except Exception:
        if settings.env not in {"local", "test"}:
            raise
        return logfire.configure(send_to_logfire=False, scrubbing=scrubbing)

    return logfire.configure(
        token=token,
        send_to_logfire=True,
        environment=logfire_environment,
        service_name=settings.service_name,
        service_version=settings.code_version,
        scrubbing=scrubbing,
    )
```

No secret name means no AWS call. A declared bad secret fails deployed startup;
local and test may stay dark. Never replace either state with a fake token.
`settings.code_version` is the immutable image tag or revision in deployed
environments and may fall back to `APP_VERSION` only for local execution.
`get_logfire_client()` owns the per-process singleton; caching `get_settings()`
does not. The default scrubber matches names containing `auth`, so the callback
exempts only the exact safe canonical fields and leaves all other redaction enabled.
When a legacy service stores `env="stg"`, keep its existing
`logfire_environment = "staging"` mapping and pass that canonical value to
`logfire.configure`; do not rename the application's deployment environment as a
side effect of this integration.

## FastAPI instrumentation

Logfire captures parsed endpoint arguments unless the mapper removes them. Keep
only safe validation-error fields:

```python
from typing import Any

from circlex.logfire import (
    DEFAULT_REQUEST_HEADERS,
    DEFAULT_RESPONSE_HEADERS,
    DEFAULT_SANITIZED_HEADERS,
    init_logfire_system_metrics,
)
from fastapi import FastAPI, Request


def safe_request_attributes(
    _request: Request,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    return {
        "errors": [
            {key: error[key] for key in ("loc", "type", "msg") if key in error}
            for error in attributes.get("errors", [])
        ]
    }


def instrument_app(
    app: FastAPI,
    logfire_client: logfire.Logfire,
    api_prefix: str,
) -> None:
    init_logfire_system_metrics(
        logfire_client,
        app,
        api_prefix,
        # capture_headers stays off: it captures every header, bypassing the
        # allowlist below. request_headers/response_headers are the allowlist.
        request_attributes_mapper=safe_request_attributes,
        request_headers=list(DEFAULT_REQUEST_HEADERS),
        response_headers=list(DEFAULT_RESPONSE_HEADERS),
        sanitize_fields=list(DEFAULT_SANITIZED_HEADERS),
    )
```

Call `get_logfire_client()` before logs or instrumented clients. Call
`instrument_app()` once, after middleware, handlers, and routers and before the
first ASGI scope. `instrument_fastapi()` patches `build_middleware_stack`, which
Starlette caches on that first scope; lifespan is already too late and produces
zero FastAPI request spans. Do not also call a combined helper that cannot
receive the mapper — it would instrument FastAPI twice.

Pass the configured client to the shared long-lived outbound-client factories
with `logfire_capture_headers=False`. The shared allowlist and credential
denylist then cover both inbound and outbound headers. Do not add global
`instrument_httpx()`. Setting `logfire_capture_headers=True` bypasses that
narrow capture path and can expose the outbound `Authorization` bearer.
Clients built without `logfire_client=` emit no egress spans; this caused a
real multi-service observability regression in production.

## Threads and processes

`instrument_system_metrics()` carries OTel context through
`ThreadPoolExecutor`, but not the application `ContextVar`s that produce
`x-user-id` and request metadata. When a worker makes outbound calls, use
`circlex.utils.threading_`'s `submit_with_contextvars(executor, fn,
contextvars=(...))`, passing `correlation_id`, `outbound_context_var` and
`audit_context_var` as the `contextvars` argument; it resets values after each
task to prevent identity bleed between reused threads.

For `multiprocessing.Pool`, preserve the exact shared initializer:

```python
from logfire.propagate import get_context

from circlex.logfire import attach_logfire_context_in_pool_initializer

with mp.Pool(
    processes=workers,
    initializer=attach_logfire_context_in_pool_initializer(
        get_context(),
        existing_initializer,
    ),
    initargs=existing_initargs,
) as pool:
    pool.map(worker, tasks)
```

For a raw subprocess, keep the adapter in the application:

```python
TRACE_CONTEXT_ENV = "APP_TRACE_CONTEXT"  # replace APP with the service namespace
_PROPAGATOR = TraceContextTextMapPropagator()


def capture_for_env() -> dict[str, str]:
    carrier = get_context()
    return {TRACE_CONTEXT_ENV: json.dumps(carrier)} if carrier else {}


def attach_from_env() -> bool:
    raw = os.environ.get(TRACE_CONTEXT_ENV)
    if not raw:
        return False
    _otel_attach(_PROPAGATOR.extract(json.loads(raw)))
    return True
```

Merge `capture_for_env()` into the child's environment. In the child, configure
Logfire first and call `attach_from_env()` once. Raw
`opentelemetry.context.attach()` is intentional: Logfire's context-manager
helper detaches when the manager is released, while the child must keep the
parent context for its whole process lifetime. Without a carrier the child
starts a normal root trace.
