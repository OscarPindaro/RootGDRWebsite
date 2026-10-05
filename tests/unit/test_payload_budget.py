"""Baseline payload budgets (F20).

The shell is deliberately small: base CSS, four small scripts and a self-hosted
font subset. The CodeMirror editor is 557 KB and must stay off reading pages, so
it is loaded on demand by ``layout/BlankPage.jinja`` and is budgeted separately.

These are committed-file measurements, not a browser trace, so they run offline
and are deterministic. Each threshold is the measured value plus roughly a third
of headroom: a change that meaningfully grows the baseline fails here instead of
arriving unnoticed. Update the number *and* the note when a ticket grows one on
purpose.
"""

import gzip
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from backend.icons import ICONS
from backend.jinja import get_catalog
from backend.navigation import Crumb

REPO = Path(__file__).parents[2]
STATIC = REPO / "src" / "frontend" / "static"

BASE_CSS = (STATIC / "css" / "main.css",)
SHELL_SCRIPTS = tuple(
    STATIC / "js" / name
    for name in ("htmx.min.js", "json-enc.min.js", "feedback.js", "format-times.js")
)
FONTS = tuple(sorted((STATIC / "fonts").glob("*.woff2")))
EDITOR = (STATIC / "js" / "editor.js",)

# How common.Icon renders one icon; the icon budget measures the whole registry.
_ICON_MARKUP = (
    '<svg class="icon icon--md" data-icon="{name}" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">{body}</svg>'
)


def _gzip(raw: bytes) -> int:
    return len(gzip.compress(raw, 9))


def _measure(files: tuple[Path, ...]) -> tuple[int, int]:
    raw = b"".join(path.read_bytes() for path in files)
    return len(raw), _gzip(raw)


def _icon_payload() -> tuple[int, int]:
    raw = "".join(
        _ICON_MARKUP.format(name=name, body=body) for name, body in ICONS.items()
    ).encode()
    return len(raw), _gzip(raw)


def check_budget(
    label: str,
    measurement: tuple[int, int],
    raw_limit: int,
    gzip_limit: int,
) -> list[str]:
    """The one budget comparison: group, measured size and limit, or empty."""
    raw, compressed = measurement
    problems: list[str] = []
    if raw > raw_limit:
        problems.append(f"{label}: {raw} raw bytes > {raw_limit}")
    if compressed > gzip_limit:
        problems.append(f"{label}: {compressed} gzip bytes > {gzip_limit}")
    return problems


# label -> (measure, raw limit, gzip limit)
# The font limits are equal on purpose: WOFF2 is already compressed, so gzip
# cannot shrink it. The fonts are the one deliberate exception to a small
# baseline — they were downloaded from a font host before F20 too, so
# self-hosting keeps the same bytes while removing the network dependency.
BUDGETS = {
    "base CSS (main.css)": (_measure(BASE_CSS), 60_000, 16_000),
    "shell JavaScript (htmx, json-enc, feedback, format-times)": (
        _measure(SHELL_SCRIPTS),
        75_000,
        25_000,
    ),
    "icon assets (the registry's inline markup, one of each)": (
        _icon_payload(),
        16_000,
        4_000,
    ),
    "fonts (self-hosted latin subsets)": (_measure(FONTS), 420_000, 420_000),
    "lazy editor (editor.js, off read-only pages)": (
        _measure(EDITOR),
        620_000,
        210_000,
    ),
}


@pytest.mark.parametrize("label", sorted(BUDGETS))
def test_the_baseline_stays_within_its_budget(label: str) -> None:
    measurement, raw_limit, gzip_limit = BUDGETS[label]

    assert not check_budget(label, measurement, raw_limit, gzip_limit)


def test_an_oversized_fixture_reports_group_measurement_and_limit() -> None:
    assert check_budget("fixture group", (1234, 999), 1000, 500) == [
        "fixture group: 1234 raw bytes > 1000",
        "fixture group: 999 gzip bytes > 500",
    ]


def test_the_pre_commit_hook_watches_the_budgeted_inputs() -> None:
    config = yaml.safe_load((REPO / ".pre-commit-config.yaml").read_text("utf-8"))
    hooks = [
        hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook["id"] == "payload-budget"
    ]
    assert len(hooks) == 1
    hook = hooks[0]
    assert hook["pass_filenames"] is False
    assert "test_payload_budget.py" in hook["entry"]
    pattern = re.compile(hook["files"])
    for path in (
        "src/frontend/static/css/main.css",
        "src/frontend/static/js/editor.js",
        "src/frontend/static/fonts/ibm-plex-sans.woff2",
        "src/frontend/js/editor/index.js",
        "src/backend/icons.py",
        "tools/build_icons.mjs",
        "tests/unit/test_payload_budget.py",
    ):
        assert pattern.search(path), path
    assert not pattern.search("docs/features-implemented/harness-tooling.md")
    assert not pattern.search("src/backend/server.py")


def test_the_editor_is_the_largest_asset_by_far() -> None:
    """Why it is lazy: it outweighs the whole shell several times over."""
    editor = BUDGETS["lazy editor (editor.js, off read-only pages)"][0][0]
    shell = BUDGETS["shell JavaScript (htmx, json-enc, feedback, format-times)"][0][0]

    assert editor > 5 * shell


def test_a_read_only_page_does_not_load_the_editor_eagerly() -> None:
    """A reading page names no editor <script> tag; BlankPage loads it on demand."""
    world = SimpleNamespace(
        id="01a0c000-0000-7000-8000-000000000001",
        name="Il Boschetto di Smeraldo",
        description="Un bosco di frontiera.",
        version=1,
        image_url=None,
        created_by=SimpleNamespace(id="01a0c000-0000-7000-8000-000000000002"),
    )
    html = str(
        get_catalog(
            str(REPO / "src" / "frontend" / "components"), app_name="Root GDR"
        ).render(
            "pages.worlds.WorldSettings",
            world=world,
            members=[],
            invites=[],
            world_context=None,
            nav=None,
            pages=None,
            crumbs=[Crumb(label="Mondi", href="/worlds")],
            description_html="<p>Un bosco di frontiera.</p>",
            current_user=SimpleNamespace(
                name="Ada",
                email="ada@example.com",
                role="admin",
                avatar_url=None,
                symbol_style="icons",
            ),
        )
    )

    assert '<script src="/static/js/editor.js">' not in html
    # The bundle is only requested when an editable field is present.
    assert 'document.querySelector("[data-markdown-field]")' in html
