import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from harness.backlog.client import (
    BoardClient,
    BoardError,
    BoardLabelSpec,
    BoardTokenSource,
    default_token_source,
    record_table,
)

from harness.backlog.labels import classify_task, load_catalogue

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


def test_default_token_uses_unified_profile_and_respects_explicit_override(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ROOTGDR_BOARD_TOKEN_FILE", raising=False)
    unified = tmp_path / ".config/devin/rootgdr/board-unified-token"
    unified.parent.mkdir(parents=True)
    unified.write_text(TOKEN)
    unified.chmod(0o600)
    assert default_token_source().token_file == unified
    assert default_token_source().token().get_secret_value() == TOKEN
    override = tmp_path / "explicit-token"
    monkeypatch.setenv("ROOTGDR_BOARD_TOKEN_FILE", str(override))
    assert default_token_source().token_file == override


def test_client_refuses_a_non_loopback_base_url():
    for url in (
        "http://board.example",
        "https://127.0.0.1:3458",
        "http://192.168.1.9:3458",
        "http://127.0.0.1:3458@board.example",
        "http://localhost:3458@board.example",
        "http://127.0.0.1:3458/api",
        "http://127.0.0.1:3458?token=private",
        "http://127.0.0.1:bad",
        "http://localhost:3458/#private",
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
        (302, "failed (302)"),
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


def test_view_reads_done_and_default_buckets():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "id": 5,
                "title": "Kanban",
                "done_bucket_id": 9,
                "default_bucket_id": 3,
            },
        )

    with client(handler) as board:
        view = board.view(2, 5)
    assert (view.done_bucket_id, view.default_bucket_id) == (9, 3)
    assert paths == ["/api/v2/projects/2/views/5"]


def test_task_bucket_maps_placement_and_reports_unplaced_as_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=envelope(
                [
                    {"id": 4, "title": "Backlog", "tasks": [{"id": 7}]},
                    {"id": 5, "title": "Done", "tasks": None},
                ]
            ),
        )

    with client(handler) as board:
        assert board.task_bucket(2, 3, 7) == 4
        assert board.task_bucket(2, 3, 99) == 0


def test_place_task_puts_only_the_reviewed_body():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": 7, "bucket_id": 4})

    with client(handler) as board:
        board.place_task(2, 5, 4, 7)
    assert captured["method"] == "PUT"
    assert captured["path"] == "/api/v2/projects/2/views/5/buckets/4/tasks"
    assert captured["body"] == {
        "task_id": 7,
        "bucket_id": 4,
        "project_view_id": 5,
    }


def test_set_task_done_sends_only_the_flag_as_a_merge_patch():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["content_type"] = request.headers["content-type"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"id": 7, "title": "T", "done": True, "description": "kept"}
        )

    with client(handler) as board:
        record = board.set_task_done(7, True)
    assert captured["method"] == "PATCH"
    assert captured["content_type"] == "application/merge-patch+json"
    assert captured["body"] == {"done": True}
    assert record.done is True


def test_unchanged_patches_reread_after_vikunjas_empty_304():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "PATCH":
            return httpx.Response(304)
        if "views" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "id": 5,
                    "title": "Kanban",
                    "default_bucket_id": 3,
                    "done_bucket_id": 9,
                },
            )
        return httpx.Response(200, json={"id": 7, "title": "T", "done": True})

    with client(handler) as board:
        record = board.set_task_done(7, True)
        view = board.set_view_buckets(2, 5, default=3, done=9)
    assert record.done is True
    assert (view.default_bucket_id, view.done_bucket_id) == (3, 9)
    assert calls == [
        ("PATCH", "/api/v2/tasks/7"),
        ("GET", "/api/v2/tasks/7"),
        ("PATCH", "/api/v2/projects/2/views/5"),
        ("GET", "/api/v2/projects/2/views/5"),
    ]


def test_add_comment_once_does_not_duplicate_an_existing_marker():
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posts.append(request.url.path)
            return httpx.Response(201, json={"id": 2, "comment": "new"})
        return httpx.Response(
            200, json=envelope([{"id": 1, "comment": "outcome REQ-0012/T04 done"}])
        )

    with client(handler) as board:
        record, created = board.add_comment_once(7, "new", "REQ-0012/T04")
    assert (record.id, created) == (1, False)
    assert posts == []


