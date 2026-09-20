"""Server-side Markdown rendering with `@[Name]` references.

Resolution stays on the server — it is the only place with the database and the
reader's permissions — and emits **semantics only**: destination, kind, tint and
the name. Shape, icon and colour live in the stylesheet, so the editor and the
server cannot render the same reference differently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markupsafe import Markup

from .constants import ContentKind

_MENTION = re.compile(r"@\[([^\]]+)\]")


@dataclass(frozen=True)
class MentionTarget:
    id: object
    kind: ContentKind
    tint: str
    href: str
    name: str


def mention_labels(text: str) -> list[str]:
    """Every distinct ``@[label]`` label in a body, in first-seen order."""
    seen: list[str] = []
    for label in _MENTION.findall(text or ""):
        label = label.strip()
        if label and label not in seen:
            seen.append(label)
    return seen


def _render_missing(label: str) -> str:
    return (
        '<span class="mention mention--missing" '
        'title="Nessun contenuto con questo nome">@'
        f"{label}</span>"
    )


def _render_mention(label: str, target: MentionTarget | None) -> str:
    if target is None:
        return _render_missing(label)
    kind = target.kind.value
    return (
        f'<a class="mention" href="{target.href}" data-kind="{kind}" '
        f'data-color="{target.tint}" title="{kind}">{target.name}</a>'
    )


def _renderer() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False})

    def mention(state, silent: bool) -> bool:
        src = state.src
        pos = state.pos
        if src[pos] != "@" or src[pos + 1 : pos + 2] != "[":
            return False
        end = src.find("]", pos + 2)
        if end < 0:
            return False
        label = src[pos + 2 : end].strip()
        if not silent:
            token = state.push("mention", "", 0)
            token.meta = {"label": label}
        state.pos = end + 1
        return True

    def render_mention_rule(self, tokens, idx, options, env) -> str:
        label = tokens[idx].meta["label"]
        mapping: dict[str, MentionTarget | None] = env.get("mentions", {})
        return _render_mention(label, mapping.get(label))

    md.inline.ruler.before("link", "mention", mention)
    md.add_render_rule("mention", render_mention_rule)
    return md


_MD = _renderer()


def render_markdown(
    text: str | None, mentions: dict[str, MentionTarget | None] | None = None
) -> Markup:
    """Render Markdown to HTML, resolving ``@[label]`` from ``mentions``."""
    html = _MD.render(text or "", {"mentions": mentions or {}})
    return Markup(html)
