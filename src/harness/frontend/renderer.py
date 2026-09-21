"""Render real JinjaX components into a minimal test page.

The component is rendered by the same catalog the application uses
(``backend.jinja.get_catalog``), so the markup under test is the markup the
app ships. Colocated CSS/JS discovered by JinjaX is emitted into the shell,
which also links the repository's real ``main.css``.
"""

from pathlib import Path

from pydantic import BaseModel

from backend.jinja import get_catalog

_SHELL = """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Component test</title>
  <link rel="stylesheet" href="/static/css/main.css">
  {assets}
</head>
<body hx-ext="json-enc">
  {content}
  {scripts}
</body>
</html>
"""


class RenderedPage(BaseModel):
    html: str
    asset_urls: list[str]


def render_component(
    components_dir: Path,
    component: str,
    props: dict | None = None,
    content: str = "",
    *,
    htmx: bool = False,
) -> RenderedPage:
    """Render one component with the real catalog and wrap it in a shell.

    ``props`` values are typed domain objects (Pydantic models), matching how
    views pass data to components. ``content`` is the JinjaX child content.
    """
    catalog = get_catalog(str(components_dir), env="dev", app_name="harness-frontend")
    kwargs: dict = dict(props or {})
    if content:
        kwargs["_content"] = content
    html = catalog.render(component, **kwargs)
    tags = "\n".join(
        [
            f'<link rel="stylesheet" href="{catalog.root_url}{url}">'
            for url in catalog.collected_css
        ]
        + [
            f'<script type="module" src="{catalog.root_url}{url}"></script>'
            for url in catalog.collected_js
        ]
    )
    assets = [
        f"{catalog.root_url}{url}"
        for url in (*catalog.collected_css, *catalog.collected_js)
    ]
    scripts = (
        """
    <script src="/static/js/htmx.min.js"></script>
    <script src="/static/js/json-enc.min.js"></script>"""
        if htmx
        else ""
    )
    page = _SHELL.format(content=html, assets=tags, scripts=scripts)
    return RenderedPage(html=page, asset_urls=assets)
