"""Capture the Devpost image gallery at the 3:2 ratio the form asks for.

The existing capture script takes full-page shots, which are 15 to 20 times taller
than they are wide. Devpost renders those as unreadable slivers, so the gallery
needs its own crops built around one section each.

Every image is a real screenshot of the running console, so the gallery cannot
show anything the app does not render. Sections are located by their heading id
rather than a pixel offset, so a layout change moves the crop instead of silently
capturing the wrong thing.

Usage:
    uv run hindsight serve                              # in another shell
    uv run python scripts/capture_gallery.py
"""

from __future__ import annotations

from pathlib import Path

CONSOLE = "http://127.0.0.1:8100"
OUT = Path(__file__).resolve().parent.parent / "docs" / "img" / "gallery"
RATIO = 3 / 2
WIDTH = 1600  # viewport width; the crop is WIDTH x WIDTH/RATIO

# (filename, path, anchor id to centre on, mode, caption for the submission notes)
SHOTS: list[tuple[str, str, str | None, str, str]] = [
    (
        "01-the-problem.png",
        "/",
        None,
        "plain",
        "A model scored 100% in testing and 83% once the answer was taken away.",
    ),
    (
        "02-how-it-works.png",
        "/",
        "what-heading",
        "plain",
        "The four steps, and the one that needs a catalog.",
    ),
    (
        "03-datahub-lineage.png",
        "/",
        "stack-heading",
        "plain",
        "The column-level path from DataHub. The middle hop is a query entity, so the "
        "evidence cites the catalog's own record of the transformation.",
    ),
    (
        "04-what-is-audited.png",
        "/audits/latest",
        "subject-heading",
        "technical",
        "The model, the feature, and the 31 day gap between the decision and the feature's data.",
    ),
    (
        "05-agent-activity.png",
        "/audits/latest",
        "activity-heading",
        "technical",
        "Every DataHub call the audit made, in order, including the MCP Server.",
    ),
    (
        "06-the-inversion.png",
        "/audits/latest",
        "trap-heading",
        "technical",
        "The legitimate feature scores higher on importance. Hindsight clears it and "
        "blocks the other one.",
    ),
    (
        "07-timeline.png",
        "/audits/latest",
        "timeline-heading",
        "technical",
        "One feature reaches past the decision. Everything left of the line was knowable.",
    ),
    (
        "08-writeback.png",
        "/audits/latest",
        "publish-heading",
        "technical",
        "Four records written to DataHub after human approval, each re-read to prove it persisted.",
    ),
    (
        "09-benchmark.png",
        "/evidence",
        "bench-heading",
        "plain",
        "42 cases, 0 false positives, 0 false negatives. Below 40% reach only reading the "
        "code still catches it.",
    ),
    (
        "10-external-data.png",
        "/evidence",
        "external-heading",
        "plain",
        "Run against a dataset we did not create, in a different domain.",
    ),
]


def _shoot(page, path: str, anchor: str | None, out: Path, mode: str) -> bool:
    page.goto(f"{CONSOLE}{path}", wait_until="networkidle")
    page.evaluate(f"document.body.setAttribute('data-mode', {mode!r})")
    page.wait_for_timeout(250)

    height = int(WIDTH / RATIO)
    if anchor is None:
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(150)
        page.screenshot(path=out, clip={"x": 0, "y": 0, "width": WIDTH, "height": height})
        return True

    target = page.query_selector(f"#{anchor}")
    if target is None:
        print(f"  MISS  #{anchor} not on {path}")
        return False

    # Centre the section, then clip a 3:2 window around where it landed.
    target.scroll_into_view_if_needed()
    page.wait_for_timeout(250)
    box = target.bounding_box()
    if box is None:
        print(f"  MISS  #{anchor} has no box on {path}")
        return False

    y = max(0, box["y"] - 40)
    view = page.viewport_size["height"]
    if y + height > view:
        y = max(0, view - height)
    page.screenshot(path=out, clip={"x": 0, "y": y, "width": WIDTH, "height": height})
    return True


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed. Run:")
        print("  uv pip install playwright && uv run playwright install chromium")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    captured = 0
    with sync_playwright() as backend:
        browser = backend.chromium.launch()
        page = browser.new_page(
            viewport={"width": WIDTH, "height": 1400},
            device_scale_factor=2,
            color_scheme="dark",
        )
        for name, path, anchor, mode, _caption in SHOTS:
            if _shoot(page, path, anchor, OUT / name, mode):
                print(f"  wrote {name}")
                captured += 1
        browser.close()

    print(f"\n{captured} of {len(SHOTS)} captured into {OUT}")
    return 0 if captured == len(SHOTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
