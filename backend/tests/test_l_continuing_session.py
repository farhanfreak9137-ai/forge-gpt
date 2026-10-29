import pytest
from pathlib import Path
from sqlalchemy import select
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import Project, ProjectSession, Task
from app.core.orchestrator.orchestrator import orchestrator
from app.core.state_machine.states import TaskState
from app.workspace.git.git_manager import GitManager
from app.ai.protocol.protocol import AIResponseEnvelope, ResponseType, ChangeOperation


@pytest.mark.asyncio
async def test_l_continuing_development_session(temp_workspace: Path):
    """
    Test L: Continuing Development Session
    1. Complete an initial task.
    2. Add follow-up request to the same project session.
    3. Modify project and verify.
    4. Confirm both tasks remain linked and accessible in the session.
    """
    ws = temp_workspace / "session_app"
    ws.mkdir()
    git_mgr = GitManager(str(ws))
    await git_mgr.init_repo()

    async with AsyncSessionLocal() as session:
        proj = Project(name="Session Project", path=str(ws))
        session.add(proj)
        await session.commit()
        await session.refresh(proj)

        proj_session = ProjectSession(project_id=proj.id, title="Multi-Task Session 1")
        session.add(proj_session)
        await session.commit()
        await session.refresh(proj_session)
        session_id = proj_session.id

        # Task 1: Create calc module
        task1 = Task(
            project_id=proj.id,
            session_id=session_id,
            title="Task 1: Create calc",
            description="Create calc.py with addition",
            state="CREATED",
        )
        session.add(task1)
        await session.commit()
        await session.refresh(task1)
        task1_id = task1.id

    # Run Task 1
    await orchestrator.run_task(task1_id, connector_name="mock")

    async with AsyncSessionLocal() as session:
        db_task1 = await session.get(Task, task1_id)
        assert db_task1.state == TaskState.COMPLETED.value

    # Now add Task 2 in the SAME project session
    async with AsyncSessionLocal() as session:
        task2 = Task(
            project_id=proj.id,
            session_id=session_id,
            title="Task 2: Add multiplication",
            description="Add multiply function to calc.py",
            state="CREATED",
        )
        session.add(task2)
        await session.commit()
        await session.refresh(task2)
        task2_id = task2.id

    mock_adapter = orchestrator.get_connector("mock")
    # Queue Task 2 plan
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task2_id,
        request_id="t2-plan",
        response_type=ResponseType.PLAN,
        payload={
            "summary": "Plan to add multiplication",
            "steps": [{"step_number": 1, "title": "Update calc.py", "description": "Add multiply", "expected_files": ["calc.py"], "dependencies": []}],
            "acceptance_criteria": ["calc.py contains multiply"]
        }
    ))
    # Queue Task 2 changes
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task2_id,
        request_id="t2-code",
        response_type=ResponseType.PROPOSE_CHANGES,
        payload={
            "summary": "Add multiply function to calc.py",
            "changes": [
                {
                    "operation": ChangeOperation.REPLACE.value,
                    "path": "calc.py",
                    "content": "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n",
                    "explanation": "Added multiply function",
                },
                {
                    "operation": ChangeOperation.REPLACE.value,
                    "path": "test_calc.py",
                    "content": "from calc import add, multiply\n\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_multiply():\n    assert multiply(2, 4) == 8\n",
                    "explanation": "Added test_multiply",
                }
            ]
        }
    ))

    # Run Task 2
    await orchestrator.run_task(task2_id, connector_name="mock")

    # Verify both tasks completed and are in the same session
    async with AsyncSessionLocal() as session:
        db_task2 = await session.get(Task, task2_id)
        assert db_task2.state == TaskState.COMPLETED.value

        query = select(Task).where(Task.session_id == session_id).order_by(Task.created_at.asc())
        result = await session.execute(query)
        session_tasks = result.scalars().all()

        assert len(session_tasks) == 2
        assert session_tasks[0].id == task1_id
        assert session_tasks[1].id == task2_id
        assert all(t.state == TaskState.COMPLETED.value for t in session_tasks)

    # Verify disk content includes both functions
    calc_content = (ws / "calc.py").read_text(encoding="utf-8")
    assert "def add" in calc_content
    assert "def multiply" in calc_content
