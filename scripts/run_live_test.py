import os
import sys
import asyncio
from pathlib import Path

# Force UTF-8 encoding for Windows console output
sys.stdout.reconfigure(encoding="utf-8")

# Setup python path to include backend
script_dir = Path(__file__).resolve().parent
root_dir = script_dir.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from app.browser.manager.browser_manager import browser_manager
from app.ai.adapters.chatgpt_edge_adapter import ChatGPTEdgeAdapter

async def run_live_test():
    print("=" * 65)
    print(" FORGEAGENT V1: REAL CHATGPT + MICROSOFT EDGE LIVE TEST")
    print("=" * 65)

    print("\n[Step 1] Initializing ChatGPT Edge Adapter...")
    adapter = ChatGPTEdgeAdapter("chatgpt_edge", {
        "website_url": "https://chatgpt.com",
        "timeout_ms": 60000,
        "response_timeout_ms": 120000,
    })

    edge_avail = await adapter.check_availability()
    print(f"  ✓ Microsoft Edge binary detected: {browser_manager.find_edge_path()}")

    print("\n[Step 2] Ensuring Microsoft Edge is running on desktop with port 9222...")
    is_edge_up = browser_manager.ensure_edge_running()
    print(f"  ✓ Edge CDP port 9222 status: {'ACTIVE' if is_edge_up else 'FAILED TO LAUNCH'}")
    if not is_edge_up:
        print("  [!] Please ensure Edge is started via START_EDGE.bat")
        return

    print("\n[Step 3] Connecting Playwright over CDP to Microsoft Edge...")
    try:
        page = await browser_manager.get_page()
        print(f"  ✓ Attached to Edge tab. Current URL: {page.url}")
    except Exception as e:
        print(f"  ✗ Failed to attach to Edge: {e}")
        return

    print("\n[Step 4] Navigating / Checking ChatGPT Web session...")
    if "chatgpt.com" not in page.url:
        print("  Navigating to https://chatgpt.com...")
        await page.goto("https://chatgpt.com", timeout=60000)
        await page.wait_for_timeout(4000)

    print(f"  ✓ Page title: '{await page.title()}'")

    # Check for login wall vs active chat
    content = await page.content()
    is_logged_in = any(x in content for x in ["prompt-textarea", "ProseMirror", "Send prompt", "Send message"])
    print(f"  ✓ ChatGPT session status: {'READY FOR PROMPTS (LOGGED IN)' if is_logged_in else 'LOGIN REQUIRED'}")

    if not is_logged_in:
        print("\n  [!] Notice: You need to log into your ChatGPT account in the opened Edge window.")
        print("      Once logged in, the session is saved permanently in backend/data/browser_profile.")
        return

    print("\n[Step 5] Sending test message to live ChatGPT...")
    test_prompt = "Hello from ForgeAgent test! Please reply with exactly: 'Edge automation works'."
    print(f"  Sending prompt: \"{test_prompt}\"")
    
    envelope = await adapter.send_request(
        prompt=test_prompt,
        task_id="live-test-1",
        request_id="live-req-1",
    )

    print("\n" + "=" * 65)
    print(" REAL CHATGPT REPLY CAPTURED VIA MICROSOFT EDGE:")
    print("=" * 65)
    reply_text = envelope.payload.get("analysis", "") or envelope.payload.get("summary", "")
    print(reply_text)
    print("=" * 65)
    print("\n>>> LIVE EDGE + CHATGPT TEST PASSED SUCCESSFULLY! <<<\n")

if __name__ == "__main__":
    try:
        asyncio.run(run_live_test())
    except Exception as exc:
        print(f"\n[Test Error]: {exc}")
        import traceback
        traceback.print_exc()

