from pathlib import Path
from types import SimpleNamespace

from backend.jinja import _markdown, get_catalog


COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"


def test_markdown_renders_commonmark_without_raw_html() -> None:
    rendered = str(_markdown("# Heading\n\n<script>alert(1)</script>"))

    assert "<h1>Heading</h1>" in rendered
    assert "<script>" not in rendered


def test_catalog_exposes_configured_application_name() -> None:
    catalog = get_catalog(str(COMPONENTS_DIR), app_name="Example App")

    assert catalog.jinja_env.globals["app_name"] == "Example App"


def test_showcase_sidebar_link_is_development_only() -> None:
    user = SimpleNamespace(name="Admin", email="admin@example.com", role="admin")
    development = get_catalog(str(COMPONENTS_DIR), env="dev")
    production = get_catalog(str(COMPONENTS_DIR), env="prod")

    assert 'href="/components"' in development.render(
        "layout.Sidebar", current_user=user
    )
    assert 'href="/components"' not in production.render(
        "layout.Sidebar", current_user=user
    )


def test_dev_login_control_is_only_rendered_when_enabled() -> None:
    catalog = get_catalog(str(COMPONENTS_DIR))

    disabled = catalog.render("pages.login.Login", dev_login_enabled=False)
    enabled = catalog.render("pages.login.Login", dev_login_enabled=True)

    assert "Dev sign in" not in disabled
    assert "Dev sign in" in enabled
