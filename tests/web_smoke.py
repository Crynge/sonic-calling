from pathlib import Path
from playwright.sync_api import sync_playwright


def main() -> None:
    output_dir = Path("tests/artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        page.locator("text=Launch Simulator").click()
        page.wait_for_timeout(1500)
        page.locator("textarea").fill("Please schedule me for tomorrow afternoon.")
        page.locator("text=Run Next Turn").click()
        page.wait_for_timeout(1200)
        page.locator("text=Twilio-ready").wait_for()
        page.screenshot(path=str(output_dir / "sonic-calling-smoke.png"), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
