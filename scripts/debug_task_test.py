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
from app.ai.agent_loop.chat_orchestrator import chat_orchestrator

async def main():
    print("=" * 65)
    print(" FORGEAGENT: BUG DETECTION & AUTONOMOUS REPAIR TEST")
    print("=" * 65)

    debug_ws = root_dir / "workspace" / "debug_task"
    calc_path = debug_ws / "calculator.py"
    test_path = debug_ws / "test_calculator.py"

    calc_code = calc_path.read_text(encoding="utf-8")
    test_code = test_path.read_text(encoding="utf-8")

    prompt = (
        f"I have a file with intentional bugs in `calculator.py`. Here is the code:\n\n"
        f"```python\n{calc_code}\n```\n\n"
        f"And here are the unit tests in `test_calculator.py`:\n\n"
        f"```python\n{test_code}\n```\n\n"
        f"The tests for `multiply`, `divide`, and `calculate_average` are currently failing. "
        f"Please:\n"
        f"1. Explain what bugs exist in `calculator.py`.\n"
        f"2. Output the corrected `calculator.py` inside a code block preceded by `### file: calculator.py` so it is automatically saved locally.\n"
        f"3. Ensure all unit tests will pass."
    )

    print("\n[Step 1] Sending buggy code & test suite to ChatGPT via Edge...")
    print("Waiting for ChatGPT to analyze, debug, and provide fixes...\n")

    reply = await chat_orchestrator.send_user_message(
        message=prompt,
        workspace_path=str(debug_ws),
        auto_pilot=True,
        connector_name="chatgpt_edge",
    )

    print("=" * 65)
    print(" CHATGPT DIAGNOSTICS & EXPLANATION:")
    print("=" * 65)
    clean_msg = reply.get("clean_message") or reply.get("text") or ""
    print(clean_msg)
    print("=" * 65)

    print("\n[Step 2] Checking files modified by ForgeAgent Hands:")
    file_changes = reply.get("executed_file_changes", [])
    if file_changes:
        for fc in file_changes:
            print(f"  ✓ Applied: {fc['path']} ({fc.get('lines', 0)} lines)")
    else:
        print("  Checking disk directly...")

    # Read repaired file
    repaired_code = calc_path.read_text(encoding="utf-8")
    print("\nUpdated `calculator.py` on disk:")
    print("-" * 50)
    print(repaired_code)
    print("-" * 50)

    print("\n[Step 3] Running pytest suite to verify all fixes...")
    import subprocess
    proc = subprocess.run(
        [str(backend_dir / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-v"],
        cwd=str(debug_ws),
        capture_output=True,
        text=True,
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)

    if proc.returncode == 0:
        print("\n>>> ALL 5 TESTS PASSED! AUTONOMOUS DEBUGGING VERIFIED SUCCESSFULLY! <<<\n")
    else:
        print(f"\n[!] Tests still failing with code {proc.returncode}.")

if __name__ == "__main__":
    asyncio.run(main())