def test_add_comment_once_posts_when_the_marker_is_absent():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            captured["body"] = json.loads(request.content)
            return httpx.Response(201, json={"id": 2, "comment": "new"})
        return httpx.Response(200, json=envelope([]))

    with client(handler) as board:
        record, created = board.add_comment_once(7, "new", "REQ-0012/T04")
    assert (record.id, created) == (2, True)
    assert captured["body"] == {"comment": "new\n\nREQ-0012/T04"}


def test_add_comment_once_rereads_after_an_ambiguous_timeout():
    reads = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal reads
        if request.method == "POST":
            raise httpx.ReadTimeout("slow", request=request)
        reads += 1
        items = [] if reads == 1 else [{"id": 3, "comment": "outcome REQ-0012/T04"}]
        return httpx.Response(200, json=envelope(items))

    with client(handler) as board:
        record, created = board.add_comment_once(7, "new", "REQ-0012/T04")
    assert (record.id, created) == (3, False)
    assert reads == 2


def test_add_comment_once_reraises_when_the_reread_finds_nothing():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=envelope([]))

    with client(handler) as board:
        with pytest.raises(BoardError, match="timed out") as error:
            board.add_comment_once(7, "new", "REQ-0012/T04")
    assert error.value.ambiguous is True


def test_add_comment_once_does_not_reread_after_a_definitive_rejection():
    reads = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal reads
        if request.method == "POST":
            return httpx.Response(404, json={"detail": "missing"})
        reads += 1
        return httpx.Response(200, json=envelope([]))

    with client(handler) as board:
        with pytest.raises(BoardError, match="not found") as error:
            board.add_comment_once(7, "new", "REQ-0012/T04")
    assert error.value.ambiguous is False
    assert reads == 1


def test_upload_attachment_verifies_stored_bytes_and_reuses_identical_files(tmp_path):
    image = tmp_path / "portrait.png"
    data = b"\x89PNG\r\n\x1a\nimage-content"
    image.write_bytes(data)
    attachment = {
        "id": 5,
        "task_id": 7,
        "file": {"id": 8, "name": image.name, "mime": "image/png", "size": len(data)},
    }
    uploaded = False
    posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal uploaded, posts
        if request.method == "POST":
            posts += 1
            assert request.url.path == "/api/v2/tasks/7/attachments"
            assert "multipart/form-data; boundary=" in request.headers["content-type"]
            assert b'name="files"; filename="portrait.png"' in request.content
            assert b"Content-Type: image/png" in request.content
            assert data in request.content
            assert str(tmp_path).encode() not in request.content
            uploaded = True
            return httpx.Response(201, json={"success": [attachment], "errors": None})
        if request.url.path.endswith("/5"):
            return httpx.Response(200, content=data)
        return httpx.Response(200, json=envelope([attachment] if uploaded else []))

    with client(handler) as board:
        first = board.upload_attachment_once(7, image)
        second = board.upload_attachment_once(7, image)
    assert first.attachment.id == second.attachment.id == 5
    assert first.created is True
    assert second.created is False
    assert len(first.sha256) == 64
    assert posts == 1


def test_upload_attachment_rejects_non_files_without_network_requests(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid input must not contact the board")

    with client(handler) as board:
        for path in (tmp_path, tmp_path / "missing.png"):
            with pytest.raises(BoardError, match="regular file"):
                board.upload_attachment_once(7, path)


def test_upload_attachment_does_not_treat_a_201_file_error_as_success(tmp_path):
    image = tmp_path / "portrait.png"
    image.write_bytes(b"image")
    posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posts
        if request.method == "POST":
            posts += 1
            return httpx.Response(
                201,
                json={
                    "success": None,
                    "errors": [{"code": 10001, "message": TOKEN}],
                },
            )
        return httpx.Response(200, json=envelope([]))

    with client(handler) as board:
        with pytest.raises(BoardError, match="rejected the attachment") as error:
            board.upload_attachment_once(7, image)
    assert TOKEN not in str(error.value)
    assert error.value.ambiguous is False
    assert posts == 1


def test_label_reads_follow_v2_pagination():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json=envelope([{"id": 4, "title": "type:feature", "hex_color": "2563eb"}]),
        )

    with client(handler) as board:
        labels = board.labels()
        attached = board.task_labels(7)
    assert labels[0].hex_color == attached[0].hex_color == "2563EB"
    assert paths == ["/api/v2/labels", "/api/v2/tasks/7/labels"]


