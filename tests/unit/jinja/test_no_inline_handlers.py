"""No inline event-handler JavaScript in the Admin and Settings pages (F18).

The Admin and Settings surfaces used to carry htmx behaviour as inline
attributes (``hx-on::after-request`` on the invite dialog). The atlas pattern
moves behaviour into a component's colocated script and connects it through
htmx events, so these pages must declare no inline handler at all. This is a
source scan: it pins the acceptance criterion without a browser.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).parents[3]
COMPONENTS = REPO / "src" / "frontend" / "components"
SCANNED = ("pages/admin", "pages/settings")

# An inline handler: `hx-on` (any variant), an `on<event>=` attribute, or a
# `javascript:` URL. The lookbehind keeps `data-on-...` and ordinary words from
# matching.
INLINE_HANDLER = re.compile(
    r"hx-on\b|(?<![\w-])on[a-z]+\s*=|\bjavascript:", re.IGNORECASE
)


def _scanned_files() -> list[Path]:
    return sorted(
        path for folder in SCANNED for path in (COMPONENTS / folder).rglob("*.jinja")
    )


def test_there_are_pages_to_scan() -> None:
    assert _scanned_files()


@pytest.mark.parametrize("path", _scanned_files(), ids=lambda p: p.name)
def test_no_inline_event_handler_javascript(path: Path) -> None:
    offenders = [
        f"{path.relative_to(REPO)}:{number}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if INLINE_HANDLER.search(line)
    ]
    assert offenders == [], (
        "inline event-handler JavaScript in an Admin/Settings page: "
        + ", ".join(offenders)
    )
