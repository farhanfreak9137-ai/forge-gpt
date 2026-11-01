import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai.protocol.protocol import AIResponseEnvelope, ChangeOperation, ResponseType
from app.core.orchestrator.orchestrator import orchestrator
from app.core.state_machine.states import TaskState
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import AIRequestRecord, ApprovalRequestRecord, Project, Task
from app.utils.clock import utcnow
from app.workspace.git.git_manager import GitManager

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}

PLAN = {
    "summary": "plan",
    "steps": [{"step_number": 1, "title": "Do it", "description": "Do the thing", "expected_files": [], "dependencies": []}],
    "acceptance_criteria": ["done"],
}
GOOD_CHANGES = {
    "summary": "add calculator",
    "changes": [
        {"operation": "create", "path": "calc.py", "content": "def add(a, b):\n    return a + b\n", "explanation": "add"},
        {"operation": "create", "path": "test_calc.py", "content": "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", "explanation": "test"},
    ],
}
MISSING_PATH_CHANGES = {
    "summary": "broken",
    "changes": [{"operation": "create", "path": None, "content": "x = 1\n", "explanation": "no path given"}],
}


def env(response_type: ResponseType, payload: dict) -> AIResponseEnvelope:
    return AIResponseEnvelope(task_id="t", request_id="r", response_type=response_type, payload=payload)


@pytest.fixture
def mock_ai():
    adapter = orchestrator.get_connector("mock")
    adapter.clear_queue()
    adapter.call_history.clear()
    yield adapter
    adapter.clear_queue()


async def make_task(workspace: Path, title: str = "task") -> tuple:
    await GitManager(str(workspace)).init_repo()
    async with AsyncSessionLocal() as session:
        project = Project(name=f"proj-{title}", path=str(workspace))
        session.add(project)
        await session.commit()
        await session.refresh(project)
        task = Task(project_id=project.id, title=title, description=title, state="CREATED")
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return project.id, task.id


async def get_task(task_id: str) -> Task:
    async with AsyncSessionLocal() as session:
        return await session.get(Task, task_id)


async def wait_for(task_id: str, states, timeout: float = 20.0) -> Task:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        task = await get_task(task_id)
        if task.state in states:
            return task
        assert asyncio.get_event_loop().time() < deadline, f"task stuck in {task.state}"
        await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_missing_path_is_sent_back_to_the_ai_for_correction(temp_workspace: Path, mock_ai):
    _, task_id = await make_task(temp_workspace, "retry-missing-path")
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))
    mock_ai.queue_response(env(ResponseType.PROPOSE_CHANGES, MISSING_PATH_CHANGES))
    mock_ai.queue_response(env(ResponseType.PROPOSE_CHANGES, GOOD_CHANGES))

    await orchestrator.run_task(task_id, connector_name="mock")

    task = await get_task(task_id)
    assert task.state == "COMPLETED", task.error_message
    assert (temp_workspace / "calc.py").exists()
    correction = mock_ai.call_history[2]["prompt"]
    assert "rejected by protocol validation" in correction and "changes.0.path" in correction

    async with AsyncSessionLocal() as session:
        records = (await session.execute(select(AIRequestRecord).where(AIRequestRecord.task_id == task_id))).scalars().all()
    assert sorted(r.status for r in records) == ["INVALID", "SUCCESS", "SUCCESS"]


@pytest.mark.asyncio
async def test_task_fails_cleanly_after_repeated_invalid_responses(temp_workspace: Path, mock_ai):
    _, task_id = await make_task(temp_workspace, "invalid-forever")
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))
    for _ in range(3):
        mock_ai.queue_response(env(ResponseType.PROPOSE_CHANGES, MISSING_PATH_CHANGES))

    await orchestrator.run_task(task_id, connector_name="mock")

    task = await get_task(task_id)
    assert task.state == "FAILED"
    assert "invalid response 3 times" in task.error_message
    assert not (temp_workspace / "calc.py").exists()


@pytest.mark.asyncio
async def test_unexpected_response_type_is_corrected_not_crashed(temp_workspace: Path, mock_ai):
    _, task_id = await make_task(temp_workspace, "wrong-type")
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))
    mock_ai.queue_response(env(ResponseType.REPORT_ANALYSIS, {"analysis": "I think we should..."}))
    mock_ai.queue_response(env(ResponseType.PROPOSE_CHANGES, GOOD_CHANGES))

    await orchestrator.run_task(task_id, connector_name="mock")

    assert (await get_task(task_id)).state == "COMPLETED"
    assert "expected response_type" in mock_ai.call_history[2]["prompt"]


@pytest.mark.asyncio
async def test_finish_response_completes_without_illegal_transition(temp_workspace: Path, mock_ai):
    """Regression: 'Illegal state transition from VALIDATING to VERIFYING'."""
    _, task_id = await make_task(temp_workspace, "finish-only")
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))
    mock_ai.queue_response(env(ResponseType.FINISH, {"summary": "Nothing to change", "verification_passed": True}))

    await orchestrator.run_task(task_id, connector_name="mock")

    task = await get_task(task_id)
    assert task.state == "COMPLETED", task.error_message


