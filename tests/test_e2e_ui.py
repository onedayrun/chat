import os
from pathlib import Path

import pytest
import httpx

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # pragma: no cover
    sync_playwright = None


def _get_base_url() -> str:
    base_url = os.environ.get("E2E_BASE_URL")
    if not base_url:
        pytest.skip("E2E_BASE_URL is required for e2e_ui tests")

    return base_url.rstrip("/")


@pytest.mark.e2e_ui
def test_ui_screenshots():
    if sync_playwright is None:
        pytest.skip("playwright is not installed")

    base_url = _get_base_url()

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{base_url}/projects",
            json={
                "client_name": "E2E_UI",
                "tier": "8h",
                "initial_message": "Hello",
            },
        )
        resp.raise_for_status()
        project_id = resp.json()["project_id"]

    out_dir = Path("artifacts/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        docs_resp = page.goto(f"{base_url}/docs", wait_until="domcontentloaded")
        assert docs_resp is not None and docs_resp.ok
        page.screenshot(path=str(out_dir / "docs.png"), full_page=True)

        chat_resp = page.goto(f"{base_url}/chat/{project_id}", wait_until="domcontentloaded")
        assert chat_resp is not None and chat_resp.ok
        page.wait_for_selector("#status", timeout=10_000)
        try:
            page.wait_for_function(
                "document.getElementById('status') && document.getElementById('status').textContent.includes('Connected')",
                timeout=10_000,
            )
        except Exception:
            pass
        page.screenshot(path=str(out_dir / f"chat-{project_id}.png"), full_page=True)

        browser.close()
