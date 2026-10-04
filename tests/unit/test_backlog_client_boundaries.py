import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from harness.backlog.client import (
    BoardClient,
    BoardError,
    BoardTokenSource,
    record_table,
)

TOKEN = "private-board-token-sentinel-value"


def client(handler) -> BoardClient:
    board = BoardClient("http://127.0.0.1:3458", SecretStr(TOKEN))
    board._client = httpx.Client(
        base_url="http://127.0.0.1:3458",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer " + TOKEN},
    )
    return board


def envelope(items, page=1, total_pages=1):
    return {
        "items": items,
        "total": len(items),
        "page": page,
        "per_page": 50,
        "total_pages": total_pages,
    }


def test_token_source_requires_a_private_canonical_file(tmp_path):
    exposed = tmp_path / "token"
    exposed.write_text(TOKEN)
    exposed.chmod(0o644)
    with pytest.raises(BoardError):
        BoardTokenSource(token_file=exposed).token()
    exposed.chmod(0o600)
    assert BoardTokenSource(token_file=exposed).token().get_secret_value() == TOKEN
    with pytest.raises(BoardError):
        BoardTokenSource(token_file=tmp_path / "missing").token()


def test_client_refuses_a_non_loopback_base_url():
    for url in (
        "http://board.example",
        "https://127.0.0.1:3458",
        "http://192.168.1.9:3458",
    ):
        with pytest.raises(BoardError):
            BoardClient(url, SecretStr(TOKEN))


def test_pagination_follows_every_page():
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        seen.append(page)
        assert request.url.params["per_page"] == "50"
        return httpx.Response(
            200, json=envelope([{"id": page, "title": f"p{page}"}], page, 3)
        )

    with client(handler) as board:
        records = board.tasks(2)
    assert [record.id for record in records] == [1, 2, 3]
    assert seen == [1, 2, 3]


def test_pagination_is_bounded():
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(
            200, json=envelope([{"id": page, "title": "x"}], page, 999)
        )

    with client(handler) as board:
        with pytest.raises(BoardError, match="reviewed bound"):
            board.tasks(2)


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "missing, expired or insufficiently scoped"),
        (403, "missing, expired or insufficiently scoped"),
        (404, "not found"),
        (422, "rejected the request payload"),
        (500, "failed (500)"),
    ],
)
def test_statuses_map_to_bounded_errors_without_echoing_bodies(status, message):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "secret-bearing upstream body"})

    with client(handler) as board:
        with pytest.raises(BoardError) as error:
            board.task(7)
    text = str(error.value)
    assert message in text
    assert "secret-bearing upstream body" not in text
    assert TOKEN not in text


def test_transport_and_timeout_failures_are_bounded():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with client(timeout) as board:
        with pytest.raises(BoardError, match="timed out"):
            board.task(7)

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with client(broken) as board:
        with pytest.raises(BoardError, match="before a response"):
            board.task(7)


def test_create_sends_only_the_reviewed_fields_and_returns_the_record():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201, json={"id": 42, "title": "REQ-0012/T03", "description": "b"}
        )

    with client(handler) as board:
        record = board.create_task(2, title="REQ-0012/T03", description="b", bucket=9)
    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v2/projects/2/tasks"
    assert captured["body"] == {
        "title": "REQ-0012/T03",
        "description": "b",
        "bucket_id": 9,
    }
    assert record.id == 42


def test_buckets_and_comments_use_the_reviewed_paths():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if "comments" in request.url.path:
            return httpx.Response(200, json=envelope([{"id": 1, "comment": "ok"}]))
        return httpx.Response(200, json=envelope([{"id": 5, "title": "Backlog"}]))

    with client(handler) as board:
        buckets = board.buckets(2, 3)
        comments = board.comments(7)
    assert [bucket.id for bucket in buckets] == [5]
    assert [comment.comment for comment in comments] == ["ok"]
    assert paths == [
        "/api/v2/projects/2/views/3/buckets",
        "/api/v2/tasks/7/comments",
    ]


def test_human_rows_never_include_the_description_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=envelope([{"id": 1, "title": "Ticket", "description": TOKEN}])
        )

    with client(handler) as board:
        rows = record_table(board.projects())
    assert rows == [("1", "Ticket")]
    assert TOKEN not in json.dumps(rows)