@pytest.mark.asyncio
async def test_approved_file_operation_is_applied_and_task_completes(temp_workspace: Path, mock_ai, async_client):
    """Regression: approving used to restart the task and fail on WAITING_FOR_APPROVAL -> SCANNING."""
    (temp_workspace / "critical.py").write_text("CRITICAL = True\n", encoding="utf-8")
    (temp_workspace / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    _, task_id = await make_task(temp_workspace, "approve-delete")
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))
    mock_ai.queue_response(env(ResponseType.PROPOSE_CHANGES, {
        "summary": "remove file",
        "changes": [{"operation": "delete", "path": "critical.py", "explanation": "deprecated"}],
    }))

    await orchestrator.run_task(task_id, connector_name="mock")
    assert (await get_task(task_id)).state == "WAITING_FOR_APPROVAL"
    assert (temp_workspace / "critical.py").exists()

    pending = [a for a in (await async_client.get("/api/v1/approvals")).json() if a["task_id"] == task_id]
    res = await async_client.post(f"/api/v1/approvals/{pending[0]['id']}/decide", json={"approved": True})
    assert res.status_code == 200

    task = await wait_for(task_id, TERMINAL)
    assert task.state == "COMPLETED", task.error_message
    assert not (temp_workspace / "critical.py").exists()


@pytest.mark.asyncio
async def test_rejected_approval_cancels_the_task(temp_workspace: Path, mock_ai, async_client):
    (temp_workspace / "critical.py").write_text("CRITICAL = True\n", encoding="utf-8")
    _, task_id = await make_task(temp_workspace, "reject-delete")
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))
    mock_ai.queue_response(env(ResponseType.PROPOSE_CHANGES, {
        "summary": "remove file",
        "changes": [{"operation": "delete", "path": "critical.py", "explanation": "deprecated"}],
    }))
    await orchestrator.run_task(task_id, connector_name="mock")

    pending = [a for a in (await async_client.get("/api/v1/approvals")).json() if a["task_id"] == task_id]
    await async_client.post(f"/api/v1/approvals/{pending[0]['id']}/decide", json={"approved": False, "reason": "no"})

    task = await get_task(task_id)
    assert task.state == "CANCELLED" and "Rejected by user" in task.error_message
    assert (temp_workspace / "critical.py").exists()


@pytest.mark.asyncio
async def test_pausing_a_running_task_leaves_it_paused_not_failed(temp_workspace: Path, mock_ai, monkeypatch):
    _, task_id = await make_task(temp_workspace, "pause-me")
    original = mock_ai.send_request

    async def slow_send(*args, **kwargs):
        await asyncio.sleep(0.4)
        return await original(*args, **kwargs)

    monkeypatch.setattr(mock_ai, "send_request", slow_send)
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))

    runner = asyncio.create_task(orchestrator.run_task(task_id, connector_name="mock"))
    await wait_for(task_id, {"WAITING_FOR_AI"})
    await orchestrator.pause_task(task_id)
    await runner

    task = await get_task(task_id)
    assert task.state == "PAUSED" and task.error_message is None
    orchestrator.pause_flags[task_id] = False


@pytest.mark.asyncio
async def test_controls_on_finished_tasks_return_409(temp_workspace: Path, mock_ai, async_client):
    _, task_id = await make_task(temp_workspace, "already-done")
    mock_ai.queue_response(env(ResponseType.PLAN, PLAN))
    mock_ai.queue_response(env(ResponseType.FINISH, {"summary": "ok"}))
    await orchestrator.run_task(task_id, connector_name="mock")

    assert (await async_client.post(f"/api/v1/tasks/{task_id}/cancel")).status_code == 409
    assert (await async_client.post(f"/api/v1/tasks/{task_id}/pause")).status_code == 409


@pytest.mark.asyncio
async def test_stale_task_cleanup_and_delete(temp_workspace: Path, async_client):
    old = utcnow() - timedelta(days=3)
    async with AsyncSessionLocal() as session:
        project = Project(name="cleanup-proj", path=str(temp_workspace))
        session.add(project)
        await session.commit()
        await session.refresh(project)
        ids = {}
        for state in ("PAUSED", "WAITING_FOR_APPROVAL", "COMPLETED", "FAILED"):
            task = Task(project_id=project.id, title=state, description=state, state=state, created_at=old, updated_at=old)
            session.add(task)
            await session.commit()
            await session.refresh(task)
            ids[state] = task.id
        session.add(ApprovalRequestRecord(task_id=ids["WAITING_FOR_APPROVAL"], action_type="FILE_OPERATION", description="x", status="PENDING"))
        fresh = Task(project_id=project.id, title="fresh", description="fresh", state="PAUSED")
        session.add(fresh)
        await session.commit()
        await session.refresh(fresh)
        project_id, fresh_id = project.id, fresh.id

    res = await async_client.post("/api/v1/tasks/cleanup", json={"older_than_hours": 24, "project_id": project_id})
    assert res.status_code == 200 and res.json()["cancelled"] == 2

    assert (await get_task(ids["PAUSED"])).state == "CANCELLED"
    assert (await get_task(ids["WAITING_FOR_APPROVAL"])).state == "CANCELLED"
    assert (await get_task(ids["COMPLETED"])).state == "COMPLETED"   # finished tasks are kept by default
    assert (await get_task(fresh_id)).state == "PAUSED"              # recent tasks are left alone
    async with AsyncSessionLocal() as session:
        approval = (await session.execute(select(ApprovalRequestRecord).where(ApprovalRequestRecord.task_id == ids["WAITING_FOR_APPROVAL"]))).scalars().first()
    assert approval.status == "REJECTED"

    purge = await async_client.post("/api/v1/tasks/cleanup", json={"older_than_hours": 24, "project_id": project_id, "delete_finished": True})
    assert purge.json()["deleted"] == 2  # COMPLETED + FAILED; the just-cancelled tasks are too recent
    assert await get_task(ids["COMPLETED"]) is None

    assert (await async_client.delete(f"/api/v1/tasks/{fresh_id}")).status_code == 409  # still PAUSED
    assert (await async_client.post("/api/v1/tasks/cleanup", json={"states": ["NOPE"]})).status_code == 422