def test_add_label_once_verifies_persistence_and_recovers_an_ambiguous_write():
    attached = False
    posts = 0

    def handler(request):
        nonlocal attached, posts
        if request.method == "POST":
            posts += 1
            assert request.url.path == "/api/v2/tasks/7/labels"
            assert json.loads(request.content) == {"label_id": 4}
            attached = True
            raise httpx.ReadTimeout("ambiguous", request=request)
        records = (
            [{"id": 4, "title": "type:feature", "hex_color": "2563EB"}]
            if attached
            else []
        )
        return httpx.Response(200, json=envelope(records))

    with client(handler) as board:
        assert board.add_label_once(7, 4) is True
        assert board.add_label_once(7, 4) is False
    assert posts == 1


def test_task_colour_patch_changes_only_colour_and_reads_it_back():
    calls = []
    colour = ""

    def handler(request):
        nonlocal colour
        calls.append(request.method)
        if request.method == "PATCH":
            assert request.headers["content-type"] == "application/merge-patch+json"
            assert json.loads(request.content) == {"hex_color": "2563EB"}
            colour = "2563eb"
            return httpx.Response(200, json={"id": 7, "hex_color": colour})
        return httpx.Response(
            200,
            json={"id": 7, "description": "keep", "done": True, "hex_color": colour},
        )

    with client(handler) as board:
        task = board.set_task_colour(7, "#2563EB")
    assert task.hex_color == "2563EB"
    assert task.description == "keep" and task.done is True
    assert calls == ["PATCH", "GET"]


def test_label_creation_reconciles_timeouts_without_duplicate_posts():
    stored = []
    posts = 0
    spec = BoardLabelSpec(
        title="type:feature", hex_color="#2563EB", description="feature"
    )

    def handler(request):
        nonlocal posts
        if request.method == "POST":
            posts += 1
            assert json.loads(request.content) == spec.model_dump()
            stored.append({"id": 4, **spec.model_dump()})
            raise httpx.ReadTimeout("ambiguous", request=request)
        return httpx.Response(200, json=envelope(stored))

    with client(handler) as board:
        assert board.ensure_label(spec).id == board.ensure_label(spec).id == 4
    assert posts == 1


@pytest.mark.parametrize(
    "records",
    [
        [{"id": 4, "title": "type:feature", "hex_color": "DC2626"}],
        [
            {"id": 4, "title": "type:feature", "hex_color": "2563EB"},
            {"id": 5, "title": "type:feature", "hex_color": "2563EB"},
        ],
    ],
)
def test_catalogue_conflicts_do_not_overwrite_labels(records):
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json=envelope(records))

    with client(handler) as board:
        with pytest.raises(BoardError, match="review"):
            board.ensure_label(BoardLabelSpec(title="type:feature", hex_color="2563EB"))


def test_classification_preserves_a_human_type_colour_and_unrelated_labels():
    catalogue = load_catalogue()
    available = [
        {"id": 1, "title": "type:bug", "hex_color": "DC2626"},
        {"id": 2, "title": "type:feature", "hex_color": "2563EB"},
        {"id": 3, "title": "area:frontend", "hex_color": "64748B"},
        {"id": 4, "title": "human-label", "hex_color": "111111"},
    ]
    attached = [available[0], available[3]]
    posts = []

    def handler(request):
        if request.method == "POST":
            label_id = json.loads(request.content)["label_id"]
            posts.append(label_id)
            attached.append(
                next(label for label in available if label["id"] == label_id)
            )
            return httpx.Response(201, json={"label_id": label_id})
        assert request.method == "GET"
        if request.url.path == "/api/v2/tasks/7":
            return httpx.Response(
                200,
                json={
                    "id": 7,
                    "project_id": 2,
                    "hex_color": "AB1234",
                    "description": "keep",
                    "done": True,
                },
            )
        return httpx.Response(
            200, json=envelope(attached if "/tasks/" in request.url.path else available)
        )

    with client(handler) as board:
        first = classify_task(board, catalogue, 7, 2, "feature", ["frontend"])
        again = classify_task(board, catalogue, 7, 2, "feature", ["frontend"])
    assert first.type_preserved and first.colour_preserved
    assert first.task.description == "keep" and first.task.done
    assert {label.title for label in first.task.labels} == {
        "type:bug",
        "area:frontend",
        "human-label",
    }
    assert again.added_labels == []
    assert posts == [3]


def test_classification_rejects_the_wrong_project_before_any_write():
    def handler(request):
        assert request.method == "GET" and request.url.path == "/api/v2/tasks/7"
        return httpx.Response(200, json={"id": 7, "project_id": 9})

    with client(handler) as board:
        with pytest.raises(BoardError, match="different project"):
            classify_task(board, load_catalogue(), 7, 2, "feature", ["frontend"])


