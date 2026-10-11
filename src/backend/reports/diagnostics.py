"""What a submitted report carries so the investigation does not start over.

The ticket gets the reader's text and the captures as attachments, plus one
bounded document: the context the browser reported, the correlation ids of the
submission, both sides of the reproduction, and the log records the server
wrote between the report being opened and being submitted. The log records are
the point — console logs rotate, and a ticket has to stay readable afterwards.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..log import recent_records
from .models import ReportModel
from .recording import BACKEND, FRONTEND

# A ticket is a report, not a dump: the snapshot is bounded on every side.
MAX_LOGS = 300
MAX_STEPS_PER_SIDE = 200


def _bounded(steps: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return steps[:limit]


def build(
    report: ReportModel,
    *,
    reproduction: dict[str, Any],
    steps: dict[str, list[dict[str, Any]]],
    request_id: str | None,
    trace_id: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    submitted_at = now or datetime.now(UTC)
    since = report.created_at.timestamp() if report.created_at else 0.0
    buffer = recent_records()
    logs = buffer.snapshot(since, submitted_at.timestamp()) if buffer else []
    return {
        "report": {
            "id": str(report.id),
            "state": report.state.value if report.state else "",
            "page_url": report.page_url,
            "user_agent": report.user_agent,
            "viewport": {
                "width": report.viewport_width,
                "height": report.viewport_height,
            },
            "opened_at": report.created_at.isoformat() if report.created_at else None,
        },
        "submitted_at": submitted_at.isoformat(),
        "correlation": {"request_id": request_id, "trace_id": trace_id},
        "reproduction": reproduction,
        "recordings": {
            FRONTEND: _bounded(steps.get(FRONTEND, []), MAX_STEPS_PER_SIDE),
            BACKEND: _bounded(steps.get(BACKEND, []), MAX_STEPS_PER_SIDE),
        },
        "logs": logs[-MAX_LOGS:],
    }


def ticket_title(report: ReportModel) -> str:
    """A short board title: what the reader wrote, or the page they were on."""
    first = (report.description or "").strip().splitlines()
    subject = first[0].strip() if first else ""
    if not subject:
        subject = report.page_url or "pagina sconosciuta"
    return f"Segnalazione — {subject[:120]}"


def ticket_description(
    report: ReportModel, *, reproduction: dict[str, Any], base_url: str | None = None
) -> str:
    reporter = "anonimo"
    if report.reporter is not None:
        reporter = report.reporter.name or report.reporter.email
    window = ""
    if reproduction.get("started_at"):
        window = f"{reproduction['started_at']} → {reproduction.get('stopped_at') or 'in corso'}"
    page = report.page_url or "sconosciuta"
    if base_url and report.page_url:
        page = f"[{report.page_url}]({base_url.rstrip('/')}{report.page_url})"
    return "\n".join(
        [
            "### Cosa non funziona",
            "",
            (report.description or "_Nessuna descrizione_").strip(),
            "",
            "### Contesto",
            "",
            f"- Pagina: {page}",
            f"- Viewport: {report.viewport_width or '?'}×{report.viewport_height or '?'}",
            f"- Chi segnala: {reporter}",
            f"- Browser: {report.user_agent or 'sconosciuto'}",
            f"- Aperta il: {report.created_at.isoformat() if report.created_at else '?'}",
            "",
            "### Riproduzione",
            "",
            f"- Sessione browser: {report.frontend_session or 'nessuna'}",
            f"- Sessione server: {report.backend_session or 'nessuna'}",
            f"- Intervallo: {window or 'nessuna'}",
            (
                f"- Passaggi: {reproduction.get('frontend_steps', 0)} nel browser, "
                f"{reproduction.get('backend_steps', 0)} sul server"
            ),
            "",
            "L'allegato `diagnostics.json` contiene il contesto, le registrazioni e "
            "le righe di log della finestra fra l'apertura e l'invio.",
        ]
    )
