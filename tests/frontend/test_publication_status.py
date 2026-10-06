"""The publication badge (REQ-0005/T02).

A compact rectangular stamp on paper: the state colour lives on the rule and
the marker, the word stays readable ink, and the badge is a fact — never
focusable, never colour alone, and it does not move the bar between states.
"""

import pytest

pytestmark = pytest.mark.frontend


def _mount(component, **overrides):
    props = {
        "base": "/worlds/w/characters/c",
        "eyebrow": "Personaggio",
        "can_manage": True,
    }
    props.update(overrides)
    return component.mount("editorial.Docbar", props=props)


def _badge(page) -> dict:
    return page.evaluate(
        """() => {
            const badge = document.querySelector('[data-publication-status]');
            const marker = badge.querySelector('.publication-status__marker');
            const style = getComputedStyle(badge);
            const box = badge.getBoundingClientRect();
            return {
                state: badge.dataset.state,
                text: badge.textContent.trim(),
                rendered: badge.innerText.trim().toUpperCase(),
                markerHidden: marker.getAttribute('aria-hidden'),
                borderColor: style.borderTopColor,
                markerColor: getComputedStyle(marker).backgroundColor,
                background: style.backgroundColor,
                color: style.color,
                radius: parseFloat(style.borderTopLeftRadius),
                height: box.height,
                tabindex: badge.getAttribute('tabindex'),
            };
        }"""
    )


def _contrast(page, first: str, second: str) -> float:
    return page.evaluate(
        """([a, b]) => {
            const luminance = (rgb) => {
                const parts = rgb.match(/\\d+/g).slice(0, 3).map(Number);
                const channels = parts.map((value) => {
                    const channel = value / 255;
                    return channel <= 0.03928
                        ? channel / 12.92
                        : Math.pow((channel + 0.055) / 1.055, 2.4);
                });
                return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
            };
            const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
            return (light + 0.05) / (dark + 0.05);
        }""",
        [first, second],
    )


@pytest.mark.parametrize("is_draft,text", [(True, "Bozza"), (False, "Pubblicato")])
def test_the_badge_always_carries_the_state_text(component, is_draft, text):
    page = _mount(component, is_draft=is_draft)

    badge = _badge(page)
    assert badge["state"] == ("draft" if is_draft else "published")
    # The copy is the plain word; the atlas voice uppercases it.
    assert badge["text"] == text
    assert badge["rendered"] == text.upper()
    # The marker is decoration; the word carries the state.
    assert badge["markerHidden"] == "true"


def test_the_states_differ_in_colour_and_stay_readable(component):
    draft = _badge(_mount(component, is_draft=True))
    published = _badge(_mount(component, is_draft=False))

    assert draft["borderColor"] != published["borderColor"]
    assert draft["markerColor"] != published["markerColor"]
    for badge in (draft, published):
        assert badge["background"] != badge["borderColor"]
        assert _contrast(component.page, badge["color"], badge["background"]) >= 4.5


def test_the_badge_is_rectangular_and_never_focusable(component):
    page = _mount(component)

    badge = _badge(page)
    assert badge["radius"] <= 2.0
    assert badge["tabindex"] is None
    # Tabbing through the bar never lands on a fact.
    reached = page.evaluate(
        """() => {
            const facts = [document.querySelector('[data-publication-status]')];
            return facts.some((el) => { el.focus(); return document.activeElement === el; });
        }"""
    )
    assert reached is False


def test_the_bar_does_not_move_between_states(component):
    draft = _mount(component, is_draft=True)
    draft_geometry = draft.evaluate(
        """() => {
            const bar = document.querySelector('.docbar');
            const badge = document.querySelector('[data-publication-status]');
            return [bar.getBoundingClientRect().height, badge.getBoundingClientRect().height];
        }"""
    )
    published = _mount(component, is_draft=False)
    published_geometry = published.evaluate(
        """() => {
            const bar = document.querySelector('.docbar');
            const badge = document.querySelector('[data-publication-status]');
            return [bar.getBoundingClientRect().height, badge.getBoundingClientRect().height];
        }"""
    )
    assert draft_geometry == published_geometry


def test_the_badge_keeps_its_shape_on_phone(component):
    page = _mount(component)
    page.set_viewport_size({"width": 390, "height": 844})

    overflow = page.evaluate(
        """() => {
            const badge = document.querySelector('[data-publication-status]');
            const box = badge.getBoundingClientRect();
            return {right: box.right, width: window.innerWidth,
                    height: box.height,
                    pageOverflow: document.documentElement.scrollWidth
                        - document.documentElement.clientWidth};
        }"""
    )
    assert overflow["pageOverflow"] == 0
    assert overflow["right"] <= overflow["width"]
    assert overflow["height"] < 44
