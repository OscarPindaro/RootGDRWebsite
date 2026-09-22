"""Designed error pages and the content negotiation behind them.

An HTML navigation that fails should land on a page composed from the product's
primitives, not on a raw framework payload: FastAPI answers a browser with
``{"detail": "Not Found"}`` by default. A JSON API client keeps the JSON
contract — the ``Accept`` header decides — and an htmx request is never sent a
whole page, because htmx does not swap a failed response; the page-level
fallback (``common.RequestFallback``, driven by ``static/js/feedback.js``) is
what the reader sees there.

The 500 page carries the request id: it is the one failure a reader has to
report, and ``harness logs --request-id`` exists to find it. A 401, 403 or 404
is self-explanatory, so the id would only be noise on those pages.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from .correlation import current as current_correlation
from .jinja import get_catalog


@dataclass(frozen=True)
class ErrorCopy:
    title: str
    message: str


ERROR_COPY: dict[int, ErrorCopy] = {
    401: ErrorCopy(
        title="Accesso richiesto",
        message="Devi accedere per vedere questa pagina. Accedi per continuare.",
    ),
    403: ErrorCopy(
        title="Non hai i permessi",
        message=(
            "Il tuo account non può vedere questa pagina. "
            "Se pensi sia un errore, chiedilo a chi amministra il mondo."
        ),
    ),
    404: ErrorCopy(
        title="Pagina non trovata",
        message=(
            "Questa pagina non esiste o è stata spostata. "
            "Controlla l’indirizzo o torna ai mondi."
        ),
    ),
    500: ErrorCopy(
        title="Qualcosa è andato storto",
        message=(
            "Il server non ha potuto completare la richiesta. "
            "Riprova tra qualche istante."
        ),
    ),
}


def _accepts_html(request: Request) -> bool:
    """Whether the client is a browser navigation rather than an API call.

    htmx sends ``HX-Request`` and swaps a fragment: a whole error page must
    never land in a fragment target, so an htmx request is answered as JSON and
    the page-level fallback is what the reader sees.
    """
    if request.headers.get("HX-Request") == "true":
        return False
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "application/xhtml+xml" in accept


def _render(
    request: Request, status: int, request_id: str | None = None
) -> HTMLResponse | None:
    config = getattr(request.app.state, "config", None)
    frontend = getattr(config, "frontend", None)
    if frontend is None or not frontend.enabled:
        return None
    copy = ERROR_COPY[status]
    catalog = get_catalog(
        frontend.components_dir,
        env=config.env,
        app_name=config.app_name,
        replay_enabled=bool(config.replay and config.replay.enabled),
    )
    html = catalog.render(
        "pages.errors.ErrorPage",
        status=status,
        title=copy.title,
        message=copy.message,
        request_id=request_id,
    )
    headers = {"X-Request-ID": request_id} if request_id else None
    return HTMLResponse(html, status_code=status, headers=headers)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    """A designed page for a browser, the framework's JSON contract otherwise.

    Reproduces FastAPI's default body for every other status, so a 422, a 405 or
    an API 404 is unchanged.
    """
    if exc.status_code in ERROR_COPY and _accepts_html(request):
        page = _render(request, exc.status_code)
        if page is not None:
            return page
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
    )


async def server_error_handler(request: Request, exc: Exception) -> Response:
    request_id = getattr(request.state, "request_id", None) or (
        current_correlation().request_id
    )
    if _accepts_html(request):
        page = _render(request, 500, request_id=request_id)
        if page is not None:
            return page
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(
        {"detail": "Internal Server Error"}, status_code=500, headers=headers
    )


def register_error_handlers(app: FastAPI) -> None:
    """Content-negotiated error responses for the whole application."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, server_error_handler)
