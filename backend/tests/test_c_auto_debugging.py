import pytest
from pathlib import Path
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.memory.database import AsyncSessionLocal
from app.memory.models.models import Project, Task
from app.core.orchestrator.orchestrator import orchestrator
from app.core.state_machine.states import TaskState
from app.workspace.git.git_manager import GitManager
from app.ai.protocol.protocol import AIResponseEnvelope, ResponseType, ChangeOperation


@pytest.mark.asyncio
async def test_c_automatic_debugging(temp_workspace: Path):
    """
    Test C: Automatic Debugging
    1. Create a sample project with an intentional, harmless test failure.
    2. Run the failing test.
    3. Capture the error.
    4. Send the error to the mock AI.
    5. Receive a corrected patch.
    6. Apply the correction.
    7. Rerun the test.
    8. Verify success.
    Confirm the task history records the entire repair sequence.
    """
    project_path = temp_workspace / "debug_app"
    project_path.mkdir()

    # Pre-populate project with a failing test
    calc_file = project_path / "calc.py"
    calc_file.write_text("def add(a, b):\n    return a - b  # Intentional bug!\n", encoding="utf-8")

    test_file = project_path / "test_calc.py"
    test_file.write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")

    git_mgr = GitManager(str(project_path))
    await git_mgr.init_repo()

    # Register project & task
    async with AsyncSessionLocal() as session:
        proj = Project(
            name="Debug Test Project",
            path=str(project_path),
            description="Project with intentional bug",
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)

        task = Task(
            project_id=proj.id,
            title="Fix calculator addition bug",
            description="Repair addition implementation so test_add passes",
            state="CREATED",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    mock_adapter = orchestrator.get_connector("mock")
    # Queue initial plan
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task_id,
        request_id="plan-req",
        response_type=ResponseType.PLAN,
        payload={
            "summary": "Plan to fix calc",
            "steps": [{"step_number": 1, "title": "Run tests and repair", "description": "Fix calc.py", "expected_files": ["calc.py"], "dependencies": []}],
            "acceptance_criteria": ["All tests pass"]
        }
    ))
    # Queue initial propose changes (still buggy or no-op)
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task_id,
        request_id="code-req",
        response_type=ResponseType.PROPOSE_CHANGES,
        payload={
            "summary": "Initial attempt",
            "changes": [
                {
                    "operation": ChangeOperation.REPLACE.value,
                    "path": "calc.py",
                    "content": "def add(a, b):\n    return a - b  # Still buggy\n",
                    "explanation": "Initial attempt",
                }
            ]
        }
    ))
    # Queue repair proposal that fixes the bug!
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task_id,
        request_id="repair-req-1",
        response_type=ResponseType.PROPOSE_CHANGES,
        payload={
            "summary": "Fix add function to use plus instead of minus",
            "changes": [
                {
                    "operation": ChangeOperation.REPLACE.value,
                    "path": "calc.py",
                    "content": "def add(a, b):\n    return a + b  # Fixed!\n",
                    "explanation": "Corrected return operator from minus to plus",
                }
            ]
        }
    ))

    # Run orchestrator
    await orchestrator.run_task(task_id, connector_name="mock")

    # Verify task state
    async with AsyncSessionLocal() as session:
        query = select(Task).where(Task.id == task_id).options(
            selectinload(Task.test_results),
            selectinload(Task.proposed_changes),
        )
        result = await session.execute(query)
        db_task = result.scalar_one()

        assert db_task.state == TaskState.COMPLETED.value
        # Repair attempt was triggered and recorded!
        assert db_task.repair_attempts >= 1
        assert len(db_task.test_results) >= 2  # First failed test, then passed test
        # Verify first test failed, second passed
        assert db_task.test_results[0].passed is False
        assert db_task.test_results[1].passed is True

    # Verify actual file on disk is fixed
    assert "return a + b" in (project_path / "calc.py").read_text(encoding="utf-8")

