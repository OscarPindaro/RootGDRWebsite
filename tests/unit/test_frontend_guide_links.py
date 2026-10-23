"""The frontend guide's links and the manuals it defers to.

REQ-0019/T21 makes ``docs/frontend_guide.md`` the practical contract. The guide
is only usable if its local references resolve and if it actually points at the
thematic manuals that own the detail. ``harness backlog check-requests`` reads
``docs/features-request/`` only, so this file guards the guide itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "frontend_guide.md"

# The manuals the guide names as authorities instead of copying their content.
DEFERRED = (
    "jinjax.md",
    "design_guide.md",
    "features-request/frontend.md",
    "features-implemented/css-ownership.md",
    "features-implemented/component-vocabulary.md",
    "features-implemented/document-layout.md",
    "features-implemented/shell.md",
    "features-implemented/dialog-pattern.md",
    "features-implemented/in-place-editing.md",
    "features-implemented/component-tests.md",
    "features-implemented/document-navigator.md",
    "development_processes/prototyping.md",
    "../prototypes/README.md",
)

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
EXTERNAL = ("https://", "http://", "mailto:")


def _without_code_blocks(text: str) -> str:
    """Drop fenced code so a bracket in an example is not read as a link."""
    kept: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def _targets(text: str) -> list[str]:
    return [
        target
        for target in LINK.findall(_without_code_blocks(text))
        if not target.startswith(EXTERNAL) and not target.startswith("#")
    ]


def test_every_local_link_in_the_guide_resolves() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    targets = _targets(text)

    assert targets, "the guide links no local file"
    missing = [
        target
        for target in targets
        if not (GUIDE.parent / target.split("#", 1)[0]).is_file()
    ]
    assert not missing, missing


def test_the_guide_names_the_manuals_it_defers_to() -> None:
    targets = _targets(GUIDE.read_text(encoding="utf-8"))

    assert sorted(set(DEFERRED) - set(targets)) == []
