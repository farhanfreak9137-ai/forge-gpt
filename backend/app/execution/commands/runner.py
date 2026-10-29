import asyncio
import os
import shlex
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from app.config.settings import settings


class SafeCommandRunner:
    """Executes validated allowlisted commands inside workspace directory."""

    def __init__(self, workspace_path: str, execution_mode: Optional[str] = None):
        self.workspace_path = Path(workspace_path).resolve()
        self.execution_mode = execution_mode or settings.execution_mode

    def is_command_allowed(self, command: str) -> Tuple[bool, str]:
        """Check if command passes the strict allowlist and safety policy."""
        stripped = command.strip()
        if not stripped:
            return False, "Command is empty"

        # Split command into arguments without executing shell
        try:
            parts = shlex.split(stripped, posix=False)
            parts = [p.strip('\"\'') for p in parts]
        except Exception as e:
            return False, f"Failed to parse command syntax: {e}"

        if not parts:
            return False, "No command tokens found"

        executable = Path(parts[0]).name.lower()
        if executable.endswith(".exe") or executable.endswith(".cmd") or executable.endswith(".bat"):
            executable = executable.rsplit(".", 1)[0]

        if executable not in settings.allowed_command_prefixes:
            return False, f"Executable '{executable}' is not in the allowed command allowlist."

        # Reject dangerous shell operators like chaining if passed directly
        dangerous_tokens = [";", "&&", "||", "|", "`", "$("]
        for token in dangerous_tokens:
            if token in parts:
                return False, f"Shell operator '{token}' is prohibited in safe native execution."

        return True, "Command is permitted"

    async def run(
        self,
        command: str,
        timeout_seconds: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        timeout = timeout_seconds or settings.command_timeout_seconds
        allowed, reason = self.is_command_allowed(command)
        if not allowed:
            raise PermissionError(f"Security policy rejected command: {reason}")

        start_time = time.time()
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        try:
            parts = shlex.split(command, posix=False)
            parts = [p.strip('\"\'') for p in parts]
            proc = await asyncio.create_subprocess_exec(
                parts[0],
                *parts[1:],
                cwd=str(self.workspace_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout),
                )
                exit_code = proc.returncode or 0
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()
                exit_code = -1
                timed_out = True

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "command": command,
                "exit_code": exit_code,
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "execution_mode": self.execution_mode,
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms,
                "timed_out": False,
                "execution_mode": self.execution_mode,
            }
