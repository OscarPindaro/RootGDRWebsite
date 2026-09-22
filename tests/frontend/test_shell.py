"""Component tests for the global shell: rail, topbar and the phone drawer.

The drawer is a modal surface without a native ``<dialog>``: ``Page.js`` marks
the rest of the shell ``inert``, locks body scroll, contains Tab, closes on
Escape or the scrim, and returns focus to the opener. Ordinary navigation keeps
native Tab order — the rail is not an ARIA composite widget — while
``common.Menu`` keeps its own APG arrow model.
"""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.frontend

PHONE = {"width": 390, "height": 844}


def _world() -> SimpleNamespace:
    return SimpleNamespace(
        id="01a0bc24-aeb6-7e03-acff-4922a42d3e98",
        name="Boschetto di Smeraldo",
        role="Master",
    )


def _nav() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            id="mondo", label="Panoramica", href="/worlds/w", mark="mondo", count=None
        ),
        SimpleNamespace(
            id="personaggi",
            label="Personaggi",
            href="/worlds/w/characters",
            mark="personaggi",
            count=3,
        ),
        SimpleNamespace(
            id="luoghi", label="Luoghi", href="/worlds/w/places", mark="luoghi", count=7
        ),
    ]


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada Lovelace",
        email="ada@example.com",
        role="member",
        avatar_url=None,
        symbol_style="icons",
    )


def _mount(component, *, pages=None, content="", symbol_style=None):
    props = {
        "title": "Boschetto di Smeraldo",
        "current_user": _user(),
        "active": "mondo",
        "world": _world(),
        "nav": _nav(),
        "pages": pages,
    }
    if symbol_style is not None:
        props["symbol_style"] = symbol_style
    return component.mount("layout.Page", props=props, content=content)


def _open_drawer(page):
    page.set_viewport_size(PHONE)
    page.click("#drawer-toggle")
    page.wait_for_selector("#rail.is-open")


# --- Desktop rail geometry ---------------------------------------------------


def test_desktop_rail_is_sticky_inside_a_full_document_column(component):
    page = _mount(component, content='<div style="height: 3000px"></div>')

    assert page.eval_on_selector(".rail", "el => getComputedStyle(el).position") == (
        "absolute"
    )
    assert page.eval_on_selector(
        ".rail__inner", "el => getComputedStyle(el).position"
    ) == ("sticky")

    rail_height = page.eval_on_selector(
        ".rail", "el => el.getBoundingClientRect().height"
    )
    assert rail_height > 3000, rail_height
    assert page.eval_on_selector(
        ".main", "el => getComputedStyle(el).marginLeft"
    ) == page.eval_on_selector(".rail", "el => getComputedStyle(el).width")


def test_desktop_rail_keeps_native_tab_order(component):
    """Arrow keys must not move through a navigation landmark."""
    page = _mount(component)

    links = page.locator("#rail a[href]")
    first = links.nth(0)
    first.focus()
    handle = first.element_handle()
    page.keyboard.press("ArrowDown")

    assert page.evaluate("el => el === document.activeElement", handle)


def test_rail_renders_the_symbol_style_preference(component):
    page = _mount(component, symbol_style="shapes")

    assert page.locator(".navitem__mark.mark--shapes").count() > 0
    assert page.locator('[data-mark-style="shapes"]').count() > 0


def test_in_world_nav_labels_counts_and_current_page(component):
    page = _mount(component, symbol_style="icons")

    labels = page.locator("#rail .rail__nav .navitem__text").all_inner_texts()
    assert labels[:3] == ["Panoramica", "Personaggi", "Luoghi"]
    assert page.locator("#rail .navitem__count").first.inner_text() == "3"

    current = page.locator('#rail .navitem[aria-current="page"]')
    assert current.count() == 1
    assert current.inner_text().strip() == "Panoramica"


def test_global_nav_renders_without_a_world(component):
    page = component.mount(
        "layout.Page",
        props={"title": "Home", "current_user": _user(), "active": "worlds"},
    )

    labels = page.locator("#rail .rail__nav .navitem__text").all_inner_texts()
    assert labels == ["Home", "Mondi"]
    assert page.locator("#rail .rail__world").inner_text() == "Archivio"
    current = page.locator('#rail .navitem[aria-current="page"]')
    assert current.count() == 1
    assert current.inner_text().strip() == "Mondi"


# --- Phone drawer: modal contract -------------------------------------------


def test_drawer_moves_focus_in_and_restores_it_on_escape(component):
    page = _mount(component)
    _open_drawer(page)

    assert page.evaluate("() => Boolean(document.activeElement.closest('#rail'))")

    page.keyboard.press("Escape")

    page.wait_for_selector("#rail.is-open", state="detached")
    assert page.evaluate("() => document.activeElement.id === 'drawer-toggle'")