def test_unknown_classification_is_rejected_without_network_requests():
    def handler(request):
        raise AssertionError("unknown vocabulary must not contact the board")

    with client(handler) as board:
        with pytest.raises(BoardError, match="approved"):
            classify_task(board, load_catalogue(), 7, 2, "unknown", [])


def test_default_catalogue_has_the_approved_types_and_neutral_areas():
    catalogue = load_catalogue()
    assert {
        label.title: label.hex_color
        for label in catalogue.labels
        if label.title.startswith("type:")
    } == {
        "type:bug": "DC2626",
        "type:feature": "2563EB",
        "type:maintenance": "B45309",
        "type:research": "7C3AED",
    }
    assert {
        label.title for label in catalogue.labels if label.title.startswith("area:")
    } == {
        "area:frontend",
        "area:backend",
        "area:database",
        "area:deployment",
        "area:tooling",
        "area:docs",
    }
    assert {
        label.hex_color for label in catalogue.labels if label.title.startswith("area:")
    } == {"64748B"}


@pytest.mark.parametrize("failure", ["timeout", "server", "invalid"])
@pytest.mark.parametrize("persisted", [False, True])
def test_upload_attachment_reconciles_ambiguous_writes_without_retrying(
    tmp_path, failure, persisted
):
    image = tmp_path / "portrait.jpg"
    data = b"image-content"
    image.write_bytes(data)
    attachment = {
        "id": 5,
        "task_id": 7,
        "file": {"id": 8, "name": image.name, "mime": "image/jpeg", "size": len(data)},
    }
    posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posts
        if request.method == "POST":
            posts += 1
            if failure == "timeout":
                raise httpx.ReadTimeout(TOKEN, request=request)
            if failure == "server":
                return httpx.Response(500, text=TOKEN)
            return httpx.Response(201, text=TOKEN)
        if request.url.path.endswith("/5"):
            return httpx.Response(200, content=data)
        items = [attachment] if posts and persisted else []
        return httpx.Response(200, json=envelope(items))

    with client(handler) as board:
        if persisted:
            receipt = board.upload_attachment_once(7, image)
            assert receipt.attachment.id == 5
            assert receipt.created is False
        else:
            with pytest.raises(BoardError) as error:
                board.upload_attachment_once(7, image)
            assert error.value.ambiguous is True
            assert TOKEN not in str(error.value)
    assert posts == 1


def test_upload_attachment_checks_content_not_just_name_and_size(tmp_path):
    image = tmp_path / "portrait.png"
    image.write_bytes(b"new")
    old = {
        "id": 5,
        "task_id": 7,
        "file": {"id": 8, "name": image.name, "mime": "image/png", "size": 3},
    }
    new = {**old, "id": 6}
    uploaded = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal uploaded
        if request.method == "POST":
            uploaded = True
            return httpx.Response(201, json={"success": [new], "errors": []})
        if request.url.path.endswith("/5"):
            return httpx.Response(200, content=b"old")
        if request.url.path.endswith("/6"):
            return httpx.Response(200, content=b"new")
        return httpx.Response(200, json=envelope([old, new] if uploaded else [old]))

    with client(handler) as board:
        receipt = board.upload_attachment_once(7, image)
    assert receipt.attachment.id == 6
    assert receipt.created is True


def test_upload_attachment_rejects_corrupted_readback(tmp_path):
    image = tmp_path / "portrait.png"
    image.write_bytes(b"new")
    attachment = {
        "id": 5,
        "task_id": 7,
        "file": {"id": 8, "name": image.name, "mime": "image/png", "size": 3},
    }
    posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posts
        if request.method == "POST":
            posts += 1
            return httpx.Response(201, json={"success": [attachment], "errors": []})
        if request.url.path.endswith("/5"):
            return httpx.Response(200, content=b"bad")
        return httpx.Response(200, json=envelope([attachment] if posts else []))

    with client(handler) as board:
        with pytest.raises(BoardError, match="could not be verified") as error:
            board.upload_attachment_once(7, image)
    assert error.value.ambiguous is True
    assert posts == 1


def test_attachments_accepts_empty_null_pages_and_rejects_another_task():
    with client(
        lambda request: httpx.Response(200, json={**envelope([]), "items": None})
    ) as board:
        assert board.attachments(7) == []
    foreign = {
        "id": 5,
        "task_id": 99,
        "file": {"id": 8, "name": "portrait.png", "mime": "image/png", "size": 3},
    }
    with client(lambda request: httpx.Response(200, json=envelope([foreign]))) as board:
        with pytest.raises(BoardError, match="different task"):
            board.attachments(7)
