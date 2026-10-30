import pytest
from pydantic import ValidationError
from app.ai.protocol.protocol import AIResponseEnvelope, ResponseType, ChangeOperation, CodeChangeItem
from app.workspace.files.file_manager import SafeFileManager
from app.workspace.patches.patcher import PatchApplicator


def test_f_invalid_ai_response_protocol_validation():
    """
    Test F: Invalid AI Response
    Verify Pydantic rejection of:
    - Unsupported actions
    - Invalid file paths (path traversal)
    - Stale file hashes
    - Malformed envelope structure
    """
    # 1. Invalid relative path with path traversal
    with pytest.raises(ValidationError):
        CodeChangeItem(
            operation=ChangeOperation.CREATE,
            path="../../etc/shadow",
            content="malicious",
            explanation="attempt traversal",
        )

    # 2. Absolute path rejection
    with pytest.raises(ValidationError):
        CodeChangeItem(
            operation=ChangeOperation.CREATE,
            path="C:/Windows/System32/calc.exe",
            content="malicious",
            explanation="attempt absolute write",
        )

    # 3. Missing required content for CREATE operation
    with pytest.raises(ValidationError):
        CodeChangeItem(
            operation=ChangeOperation.CREATE,
            path="safe.py",
            content=None,
            explanation="missing content",
        )

    # 4. Invalid protocol version rejection
    with pytest.raises(ValidationError):
        AIResponseEnvelope(
            protocol_version="unsupported.v99",
            task_id="t1",
            request_id="r1",
            response_type=ResponseType.PLAN,
            payload={},
        )


def test_f_stale_hash_rejection(tmp_path):
    """Verify patch rejection when expected file hash does not match current state."""
    fm = SafeFileManager(str(tmp_path))
    fm.write_file_atomic("tracked.py", "version_1 = True\n")
    patcher = PatchApplicator(fm)

    stale_change = CodeChangeItem(
        operation=ChangeOperation.REPLACE,
        path="tracked.py",
        expected_hash="deadbeef1234567890abcdef",  # Wrong hash
        content="version_2 = True\n",
        explanation="Stale replace attempt",
    )

    success, message, _ = patcher.apply_change(stale_change)
    assert success is False
    assert "Stale file error" in message

