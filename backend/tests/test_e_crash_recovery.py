import pytest
from pathlib import Path
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import Project, Task
from app.core.state_machine.states import TaskState
from app.core.recovery.recovery import crash_recovery_manager
from app.workspace.git.git_manager import GitManager


@pytest.mark.asyncio
async def test_e_crash_recovery(temp_workspace: Path):
    """
    Test E: Agent Crash Recovery
    1. Start a multi-step task.
    2. Persist an intermediate checkpoint.
    3. Simulate termination of the agent process during execution.
    4. Restart backend and run recovery scan.
    5. Load unfinished task and reconcile state.
    6. Confirm safe status allows safe user review/resumption.
    """
    ws = temp_workspace / "crash_app"
    ws.mkdir()
    git_mgr = GitManager(str(ws))
    await git_mgr.init_repo()

    async with AsyncSessionLocal() as session:
        proj = Project(
            name="Crash Recovery Project",
            path=str(ws),
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)

        # Simulate task interrupted while in transient state "TESTING"
        task = Task(
            project_id=proj.id,
            title="Interrupted Task",
            description="Task interrupted by unexpected server restart",
            state=TaskState.TESTING.value,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    # Execute Crash Recovery scan
    recovered = await crash_recovery_manager.scan_and_recover()
    assert any(r["task_id"] == task_id for r in recovered)

    # Verify task was reconciled from transient state to PAUSED
    async with AsyncSessionLocal() as session:
        reconciled_task = await session.get(Task, task_id)
        assert reconciled_task.state == TaskState.PAUSED.value
        assert "server restart" in reconciled_task.error_message

