"""Alert announces by weight, and a caller can override it.

F19 gives ``common.Alert`` a variant-derived default role: a blocking or
destructive ``danger`` alert is announced assertively (``role="alert"``), while
success, info and warning are ordinary feedback announced politely
(``role="status"``). A caller with a contextual reason can pass ``role`` — the
Settings status passes ``role="none"`` because a pre-existing polite region is
the announcer.
"""

import re
from pathlib import Path

import pytest

from backend.jinja import get_catalog

COMPONENTS = Path(__file__).parents[3] / "src" / "frontend" / "components"


def _role(variant: str, **extra) -> str:
    html = str(
        get_catalog(str(COMPONENTS), app_name="Root GDR").render(
            "common.Alert", variant=variant, content="x", **extra
        )
    )
    match = re.search(r'role="([^"]+)"', html)
    assert match is not None, html
    return match.group(1)


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("danger", "alert"),
        ("warning", "status"),
        ("info", "status"),
        ("success", "status"),
    ],
)
def test_the_default_role_follows_the_variant(variant: str, expected: str) -> None:
    assert _role(variant) == expected


def test_a_caller_can_override_the_role() -> None:
    assert _role("success", role="none") == "none"
    assert _role("danger", role="alert") == "alert"
