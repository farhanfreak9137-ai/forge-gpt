"""
ForgeAgent V1: Direct Interactive Microsoft Edge + ChatGPT Chat Script
Usage:
    python scripts/chat_edge.py
    python scripts/chat_edge.py "Write a python function to calculate fibonacci numbers"
    python scripts/chat_edge.py --headless "Hello ChatGPT"
"""

import sys
import os
import asyncio
from pathlib import Path

# Fix Windows console UTF-8 printing
sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

from app.config.settings import settings
from app.ai.adapters.chatgpt_edge_adapter import ChatGPTEdgeAdapter
from app.browser.manager.browser_manager import browser_manager


async def chat_once(prompt_text: str, headless: bool = False):
    browser_manager.headless = headless
    adapter = ChatGPTEdgeAdapter("chatgpt_edge", {
        "website_url": "https://chatgpt.com",
        "timeout_ms": 60000,
    })

    print(f"\n[ForgeAgent] Opening Microsoft Edge (headless={headless})...")
    print(f"[ForgeAgent] Sending prompt to ChatGPT: \"{prompt_text}\"")
    print("[ForgeAgent] Waiting for ChatGPT to respond...\n")

    try:
        envelope = await adapter.send_request(
            prompt=prompt_text,
            task_id="cli-chat-task",
            request_id="cli-chat-req",
        )
        reply = envelope.payload.get("analysis") or envelope.payload.get("summary") or str(envelope.payload)
        print("=" * 60)
        print("ChatGPT Response (via Microsoft Edge):")
        print("=" * 60)
        print(reply)
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"\n[Error] Failed to communicate with ChatGPT: {e}")
    finally:
        await browser_manager.close()


async def interactive_loop(headless: bool = False):
    print("=" * 65)
    print(" ForgeAgent V1: Interactive Microsoft Edge + ChatGPT Chat")
    print("=" * 65)
    print("Type your message and press Enter. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting chat.")
                break

            await chat_once(user_input, headless=headless)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat.")
            break


def main():
    args = sys.argv[1:]
    headless = False
    if "--headless" in args:
        headless = True
        args.remove("--headless")

    if args:
        prompt = " ".join(args)
        asyncio.run(chat_once(prompt, headless=headless))
    else:
        asyncio.run(interactive_loop(headless=headless))


if __name__ == "__main__":
    main()
