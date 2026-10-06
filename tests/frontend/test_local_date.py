"""The browser's local ISO date, used by the new-session trigger (REQ-0007/T01).

Real Chromium, the real script: the helper must read the local calendar
components, so a session created just after local midnight is dated with the
new day and one created just before it keeps the old day — a UTC conversion
would name the wrong day in one of the two cases.
"""

from harness.browser_runtime import REPO_ROOT

SCRIPT = REPO_ROOT / "src" / "frontend" / "static" / "js" / "format-times.js"


def test_local_iso_date_uses_local_components(component):
    page = component.mount("common.Button", props={"label": "x"})
    page.add_script_tag(path=str(SCRIPT))

    assert page.evaluate("localIsoDate(new Date(2026, 9, 6, 0, 30))") == "2026-10-06"
    assert page.evaluate("localIsoDate(new Date(2026, 9, 5, 23, 30))") == "2026-10-05"
    assert page.evaluate("localIsoDate(new Date(2026, 9, 5, 12, 0))") == "2026-10-05"
