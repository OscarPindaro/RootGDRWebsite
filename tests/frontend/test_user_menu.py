"""Component test for the sidebar user menu trigger layout.

The trigger is a dedicated identity control (not a ``common.Button``): avatar,
name/email and chevron on one row, the chevron on the right. The avatar and
chevron are vertically centered on the identity block, and the name/email text
truncates instead of pushing the chevron out.
"""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.frontend


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada Lovelace",
        email="ada@example.com",
        role="member",
        avatar_url=None,
    )


def _rect(page, selector: str) -> dict:
    return page.evaluate(
        """selector => {
            const rect = document.querySelector(selector).getBoundingClientRect();
            return {top: rect.top, left: rect.left, width: rect.width, height: rect.height};
        }""",
        selector,
    )


def _center(rect: dict) -> float:
    return rect["top"] + rect["height"] / 2


def test_trigger_lays_avatar_name_and_chevron_on_one_row(component):
    page = component.mount("layout.UserMenu", props={"current_user": _user()})

    avatar = _rect(page, "#user-menu-trigger .avatar")
    info = _rect(page, "#user-menu-trigger .user-menu-info")
    name = _rect(page, "#user-menu-trigger .user-menu-name")
    chevron = _rect(page, '#user-menu-trigger [data-lucide="chevron-up"]')

    # The avatar and the chevron are centered on the identity block, so the
    # row reads as one line even though name and email stack.
    assert abs(_center(avatar) - _center(info)) < 4
    assert abs(_center(chevron) - _center(info)) < 4
    assert avatar["left"] < name["left"]
    assert chevron["left"] > name["left"]


def test_trigger_is_a_dedicated_identity_control_not_a_button(component):
    """The acceptance forbids a generic Button override for user identity."""
    page = component.mount("layout.UserMenu", props={"current_user": _user()})

    trigger = page.locator("#user-menu-trigger")
    classes = trigger.get_attribute("class") or ""
    assert "btn" not in classes.split()
    assert trigger.get_attribute("aria-haspopup") == "menu"
    assert trigger.get_attribute("popovertarget") == "user-menu-popover"


def test_a_long_identity_truncates_without_hiding_the_chevron(component):
    user = SimpleNamespace(
        name="Massimiliano Alessandro Della Rovere di Montalfoglio",
        email="massimiliano.alessandro.della.rovere@example-very-long-domain.test",
        role="member",
        avatar_url=None,
    )
    page = component.mount("layout.UserMenu", props={"current_user": user})
    page.set_viewport_size({"width": 240, "height": 400})

    name = page.locator("#user-menu-trigger .user-menu-name")
    email = page.locator("#user-menu-trigger .user-menu-email")
    chevron = page.locator('#user-menu-trigger [data-lucide="chevron-up"]')

    assert name.evaluate("el => el.scrollWidth > el.clientWidth")
    assert email.evaluate("el => el.scrollWidth > el.clientWidth")
    assert chevron.bounding_box() is not None
    trigger = page.locator("#user-menu-trigger").bounding_box()
    assert chevron.bounding_box()["x"] < trigger["x"] + trigger["width"]
