"""Component test for the sidebar user menu trigger layout.

The trigger is a ``common.Button`` whose slotted content (avatar, name/email,
chevron) must read as a single row with the chevron on the right.
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
            return {top: rect.top, left: rect.left, width: rect.width};
        }""",
        selector,
    )


def test_trigger_lays_avatar_name_and_chevron_on_one_row(component):
    page = component.mount("layout.UserMenu", props={"current_user": _user()})

    avatar = _rect(page, "#user-menu-trigger .avatar")
    name = _rect(page, "#user-menu-trigger .user-menu-name")
    chevron = _rect(page, '#user-menu-trigger [data-lucide="chevron-up"]')

    assert abs(avatar["top"] - name["top"]) < 8
    assert abs(chevron["top"] - name["top"]) < 8
    assert chevron["left"] > name["left"]
