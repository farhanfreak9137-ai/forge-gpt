import sys
import logging
from typing import Dict, Any, Optional
from app.execution.commands.runner import SafeCommandRunner
from app.execution.diagnostics.diagnostics import DiagnosticParser

logger = logging.getLogger("forgeagent.execution.test_runner")


class TestRunner:
    """Executes automated verification and test suites on project workspaces."""

    def __init__(self, command_runner: SafeCommandRunner):
        self.command_runner = command_runner

    async def run_tests(self, custom_command: Optional[str] = None) -> Dict[str, Any]:
        """Detect and execute the project test suite."""
        cmd = custom_command

        # Auto-detect if no custom command provided
        if not cmd:
            ws = self.command_runner.workspace_path
            py_exe = f'"{sys.executable}"'
            if (ws / "pytest.ini").exists() or any(ws.glob("test_*.py")) or (ws / "tests").is_dir():
                cmd = f"{py_exe} -m pytest"
            elif (ws / "package.json").exists():
                cmd = "npm test"
            else:
                cmd = f"{py_exe} -m unittest discover"

        logger.info(f"Executing test command: {cmd}")
        res = await self.command_runner.run(cmd)

        passed = res["exit_code"] == 0
        failure_details = None
        if not passed:
            failure_details = DiagnosticParser.extract_failure_details(
                res["stdout"],
                res["stderr"],
            )

        return {
            "test_command": cmd,
            "passed": passed,
            "exit_code": res["exit_code"],
            "stdout": res["stdout"],
            "stderr": res["stderr"],
            "duration_ms": res["duration_ms"],
            "failure_details": failure_details,
        }
