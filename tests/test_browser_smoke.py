"""ブラウザで実際に操作するテストの見本。`uv run playwright install chromium` のあと `uv run pytest tests/test_browser_smoke.py`。"""

from playwright.sync_api import Page, expect


def test_ログインして店一覧が出る(page: Page, live_server: str):
    page.goto(f"{live_server}/login")
    page.fill("#email", "hyeonwoo.kim@2wins.ai")
    page.fill("#password", "eats1234")
    page.click("button[type=submit]")
    page.wait_for_url(f"{live_server}/")
    expect(page.locator(".store-card")).to_have_count(10)
