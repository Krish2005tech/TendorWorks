"""Run against a local demo server. This creates a clearly named demonstration project."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "test-results"
    output.mkdir(exist_ok=True)
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    base = os.environ.get("TENDER_TEST_URL", "http://127.0.0.1:8000")
    with sync_playwright() as playwright:
        kwargs = {"executable_path": str(chrome)} if chrome.exists() else {}
        browser = playwright.chromium.launch(headless=True, **kwargs)
        page = browser.new_page(viewport={"width": 1440, "height": 1060}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        expect(page.get_by_role("heading", name="Build with a clearer picture.")).to_be_visible()
        page.screenshot(path=str(output / "workspace.png"), full_page=True)
        page.get_by_role("button", name="Explore a sample estimate").click()
        expect(page.get_by_role("heading", name="What are we building?")).to_be_visible()
        page.get_by_label("Project name", exact=True).fill("Browser verification · primary school")
        page.get_by_role("button", name="Generate concept estimate").click()
        expect(page.locator("#main .badge.draft")).to_be_visible(timeout=60000)
        page.screenshot(path=str(output / "estimate.png"), full_page=True)
        page.get_by_role("tab", name="Bill of quantities").click()
        expect(page.locator("#boq-body tr")).to_have_count(24)
        page.get_by_role("button", name="Brick masonry, including mortar", exact=True).click()
        expect(page.get_by_role("heading", name="Evidence chain")).to_be_visible()
        page.screenshot(path=str(output / "evidence.png"), full_page=True)
        page.get_by_role("button", name="Close dialog").click()
        with page.expect_download() as downloaded:
            page.get_by_role("button", name="Export BOQ").click()
        assert downloaded.value.suggested_filename == "boq.xlsx"
        page.get_by_role("tab", name="Concept drawings").click()
        expect(page.locator("#drawing-canvas img")).to_be_visible()
        page.screenshot(path=str(output / "drawing.png"), full_page=True)
        page.get_by_role("tab", name="Overview").click()
        page.get_by_role("button", name="Add feedback").click()
        page.get_by_label("What should change, and why?").fill(
            "Browser check: verify the concept dimensions against the site survey."
        )
        page.get_by_role("button", name="Submit for review").click()
        expect(page.locator("#detail-dialog")).not_to_be_visible()
        page.get_by_role("link", name="Knowledge library").click()
        expect(page.get_by_role("heading", name="Your knowledge library.")).to_be_visible()
        page.get_by_role("button", name="Scan database folder").click()
        expect(page.get_by_role("button", name="Scan database folder")).to_be_enabled(timeout=15000)
        page.get_by_role("searchbox", name="Search source knowledge").fill("DEMO.007")
        page.get_by_role("button", name="Search", exact=True).click()
        expect(page.locator(".search-result").first).to_be_visible()
        page.screenshot(path=str(output / "knowledge.png"), full_page=True)
        page.get_by_role("link", name="Review & feedback").click()
        expect(page.locator(".feedback-card").first).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(base + "/#projects")
        expect(page.get_by_role("heading", name="Build with a clearer picture.")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(output / "mobile.png"), full_page=True)
        assert not errors, errors
        print(
            json.dumps({"status": "passed", "console_errors": errors, "screenshots": str(output)}, indent=2)
        )
        browser.close()


if __name__ == "__main__":
    main()
