"""Capture the screenshots a judge sees before deciding whether to run anything.

Most reviewers will not stand up Docker and DataHub to evaluate a submission, so
the images are how they see that Hindsight genuinely reads and writes a real
catalog. Automating the capture means the README's pictures can never drift from
what the app actually renders.

Usage:
    uv run python scripts/capture_screenshots.py            # console only
    uv run python scripts/capture_screenshots.py --datahub  # include DataHub UI

Requires the console on http://127.0.0.1:8100 (`uv run hindsight serve`), and for
--datahub a local DataHub at http://localhost:9002 with a published audit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CONSOLE = "http://127.0.0.1:8100"
DATAHUB = "http://localhost:9002"
OUT = Path(__file__).resolve().parent.parent / "docs" / "img"

# (filename, url, description, theme, full_page)
CONSOLE_SHOTS = [
    ("console-overview.png", "/", "Overview with the scenario picker", "dark", True),
    ("console-overview-light.png", "/", "The same page in light theme", "light", True),
    ("console-audit-plain.png", "/audits/latest", "Plain-English verdict", "dark", True),
    ("console-evidence.png", "/evidence", "The artifacts, read from disk", "dark", True),
    ("console-runs.png", "/audits", "Run history", "dark", False),
    ("console-settings.png", "/settings", "Connection and audit target", "dark", False),
]


def _capture(page, url: str, path: Path, *, theme: str, full_page: bool, mode: str) -> None:
    page.goto(url, wait_until="networkidle", timeout=45000)
    page.evaluate(
        "([t, m]) => { try { localStorage.setItem('hindsight-theme', t);"
        " localStorage.setItem('hindsight-mode', m); } catch (e) {} }",
        [theme, mode],
    )
    page.reload(wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(700)  # let the activity log settle
    page.screenshot(path=str(path), full_page=full_page)
    print(f"  captured {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datahub", action="store_true", help="also capture the DataHub UI")
    parser.add_argument("--console", default=CONSOLE)
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed. Run:")
        print("  uv pip install playwright && uv run playwright install chromium")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as backend:
        browser = backend.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)

        print("Console:")
        for name, path_part, _desc, theme, full_page in CONSOLE_SHOTS:
            mode = "technical" if "technical" in name else "plain"
            _capture(
                page,
                args.console + path_part,
                OUT / name,
                theme=theme,
                full_page=full_page,
                mode=mode,
            )

        # The technical view is a separate shot of the same route.
        _capture(
            page,
            args.console + "/audits/latest",
            OUT / "console-audit-technical.png",
            theme="dark",
            full_page=True,
            mode="technical",
        )

        if args.datahub:
            print("DataHub:")
            for name, path_part in (
                ("datahub-search.png", "/search?query=hindsight"),
                ("datahub-tags.png", "/tag/urn:li:tag:hindsight:leakage-confirmed"),
            ):
                try:
                    page.goto(DATAHUB + path_part, wait_until="networkidle", timeout=45000)
                    page.wait_for_timeout(1500)
                    page.screenshot(path=str(OUT / name))
                    print(f"  captured {name}")
                except Exception as error:  # noqa: BLE001 - best effort, DataHub may need login
                    print(f"  skipped {name}: {error}")

        browser.close()

    print(f"\nWrote screenshots to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
