"""Tests for htmx payload and FastAPI route compatibility."""

from __future__ import annotations

from pathlib import Path

from fastapi import Body, FastAPI, File, Form, UploadFile
from pydantic import BaseModel

from pre_commits.htmx_payloads.hook import (
    HtmxRequest,
    PayloadKind,
    RoutePayload,
    check_requests,
    matching_routes,
    route_payloads,
    run_check,
    template_requests,
)


class JsonBody(BaseModel):
    name: str


def _routes() -> list[RoutePayload]:
    app = FastAPI()

    @app.post("/items/{item_id}")
    async def json_route(item_id: int, body: JsonBody) -> None:
        pass

    @app.post("/members")
    async def form_route(email: str = Form(...)) -> None:
        pass

    @app.put("/images/{image_id}")
    async def upload_route(image_id: int, image: UploadFile = File(...)) -> None:
        pass

    @app.patch("/scalar")
    async def scalar_route(value: str = Body(...)) -> None:
        pass

    @app.post("/ping")
    async def empty_route() -> None:
        pass

    return route_payloads(app.routes)


def _request(
    path: str,
    method: str = "POST",
    *,
    ignore: bool = False,
    multipart: bool = False,
) -> HtmxRequest:
    return HtmxRequest(
        component=Path("Form.jinja"),
        line=3,
        method=method,
        path=path,
        ignores_json_enc=ignore,
        multipart=multipart,
    )


def test_route_payloads_classifies_resolved_fastapi_signatures() -> None:
    kinds = {(route.method, route.path): route.kind for route in _routes()}

    assert kinds == {
        ("POST", "/items/{item_id}"): PayloadKind.JSON,
        ("POST", "/members"): PayloadKind.FORM,
        ("PUT", "/images/{image_id}"): PayloadKind.UPLOAD,
        ("PATCH", "/scalar"): PayloadKind.INVALID_JSON,
        ("POST", "/ping"): PayloadKind.NONE,
    }


def test_template_requests_reads_encoding_and_attribute_line(tmp_path: Path) -> None:
    component = tmp_path / "Forms.jinja"
    component.write_text(
        '<form\n  hx-post="/members" hx-ext="ignore:json-enc"></form>\n'
        '<form hx-put="/images/{{ image.id }}"\n'
        '      hx-ext="ignore:json-enc" hx-encoding="multipart/form-data"></form>\n',
        encoding="utf-8",
    )

    requests = template_requests(tmp_path)

    assert [(request.method, request.path, request.line) for request in requests] == [
        ("POST", "/members", 2),
        ("PUT", "/images/{{ image.id }}", 3),
    ]
    assert requests[0].ignores_json_enc
    assert requests[1].ignores_json_enc and requests[1].multipart


def test_dynamic_paths_match_one_segment_and_base_prefixes() -> None:
    routes = _routes()

    assert [
        route.path
        for route in matching_routes(_request("/items/{{ item.id }}"), routes)
    ] == ["/items/{item_id}"]
    prefixed = RoutePayload(
        path="/worlds/{world_id}/places/{place_id}/toggle/locked",
        method="POST",
        kind=PayloadKind.NONE,
    )
    assert matching_routes(_request("{{ base }}/toggle/locked"), [prefixed]) == [
        prefixed
    ]
    assert matching_routes(_request("{{ action }}"), routes) == []


def test_json_form_and_upload_contracts() -> None:
    routes = _routes()
    valid = [
        _request("/items/1"),
        _request("/members", ignore=True),
        _request("/images/1", "PUT", ignore=True, multipart=True),
        _request("/ping"),
    ]
    assert check_requests(valid, routes) == []

    invalid = [
        _request("/items/1", ignore=True),
        _request("/members"),
        _request("/images/1", "PUT"),
        _request("/scalar", "PATCH"),
    ]
    messages = [diagnostic.message for diagnostic in check_requests(invalid, routes)]
    assert messages == [
        "POST /items/{item_id} expects JSON; remove ignore:json-enc",
        'POST /members uses Form; add hx-ext="ignore:json-enc"',
        'PUT /images/{image_id} uploads a file; add hx-ext="ignore:json-enc" '
        'and hx-encoding="multipart/form-data"',
        "PATCH /scalar must declare a Pydantic request body",
    ]


def test_repository_htmx_payloads_match_view_routes() -> None:
    components = Path("src/frontend/components")

    assert run_check(components) == []
