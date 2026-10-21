"""Capture real-app prototype states without authentication or mutation calls."""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from harness.browser_runtime import ensure_browsers_path


async def capture(base_url: str, output: Path, views: list[str]) -> None:
    ensure_browsers_path()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        for view in views:
            for name, width, height in [
                ("desktop", 1440, 1000),
                ("phone", 390, 844),
            ]:
                context = await browser.new_context(
                    viewport={"width": width, "height": height},
                    reduced_motion="reduce",
                )
                page = await context.new_page()
                errors = []
                mutations = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "console",
                    lambda message: (
                        errors.append(message.text) if message.type == "error" else None
                    ),
                )
                page.on(
                    "request",
                    lambda request: (
                        mutations.append(request.url)
                        if request.method not in {"GET", "HEAD", "OPTIONS"}
                        else None
                    ),
                )
                response = await page.goto(
                    f"{base_url}/components/planning?view={view}",
                    wait_until="networkidle",
                )
                assert response is not None and response.status == 200
                await page.evaluate("document.fonts.ready")
                await page.screenshot(
                    path=output / f"{view}-{name}-open.png", full_page=True
                )
                if await page.locator("[data-card-mode-choice='flip']").count():
                    await page.locator("[data-card-mode-choice='flip']").click()
                    for button in await page.locator("[data-card-flip]").all():
                        await button.click()
                    await page.evaluate("window.scrollTo(0, 0)")
                    await page.screenshot(
                        path=output / f"{view}-{name}-reverse.png", full_page=True
                    )
                if view == "assistant":
                    await page.locator(
                        "[data-demo-request] button[type='submit']"
                    ).click()
                    await page.locator("[data-reference-open]").first.click()
                    await page.locator("[name='planning-reference-name']").fill(
                        "Nome corretto"
                    )
                    await page.locator("[data-reference-correct]").click()
                elif view == "evaluation":
                    await page.locator("[name='planning-produced-count']").fill("2")
                    await page.locator(
                        "[data-demo-evaluation] button[type='submit']"
                    ).click()
                elif view == "history":
                    await page.locator("label.switch").click()
                    await page.locator("[data-demo-undo]").click()
                elif view == "settings":
                    await page.locator(
                        "[data-demo-settings] button[type='submit']"
                    ).click()
                if view in {"assistant", "evaluation", "history", "settings"}:
                    await page.evaluate("window.scrollTo(0, 0)")
                    await page.screenshot(
                        path=output / f"{view}-{name}-interaction.png", full_page=True
                    )
                if view == "npcs":
                    await page.get_by_role(
                        "button", name="Scheda aperta", exact=True
                    ).click()
                    marks = page.locator("[data-track='ada:wounds:0']")
                    await marks.check()
                    await page.get_by_role(
                        "button", name="Apri riferimento rapido"
                    ).click()
                    await page.locator(
                        "#planning-quick-reference [data-npc='ada']"
                    ).wait_for()
                    assert await marks.count() == 2
                    assert (
                        await marks.nth(0).is_checked()
                        and await marks.nth(1).is_checked()
                    )
                    assert (
                        await page.locator(
                            "#planning-quick-reference .planning-npc__tracks"
                        ).evaluate("element => getComputedStyle(element).display")
                        == "grid"
                    )
                overflow = await page.evaluate(
                    "document.documentElement.scrollWidth > window.innerWidth"
                )
                results.append(
                    {
                        "view": view,
                        "viewport": name,
                        "overflow": overflow,
                        "errors": list(errors),
                        "mutations": list(mutations),
                    }
                )
                assert not overflow and not errors and not mutations, results[-1]
                await context.close()
        await browser.close()
    (output / "metrics.json").write_text(json.dumps(results, indent=2))
    print(f"Captured {len(results)} viewport/view combinations in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--views", nargs="+", default=["story", "npcs"])
    args = parser.parse_args()
    asyncio.run(capture(args.base_url, args.output_dir, args.views))
