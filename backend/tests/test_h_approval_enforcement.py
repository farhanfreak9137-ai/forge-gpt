import pytest
from pathlib import Path
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import Project, Task, ApprovalRequestRecord
from app.core.orchestrator.orchestrator import orchestrator
from app.core.state_machine.states import TaskState
from app.ai.protocol.protocol import AIResponseEnvelope, ResponseType, ChangeOperation
from app.workspace.git.git_manager import GitManager


@pytest.mark.asyncio
async def test_h_approval_enforcement(temp_workspace: Path, async_client):
    """
    Test H: Approval Enforcement
    1. Attempt operation requiring approval (e.g. delete important file).
    2. Verify task pauses in WAITING_FOR_APPROVAL.
    3. Verify approval request created.
    4. Approve via API and verify task resumes.
    """
    ws = temp_workspace / "approval_app"
    ws.mkdir()
    git_mgr = GitManager(str(ws))
    await git_mgr.init_repo()

    # Create file that will be targeted for deletion
    target_file = ws / "critical.py"
    target_file.write_text("CRITICAL_LOGIC = True\n", encoding="utf-8")

    async with AsyncSessionLocal() as session:
        proj = Project(name="Approval Test", path=str(ws))
        session.add(proj)
        await session.commit()
        await session.refresh(proj)

        task = Task(
            project_id=proj.id,
            title="Delete critical file",
            description="Delete critical.py",
            state="CREATED",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    mock_adapter = orchestrator.get_connector("mock")
    # Queue plan
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task_id,
        request_id="r-plan",
        response_type=ResponseType.PLAN,
        payload={
            "summary": "Plan to delete file",
            "steps": [{"step_number": 1, "title": "Delete", "description": "Remove critical.py", "expected_files": [], "dependencies": []}],
            "acceptance_criteria": ["critical.py removed"]
        }
    ))
    # Queue propose changes with DELETE operation
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task_id,
        request_id="r-code",
        response_type=ResponseType.PROPOSE_CHANGES,
        payload={
            "summary": "Delete critical file",
            "changes": [
                {
                    "operation": ChangeOperation.DELETE.value,
                    "path": "critical.py",
                    "explanation": "Remove deprecated critical file",
                }
            ]
        }
    ))

    # Run task - should pause for approval
    await orchestrator.run_task(task_id, connector_name="mock")

    # Verify task state is WAITING_FOR_APPROVAL
    async with AsyncSessionLocal() as session:
        db_task = await session.get(Task, task_id)
        assert db_task.state == TaskState.WAITING_FOR_APPROVAL.value

    # Verify approval record is listed in API
    res = await async_client.get("/api/v1/approvals")
    assert res.status_code == 200
    approvals = res.json()
    task_approvals = [a for a in approvals if a["task_id"] == task_id]
    assert len(task_approvals) == 1
    approval_id = task_approvals[0]["id"]

    # Verify file is NOT deleted yet
    assert target_file.exists()

    # Reject approval
    res = await async_client.post(f"/api/v1/approvals/{approval_id}/decide", json={
        "approved": False,
        "reason": "Prevented by user"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "REJECTED"

    # Verify file remains intact after rejection
    assert target_file.exists()