def test_drawer_marks_the_background_inert_and_locks_scroll(component):
    page = _mount(component)
    _open_drawer(page)

    assert page.eval_on_selector(".main", "el => el.hasAttribute('inert')")
    assert page.evaluate("() => document.body.classList.contains('drawer-open')")
    assert (
        page.eval_on_selector("body", "el => getComputedStyle(el).overflow") == "hidden"
    )

    page.keyboard.press("Escape")

    assert not page.eval_on_selector(".main", "el => el.hasAttribute('inert')")
    assert not page.evaluate("() => document.body.classList.contains('drawer-open')")


def test_tab_cannot_leave_an_open_drawer(component):
    page = _mount(
        component, pages=[{"label": f"Pagina {n}", "href": f"/p/{n}"} for n in range(5)]
    )
    _open_drawer(page)

    for _ in range(40):
        page.keyboard.press("Tab")
        assert page.evaluate(
            "() => Boolean(document.activeElement.closest('#rail'))"
        ), "Tab escaped the drawer"

    for _ in range(8):
        page.keyboard.press("Shift+Tab")
        assert page.evaluate(
            "() => Boolean(document.activeElement.closest('#rail'))"
        ), "Shift+Tab escaped the drawer"


def test_scrim_closes_the_drawer_and_restores_focus(component):
    page = _mount(component)
    _open_drawer(page)

    page.click("#scrim")

    page.wait_for_selector("#rail.is-open", state="detached")
    assert page.evaluate("() => document.activeElement.id === 'drawer-toggle'")


def test_a_selected_navigation_link_closes_without_restoring_focus(component):
    page = _mount(component)
    _open_drawer(page)

    # Prevent the real navigation so the assertion can run on this document.
    page.evaluate(
        """() => {
            const link = document.querySelector('#rail a[href]');
            link.addEventListener('click', event => event.preventDefault());
            link.click();
        }"""
    )

    page.wait_for_selector("#rail.is-open", state="detached")
    assert page.evaluate("() => document.activeElement.id !== 'drawer-toggle'")


def test_opening_the_palette_from_the_drawer_closes_the_drawer(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body={"data": []})
    _open_drawer(page)

    page.click("[data-open-palette]")
    page.wait_for_selector("#palette.is-open")

    assert not page.evaluate(
        "() => document.getElementById('rail').classList.contains('is-open')"
    )
    assert not page.eval_on_selector("#palette", "el => el.hasAttribute('inert')")


# --- Long content ------------------------------------------------------------


def test_many_pages_scroll_and_keep_the_user_menu_reachable(component):
    pages = [
        {"label": f"Pagina numero {n}", "href": f"/worlds/w/pages/{n}"}
        for n in range(40)
    ]
    page = _mount(component, pages=pages)

    assert page.eval_on_selector(
        ".rail__inner", "el => el.scrollHeight > el.clientHeight"
    )
    assert page.locator("#user-menu-trigger").count() == 1


def test_a_long_world_name_truncates_or_wraps_without_overflow(component):
    world = SimpleNamespace(
        id="01a0bc24-aeb6-7e03-acff-4922a42d3e98",
        name="Massimiliano Alessandro Della Rovere di Montalfoglio e Valli",
        role="Master",
    )
    page = component.mount(
        "layout.Page",
        props={
            "title": "Boschetto",
            "current_user": _user(),
            "active": "mondo",
            "world": world,
            "nav": _nav(),
        },
    )

    overflow = page.eval_on_selector(
        ".rail__inner", "el => el.scrollWidth - el.clientWidth"
    )
    assert overflow <= 1, overflow
    assert page.locator("#user-menu-trigger").count() == 1


# --- Menu keyboard model stays its own --------------------------------------


def test_the_user_menu_keeps_its_own_arrow_model(component):
    page = component.mount("layout.UserMenu", props={"current_user": _user()})

    page.click("#user-menu-trigger")
    page.wait_for_selector("#user-menu-popover:popover-open")

    items = page.locator("#user-menu-popover [role=menuitem]")
    assert items.count() >= 2
    page.wait_for_function(
        "() => document.activeElement.closest('#user-menu-popover') !== null"
    )

    page.keyboard.press("ArrowDown")
    assert page.evaluate(
        "() => document.activeElement.getAttribute('data-testid')"
    ) == ("user-menu-logout")
    page.keyboard.press("ArrowUp")
    assert page.evaluate(
        "() => document.activeElement.getAttribute('data-testid')"
    ) == ("user-menu-settings")
