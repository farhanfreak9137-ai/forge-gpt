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
        sensitive_files = {".env", "docker-compose.yml", "Dockerfile"}
        if change.path in sensitive_files:
            return (
                PermissionLevel.EXPLICIT_APPROVAL_REQUIRED,
                f"Modifying sensitive configuration '{change.path}' requires explicit user approval",
            )

        return PermissionLevel.TASK_ALLOWED, "File operation permitted within approved task"

    def evaluate_command(self, command: str) -> Tuple[PermissionLevel, str]:
        if self._emergency_stop_triggered:
            return PermissionLevel.EXPLICIT_APPROVAL_REQUIRED, "Emergency stop is active"

        cmd_lower = command.lower()

        # Dependency installation commands require approval
        if any(kw in cmd_lower for kw in ["install", "add", "pip install", "npm install", "yarn add"]):
            return (
                PermissionLevel.EXPLICIT_APPROVAL_REQUIRED,
                f"Package or dependency installation command requires explicit user approval: '{command}'",
            )

        # Destructive Git commands require approval
        if "git push" in cmd_lower or "git reset --hard" in cmd_lower:
            return (
                PermissionLevel.EXPLICIT_APPROVAL_REQUIRED,
                f"Remote or destructive Git operation requires explicit user approval: '{command}'",
            )

        return PermissionLevel.TASK_ALLOWED, "Command permitted within approved task"


permission_policy = PermissionPolicy()
