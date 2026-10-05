"""Typed loader of the cycle plan's tickets and their specification links.

The plan's ticket sections are the approved list for the cycle; the request
documents are the specifications they reference. Nothing here invents a
ticket that the plan does not define.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from .requests import REPO_ROOT, RequestError, load_requests

PLAN = Path("docs/development_processes/afk-cycle-plan-2026-10-03.md")
_PLAN_TICKET = re.compile(r"^### (REQ-\d{4}/T\d{2}) — (.+)$")
_PLAN_HARNESS_TICKET = re.compile(r"^### T(\d{2})(?: / H\d)? — (.+)$")
_PLAN_SECTION = re.compile(r"^## (\d+)\..*$")
_SECTION_REQUEST = re.compile(r"REQ-\d{4}")

# Named in REQ-0012/T05 and REQ-0001: deferred by the approved cycle, kept as
# a card without claiming progress.
DEFERRED_TICKETS = {
    "REQ-0001/T01": "App identity and owner/bot branch policy",
}
DEFERRED_NOTE = (
    "Deferred by the approved 2026-10-03 cycle: no GitHub App, mandatory PR "
    "workflow or branch-policy changes. Kept as a deferred card without "
    "claiming progress."
)


class PlanTicket(BaseModel):
    key: str
    title: str
    spec: Path
    section: str
    deferred: bool = False


class PlanError(RequestError):
    """Bounded plan-loading failure."""


def load_plan_tickets(root: Path = REPO_ROOT, plan: Path = PLAN) -> list[PlanTicket]:
    """Read the plan's ticket headings and link each to its request document."""
    documents = {item.metadata.id: item.path for item in load_requests(root)}
    text = (root / plan).read_text(encoding="utf-8")
    tickets: list[PlanTicket] = []
    section = ""
    section_request = ""
    for line in text.splitlines():
        section_match = _PLAN_SECTION.match(line)
        if section_match:
            section = section_match.group(1)
            found = _SECTION_REQUEST.search(line)
            section_request = found.group(0) if found else ""
            continue
        key = title = ""
        plan_match = _PLAN_TICKET.match(line)
        if plan_match:
            key, title = plan_match.group(1), plan_match.group(2)
        else:
            harness_match = _PLAN_HARNESS_TICKET.match(line)
            if harness_match and section_request:
                key = f"{section_request}/T{harness_match.group(1)}"
                title = harness_match.group(2)
        if key:
            tickets.append(_ticket(key, title, section, documents))
    for key, title in DEFERRED_TICKETS.items():
        tickets.append(_ticket(key, title, "", documents, deferred=True))
    return tickets


def _ticket(
    key: str,
    title: str,
    section: str,
    documents: dict[str, Path],
    *,
    deferred: bool = False,
) -> PlanTicket:
    request = key.split("/", 1)[0]
    spec = documents.get(request)
    if spec is None:
        raise PlanError(f"Plan ticket {key} has no request document")
    return PlanTicket(
        key=key, title=title, spec=spec, section=section, deferred=deferred
    )


def ticket_description(ticket: PlanTicket, plan: Path = PLAN) -> str:
    """Stable reference to the specification and the plan section."""
    lines = [f"Spec: {ticket.spec}", f"Plan: {plan} section {ticket.section}"]
    if ticket.deferred:
        lines.extend(["", DEFERRED_NOTE])
    return "\n".join(lines)
