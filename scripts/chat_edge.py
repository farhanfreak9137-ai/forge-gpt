"""
ForgeAgent V1: Interactive Microsoft Edge + ChatGPT Studio & CLI Agent
Combines standard ChatGPT Web (Brain) with ForgeAgent Local Execution Engine (Hands).

Usage:
    python scripts/chat_edge.py
    python scripts/chat_edge.py "How are you?"
    python scripts/chat_edge.py "Create a python script in scripts/calc.py to multiply two numbers"
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
from app.browser.manager.browser_manager import browser_manager
from app.ai.agent_loop.chat_orchestrator import chat_orchestrator


async def chat_once(prompt_text: str, auto_pilot: bool = True):
    print(f"\n[ForgeAgent] Brain: Microsoft Edge (ChatGPT Web)")
    print(f"[ForgeAgent] Hands: Auto-Pilot={'ON' if auto_pilot else 'OFF'}")
    print(f"[ForgeAgent] Sending: \"{prompt_text}\"")
    print("[ForgeAgent] Waiting for ChatGPT and executing actions...\n")

    try:
        reply = await chat_orchestrator.send_user_message(
            message=prompt_text,
            workspace_path=str(root_dir),
            auto_pilot=auto_pilot,
            connector_name="chatgpt_edge",
        )

        print("=" * 60)
        print("ChatGPT:")
        print("=" * 60)
        clean_msg = reply.get("clean_message") or reply.get("text", "")
        print(clean_msg)
        print("=" * 60)

        # Print executed files if any
        file_changes = reply.get("executed_file_changes", [])
        if file_changes:
            print("\n[Hands] Files written to workspace:")
            for fc in file_changes:
                print(f"  ✓ {fc['path']} ({fc['lines']} lines)")

        # Print executed commands if any
        commands = reply.get("executed_commands", [])
        if commands:
            print("\n[Hands] Terminal commands executed:")
            for cmd in commands:
                status = "PASSED" if cmd.get("passed") else "FAILED"
                print(f"  [{status}] {cmd['command']} (exit: {cmd['exit_code']}, {cmd['duration_ms']}ms)")
                if cmd.get("stdout"):
                    print(f"    STDOUT: {cmd['stdout'].strip()}")
                if cmd.get("stderr"):
                    print(f"    STDERR: {cmd['stderr'].strip()}")

        if reply.get("repair_iterations", 0) > 0:
            print(f"\n[Hands] Auto-pilot repaired failures across {reply['repair_iterations']} iteration(s).")

        print()

    except Exception as e:
        print(f"\n[Error] Failed to communicate or execute: {e}\n")


async def interactive_loop(auto_pilot: bool = True):
    print("=" * 68)
    print(" ForgeAgent V1: Antigravity / Cursor Pair Programming Agent")
    print(" Brain: ChatGPT Web (Unlimited Tokens) | Hands: ForgeAgent Engine")
    print("=" * 68)
    print("Ask casual questions, or ask it to create apps, write code & run tests.")
    print("Type your message and press Enter. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting ForgeAgent.")
                break

            await chat_once(user_input, auto_pilot=auto_pilot)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting ForgeAgent.")
            break
        finally:
            await browser_manager.close()


def main():
    args = sys.argv[1:]
    auto_pilot = True
    if "--no-autopilot" in args:
        auto_pilot = False
        args.remove("--no-autopilot")

    if args:
        prompt = " ".join(args)
        asyncio.run(chat_once(prompt, auto_pilot=auto_pilot))
    else:
        asyncio.run(interactive_loop(auto_pilot=auto_pilot))


if __name__ == "__main__":
    main()
