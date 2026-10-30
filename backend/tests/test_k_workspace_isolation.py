import os
import pytest
from pathlib import Path
from app.workspace.files.file_manager import SafeFileManager
from app.execution.commands.runner import SafeCommandRunner


def test_k_workspace_path_traversal_blocked(temp_workspace: Path):
    """
    Test K: Workspace Isolation - Path Traversal
    Confirm attempts to access or write outside workspace boundaries are blocked.
    """
    ws = temp_workspace / "isolated_ws"
    ws.mkdir()
    fm = SafeFileManager(str(ws))

    # 1. Directory traversal attempt
    with pytest.raises(PermissionError):
        fm.resolve_safe_path("../outside.txt")

    # 2. Deep traversal attempt
    with pytest.raises(PermissionError):
        fm.resolve_safe_path("sub/../../escaped.txt")

    # 3. Absolute path attempt
    with pytest.raises(PermissionError):
        fm.resolve_safe_path("C:/escaped_root.txt")


def test_k_command_execution_isolation(temp_workspace: Path):
    """
    Test K: Workspace Isolation - Command Runner Allowlist & Operator Injection
    Confirm unapproved commands and shell chaining attempts are rejected.
    """
    ws = temp_workspace / "isolated_ws"
    ws.mkdir()
    runner = SafeCommandRunner(str(ws))

    # 1. Disallowed command
    allowed, reason = runner.is_command_allowed("rmdir /s /q C:\\")
    assert allowed is False
    assert "not in the allowed command allowlist" in reason

    # 2. Shell chaining operator injection
    allowed, reason = runner.is_command_allowed("python main.py && del *")
    assert allowed is False
    assert "Shell operator '&&' is prohibited" in reason

    # 3. Semicolon chaining
    allowed, reason = runner.is_command_allowed("python -v ; whoami")
    assert allowed is False
    assert "Shell operator" in reason

    # 4. Allowed command
    allowed, _ = runner.is_command_allowed("python --version")
    assert allowed is True

