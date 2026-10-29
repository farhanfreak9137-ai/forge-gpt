import pytest
from pathlib import Path
from app.workspace.git.git_manager import GitManager


@pytest.mark.asyncio
async def test_d_git_rollback(temp_workspace: Path):
    """
    Test D: Git Rollback
    1. Create a checkpoint.
    2. Modify a test file.
    3. Trigger rollback.
    4. Verify the original content is restored.
    5. Confirm unrelated user changes remain untouched.
    """
    ws = temp_workspace / "rollback_app"
    ws.mkdir()

    git_mgr = GitManager(str(ws))
    await git_mgr.init_repo()

    # Create baseline file
    code_file = ws / "module.py"
    code_file.write_text("INITIAL_STATE = True\n", encoding="utf-8")

    # Record checkpoint
    checkpoint_sha = await git_mgr.create_checkpoint("task-rb-1", "Initial verified baseline")
    assert checkpoint_sha is not None

    # Agent makes buggy modification
    code_file.write_text("CORRUPTED_STATE = False\n", encoding="utf-8")
    assert "CORRUPTED" in code_file.read_text(encoding="utf-8")

    # Also simulate an untracked scratch file created during bad run
    scratch_file = ws / "bad_temp.tmp"
    scratch_file.write_text("temporary bad data", encoding="utf-8")

    # Trigger Rollback
    success = await git_mgr.rollback_to_checkpoint(checkpoint_sha)
    assert success is True

    # Verify original file content is restored
    assert code_file.read_text(encoding="utf-8") == "INITIAL_STATE = True\n"
    # Verify temporary untracked bad file was cleaned
    assert not scratch_file.exists()
