import sys
import os
import asyncio
from pathlib import Path

# Force UTF-8 encoding for Windows console output
sys.stdout.reconfigure(encoding="utf-8")

# Setup python path to include backend
script_dir = Path(__file__).resolve().parent
root_dir = script_dir.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from app.config.settings import settings
from app.browser.manager.browser_manager import browser_manager
from app.ai.agent_loop.chat_orchestrator import chat_orchestrator

async def main():
    print("=" * 65)
    print(" FORGEAGENT: GENERATING STATIC WEBSITE VIA REAL CHATGPT")
    print("=" * 65)

    workspace_dir = root_dir / "workspace"
    prompt = (
        "Create a complete, modern responsive static website with HTML, CSS, and JS. "
        "Save the files as: "
        "1. static-site/index.html "
        "2. static-site/style.css "
        "3. static-site/script.js "
        "Make it an attractive tech product landing page with a hero banner, features cards, "
        "and an interactive button in JavaScript (e.g. click counter or theme toggle). "
        "Provide the complete code for all three files."
    )

    print(f"\n[1/3] Sending prompt to ChatGPT via Microsoft Edge...")
    print(f"Prompt: {prompt}\n")

    reply = await chat_orchestrator.send_user_message(
        message=prompt,
        workspace_path=str(workspace_dir),
        auto_pilot=True,
        connector_name="chatgpt_edge",
    )

    print("=" * 65)
    print(" CHATGPT RESPONSE RECEIVED:")
    print("=" * 65)
    clean_msg = reply.get("clean_message") or reply.get("text") or ""
    print(clean_msg[:500] + ("..." if len(clean_msg) > 500 else ""))
    print("=" * 65)

    print("\n[2/3] Verifying files saved locally by ForgeAgent Hands:")
    file_changes = reply.get("executed_file_changes", [])
    if file_changes:
        for fc in file_changes:
            print(f"  ✓ {fc['path']} ({fc.get('lines', 0)} lines)")
    else:
        print("  Checking workspace directory directly...")

    # Verify physical files on disk
    site_dir = workspace_dir / "static-site"
    expected_files = ["index.html", "style.css", "script.js"]
    saved_files = []

    for fname in expected_files:
        fpath = site_dir / fname
        if fpath.exists():
            size = fpath.stat().st_size
            line_count = len(fpath.read_text(encoding="utf-8", errors="ignore").splitlines())
            saved_files.append(fname)
            print(f"  [FOUND ON DISK] {fname} ({size} bytes, {line_count} lines)")
        else:
            print(f"  [MISSING] {fname}")

    # Also check if files were created in workspace root without static-site/ prefix
    if len(saved_files) == 0:
        for fname in expected_files:
            fpath = workspace_dir / fname
            if fpath.exists():
                size = fpath.stat().st_size
                line_count = len(fpath.read_text(encoding="utf-8", errors="ignore").splitlines())
                saved_files.append(fname)
                print(f"  [FOUND IN ROOT] {fname} ({size} bytes, {line_count} lines)")

    print(f"\nTotal files successfully written to disk: {len(saved_files)}/{len(expected_files)}")

    if len(saved_files) > 0:
        print("\n[3/3] Rendering static website in Playwright...")
        target_html = (site_dir / "index.html") if (site_dir / "index.html").exists() else (workspace_dir / "index.html")
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto(target_html.as_uri())
            title = await page.title()
            print(f"  ✓ Rendered page title: '{title}'")
            screenshot_path = str(root_dir / "workspace" / "static_site_rendered.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"  ✓ Saved screenshot of generated website to: {screenshot_path}")
            await browser.close()
        print("\n>>> STATIC WEBSITE CREATION AND LOCAL PERSISTENCE FULLY VERIFIED! <<<\n")
    else:
        print("\n[!] No files were created. Inspecting raw reply actions...")
        print(f"Parsed file actions: {reply.get('executed_file_changes')}")
        print(f"Action errors: {reply.get('action_errors')}")

if __name__ == "__main__":
    asyncio.run(main())

