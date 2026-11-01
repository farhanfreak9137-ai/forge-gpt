import shlex
from enum import Enum
from typing import Dict, Any, Tuple, Optional
from app.ai.protocol.protocol import ChangeOperation, CodeChangeItem


class PermissionLevel(str, Enum):
    AUTOMATICALLY_ALLOWED = "AUTOMATICALLY_ALLOWED"
    TASK_ALLOWED = "TASK_ALLOWED"
    EXPLICIT_APPROVAL_REQUIRED = "EXPLICIT_APPROVAL_REQUIRED"


class PermissionPolicy:
    """Supervised autonomy enforcement engine for ForgeAgent."""

    def __init__(self):
        self._emergency_stop_triggered: bool = False

    def trigger_emergency_stop(self) -> None:
        self._emergency_stop_triggered = True

    def reset_emergency_stop(self) -> None:
        self._emergency_stop_triggered = False

    @property
    def is_emergency_stop_active(self) -> bool:
        return self._emergency_stop_triggered

    @staticmethod
    def is_sensitive_path(path: str) -> bool:
        normalized = path.replace("\\", "/").strip().lower()
        name = normalized.rsplit("/", 1)[-1]
        return (
            name.startswith(".env")
            or name in {"docker-compose.yml", "docker-compose.yaml", "dockerfile"}
            or normalized.startswith((".github/", ".git/"))
            or "/.git/" in normalized
        )

    def evaluate_file_change(self, change: CodeChangeItem) -> Tuple[PermissionLevel, str]:
        if self._emergency_stop_triggered:
            return PermissionLevel.EXPLICIT_APPROVAL_REQUIRED, "Emergency stop is active"

        # Explicit approval required for file deletion
        if change.operation == ChangeOperation.DELETE:
            return (
                PermissionLevel.EXPLICIT_APPROVAL_REQUIRED,
                f"Deleting workspace file '{change.path}' requires explicit user approval",
            )

        # Explicit approval required if modifying sensitive config files directly
        for candidate in (change.path, change.destination_path):
            if candidate and self.is_sensitive_path(candidate):
                return (
                    PermissionLevel.EXPLICIT_APPROVAL_REQUIRED,
                    f"Modifying sensitive configuration '{candidate}' requires explicit user approval",
                )

        return PermissionLevel.TASK_ALLOWED, "File operation permitted within approved task"

    def evaluate_command(self, command: str) -> Tuple[PermissionLevel, str]:
        if self._emergency_stop_triggered:
            return PermissionLevel.EXPLICIT_APPROVAL_REQUIRED, "Emergency stop is active"

        try:
            tokens = [t.strip("\"'").lower() for t in shlex.split(command, posix=False)]
        except ValueError:
            return PermissionLevel.EXPLICIT_APPROVAL_REQUIRED, f"Command could not be parsed: '{command}'"
        if not tokens:
            return PermissionLevel.EXPLICIT_APPROVAL_REQUIRED, "Command is empty"

        exe = tokens[0].replace("\\", "/").rsplit("/", 1)[-1]
        if exe.endswith(".exe"):
            exe = exe[:-4]
        rest = tokens[1:]

        # Dependency installation commands require approval (`git add` is NOT one of them)
        package_verbs = {"install", "i", "add", "remove", "uninstall", "update", "upgrade", "ci", "get", "sync"}
        runs_pip = exe in ("pip", "uv") or (exe in ("python", "py") and "pip" in rest[:2])
        if (exe in ("npm", "yarn", "pnpm", "cargo", "dotnet", "go") or runs_pip) and package_verbs & set(rest[:3]):
            return (
                PermissionLevel.EXPLICIT_APPROVAL_REQUIRED,
                f"Package or dependency installation command requires explicit user approval: '{command}'",
            )

        if exe == "git" and rest:
            sub = rest[0]
            flags = set(rest[1:])
            destructive = (
                sub in ("push", "clean", "rm")
                or (sub == "reset" and "--hard" in flags)
                or (sub == "checkout" and flags & {"-f", "--force"})
                or (sub == "branch" and flags & {"-d", "--delete", "-D"})
                or (sub == "stash" and flags & {"drop", "clear"})
            )
            if destructive:
                return (
                    PermissionLevel.EXPLICIT_APPROVAL_REQUIRED,
                    f"Remote or destructive Git operation requires explicit user approval: '{command}'",
                )

        return PermissionLevel.TASK_ALLOWED, "Command permitted within approved task"


permission_policy = PermissionPolicy()

