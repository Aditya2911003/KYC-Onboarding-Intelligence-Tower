"""Capture README screenshots of all 13 pages and a short demo GIF with Playwright.

Starts the Streamlit app on a free port, visits every page at laptop width,
saves ``docs/screenshots/01_executive.png`` through ``13_about.png``, one phone-width
shot (``mobile_executive.png``) and ``demo.gif`` (Executive -> donut cross-filter
-> Controls -> Customer 360 -> AI Copilot), then stops the app.

Usage::

    python scripts/capture_screenshots.py [--port 8765] [--out docs/screenshots]
"""

from __future__ import annotations

import argparse
import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ("01_executive", ""),
    ("02_funnel", "funnel"),
    ("03_risk", "risk"),
    ("04_controls", "controls"),
    ("05_documents", "documents"),
    ("06_operations", "operations"),
    ("07_review_backlog", "review_backlog"),
    ("08_rules", "rules"),
    ("09_customer_360", "customer_360"),
    ("10_ai_copilot", "ai_copilot"),
    ("11_model_method", "model_method"),
    ("12_data_quality", "data_quality"),
    ("13_about", "about"),
]
WIDTH = 1440
SETTLE_MS = 6_000


def free_port() -> int:
    """Return an unused local TCP port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(port: int, timeout: float = 60.0) -> None:
    """Block until the Streamlit server accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError(f"Streamlit did not start on port {port}")


def settle(page: Page) -> None:
    """Wait for Streamlit to finish rendering the current script run."""
    page.wait_for_timeout(1_000)
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=60_000)
    page.wait_for_timeout(SETTLE_MS)


def full_height(page: Page) -> int:
    """Height of the scrollable Streamlit main area (the window itself does not scroll)."""
    return int(
        page.evaluate(
            "() => { const m = document.querySelector('[data-testid=\"stMain\"]');"
            " return Math.max(m ? m.scrollHeight : 0, document.body.scrollHeight); }"
        )
    )


def shoot(page: Page, path: Path, width: int = WIDTH) -> None:
    """Resize the viewport to the full content height and save a PNG."""
    page.set_viewport_size({"width": width, "height": 900})
    page.wait_for_timeout(500)
    page.set_viewport_size({"width": width, "height": min(full_height(page) + 40, 9_000)})
    page.wait_for_timeout(1_500)
    page.screenshot(path=str(path))


def frame(page: Page, frames: list[Image.Image]) -> None:
    """Append a downscaled viewport frame to the GIF."""
    png = page.screenshot()
    image = Image.open(io.BytesIO(png)).convert("RGB")
    image.thumbnail((1100, 800))
    frames.append(image.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))


def capture(port: int, out: Path) -> None:
    """Visit every page, save screenshots and the demo GIF."""
    out.mkdir(parents=True, exist_ok=True)
    base = f"http://localhost:{port}"
    launch_args: dict = {}
    if os.environ.get("CHROMIUM_PATH"):
        launch_args["executable_path"] = os.environ["CHROMIUM_PATH"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_args)
        page = browser.new_page(viewport={"width": WIDTH, "height": 900})
        for name, path in PAGES:
            page.goto(f"{base}/{path}")
            settle(page)
            shoot(page, out / f"{name}.png")
            print(f"saved {name}.png", flush=True)

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(base)
        settle(page)
        page.screenshot(path=str(out / "mobile_executive.png"), full_page=False)
        print("saved mobile_executive.png", flush=True)

        frames: list[Image.Image] = []
        page.set_viewport_size({"width": WIDTH, "height": 900})
        page.goto(base)
        settle(page)
        frame(page, frames)
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(1_500)
        frame(page, frames)
        points = page.locator("div.st-key-tile_exec_donut g.trace.scatter g.points path")
        if points.count():
            box = points.nth(min(20, points.count() - 1)).bounding_box()
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                settle(page)
                page.mouse.wheel(0, -2_000)
                page.wait_for_timeout(1_000)
                frame(page, frames)
        for path in ("controls", "customer_360", "ai_copilot"):
            page.goto(f"{base}/{path}")
            settle(page)
            frame(page, frames)
        frames[0].save(out / "demo.gif", save_all=True, append_images=frames[1:], duration=2_200, loop=0)
        print(f"saved demo.gif ({len(frames)} frames)", flush=True)
        browser.close()


def main(argv: list[str] | None = None) -> int:
    """Start the app, capture everything, stop the app."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=0, help="port for the temporary app (default: a free port)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "screenshots")
    args = parser.parse_args(argv)
    port = args.port or free_port()
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(REPO_ROOT / "app" / "streamlit_app.py"),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server(port)
        capture(port, args.out)
    finally:
        server.terminate()
        server.wait(timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
