"""Check that htmx encodings agree with FastAPI endpoint payloads."""

from __future__ import annotations

import re
import signal
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Optional

import typer
from fastapi.params import File, Form
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict
from rich.console import Console

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
CODE = "E930"
DEFAULT_COMPONENTS_DIR = Path("src/frontend/components")

TAG = re.compile(r"<(?!!|/)(?:[^>\"']|\"[^\"]*\"|'[^']*')+>", re.DOTALL)
ATTRIBUTE = re.compile(r"\b([\w:-]+)\s*=\s*([\"'])(.*?)\2", re.DOTALL)
EXPRESSION = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)
METHODS = ("post", "put", "patch")

err_console = Console(stderr=True, soft_wrap=True)


class PayloadKind(StrEnum):
    NONE = "none"
    JSON = "json"
    FORM = "form"
    UPLOAD = "upload"
    INVALID_JSON = "non-Pydantic JSON"


class HtmxRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    component: Path
    line: int
    method: str
    path: str
    ignores_json_enc: bool = False
    multipart: bool = False


class RoutePayload(BaseModel):
    path: str
    method: str
    kind: PayloadKind


class Diagnostic(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    line: int
    message: str


def _handle_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(EXIT_ERROR)


signal.signal(signal.SIGTERM, _handle_sigterm)


def _attributes(tag: str) -> dict[str, str]:
    return {match.group(1).lower(): match.group(3) for match in ATTRIBUTE.finditer(tag)}


def template_requests(components_dir: Path) -> list[HtmxRequest]:
    """Read htmx write requests and their effective encoding attributes."""
    requests: list[HtmxRequest] = []
    for component in sorted(components_dir.rglob("*.jinja")):
        source = component.read_text(encoding="utf-8")
        for tag_match in TAG.finditer(source):
            tag = tag_match.group()
            attrs = _attributes(tag)
            request = next(
                (
                    (method, attrs[f"hx-{method}"])
                    for method in METHODS
                    if f"hx-{method}" in attrs
                ),
                None,
            )
            if request is None:
                continue
            method, path = request
            extensions = {item.strip() for item in attrs.get("hx-ext", "").split(",")}
            requests.append(
                HtmxRequest(
                    component=component,
                    line=source[: tag_match.start()].count("\n")
                    + tag[: tag.lower().index(f"hx-{method}")].count("\n")
                    + 1,
                    method=method.upper(),
                    path=path,
                    ignores_json_enc="ignore:json-enc" in extensions,
                    multipart=attrs.get("hx-encoding", "").lower()
                    == "multipart/form-data",
                )
            )
    return requests


def _is_pydantic(annotation: object) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def route_payloads(routes: list[object]) -> list[RoutePayload]:
    """Describe write-route payloads from FastAPI's resolved signatures."""
    found: list[RoutePayload] = []
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        body = route.dependant.body_params
        if any(isinstance(param.field_info, File) for param in body):
            kind = PayloadKind.UPLOAD
        elif any(isinstance(param.field_info, Form) for param in body):
            kind = PayloadKind.FORM
        elif body and all(_is_pydantic(param.field_info.annotation) for param in body):
            kind = PayloadKind.JSON
        elif body:
            kind = PayloadKind.INVALID_JSON
        else:
            kind = PayloadKind.NONE
        for method in sorted(route.methods & {"POST", "PUT", "PATCH"}):
            found.append(RoutePayload(path=route.path, method=method, kind=kind))
    return found


def _segments(path: str, *, template: bool) -> list[str] | None:
    path = path.strip().split("?", 1)[0].split("#", 1)[0]
    if template and EXPRESSION.fullmatch(path):
        return None
    parts = path.strip("/").split("/") if path.strip("/") else []
    if template:
        segments: list[str] = []
        for index, part in enumerate(parts):
            if not EXPRESSION.search(part):
                segments.append(part)
            else:
                segments.append("**" if index == 0 else "*")
        return segments
    return [
        "*" if part.startswith("{") and part.endswith("}") else part for part in parts
    ]


def _matches(request: list[str], route: list[str]) -> bool:
    if not request:
        return not route
    head, tail = request[0], request[1:]
    if head == "**":
        return any(_matches(tail, route[index:]) for index in range(1, len(route) + 1))
    if not route or head != "*" and route[0] not in ("*", head):
        return False
    return _matches(tail, route[1:])


def matching_routes(
    request: HtmxRequest, routes: list[RoutePayload]
) -> list[RoutePayload]:
    request_segments = _segments(request.path, template=True)
    if request_segments is None:
        return []
    return [
        route
        for route in routes
        if route.method == request.method
        and _matches(request_segments, _segments(route.path, template=False) or [])
    ]


def _problem(request: HtmxRequest, route: RoutePayload) -> str | None:
    if route.kind == PayloadKind.INVALID_JSON:
        return f"{request.method} {route.path} must declare a Pydantic request body"
    if route.kind == PayloadKind.JSON and request.ignores_json_enc:
        return f"{request.method} {route.path} expects JSON; remove ignore:json-enc"
    if route.kind == PayloadKind.FORM and not request.ignores_json_enc:
        return f'{request.method} {route.path} uses Form; add hx-ext="ignore:json-enc"'
    if route.kind == PayloadKind.UPLOAD:
        missing = []
        if not request.ignores_json_enc:
            missing.append('hx-ext="ignore:json-enc"')
        if not request.multipart:
            missing.append('hx-encoding="multipart/form-data"')
        if missing:
            return f"{request.method} {route.path} uploads a file; add {' and '.join(missing)}"
    return None


def check_requests(
    requests: list[HtmxRequest], routes: list[RoutePayload]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for request in requests:
        seen: set[str] = set()
        for route in matching_routes(request, routes):
            problem = _problem(request, route)
            if problem is not None and problem not in seen:
                diagnostics.append(
                    Diagnostic(
                        path=request.component, line=request.line, message=problem
                    )
                )
                seen.add(problem)
    return diagnostics


def run_check(components_dir: Path) -> list[Diagnostic]:
    """Check every correlatable component request against the application routes."""
    from backend.server import app  # noqa: PLC0415

    return check_requests(template_requests(components_dir), route_payloads(app.routes))


app = typer.Typer(
    add_completion=False,
    help="Check that htmx request encodings agree with FastAPI payloads.",
)


@app.callback(invoke_without_command=True)
def main(
    filenames: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Staged files. Accepted but not used for scoping."),
    ] = None,
    components_dir: Annotated[
        Path,
        typer.Option("--components-dir", help="Root of the JinjaX components."),
    ] = DEFAULT_COMPONENTS_DIR,
) -> None:
    if not components_dir.is_dir():
        err_console.print(f"{components_dir}: components directory not found")
        raise typer.Exit(EXIT_USAGE)
    try:
        diagnostics = run_check(components_dir)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"could not inspect application routes: {exc}")
        raise typer.Exit(EXIT_USAGE) from exc
    for diagnostic in diagnostics:
        err_console.print(
            f"{diagnostic.path}:{diagnostic.line}: {CODE} {diagnostic.message}"
        )
    raise typer.Exit(EXIT_ERROR if diagnostics else EXIT_OK)


def cli() -> None:
    try:
        app()
    except KeyboardInterrupt:
        raise
    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(EXIT_OK)
    except SystemExit as exc:
        sys.exit(exc.code)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Unexpected error: {exc}")
        sys.exit(EXIT_ERROR)
