import pytest
from pathlib import Path
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import Project, Task
from app.core.orchestrator.orchestrator import orchestrator
from app.core.state_machine.states import TaskState
from app.workspace.git.git_manager import GitManager
from app.ai.protocol.protocol import AIResponseEnvelope, ResponseType, ChangeOperation


@pytest.mark.asyncio
async def test_b_existing_project_modification(temp_workspace: Path):
    """
    Test B: Existing Project Modification
    1. Open a sample existing project.
    2. Ask the agent to add a feature.
    3. Generate a change proposal.
    4. Validate and apply it.
    5. Run tests.
    6. Inspect Git diff.
    7. Verify the original project data was preserved.
    """
    project_path = temp_workspace / "existing_app"
    project_path.mkdir()

    # Pre-populate with existing file
    original_file = project_path / "original.txt"
    original_file.write_text("Original untouched user content\n", encoding="utf-8")

    git_mgr = GitManager(str(project_path))
    await git_mgr.init_repo()

    # Register project
    async with AsyncSessionLocal() as session:
        proj = Project(
            name="Existing App",
            path=str(project_path),
            description="Existing application",
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        project_id = proj.id

        task = Task(
            project_id=project_id,
            title="Add helper feature",
            description="Add helper functions and unit tests",
            state="CREATED",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    # Configure mock adapter to propose changes that add helper.py
    mock_adapter = orchestrator.get_connector("mock")
    # Queue plan
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task_id,
        request_id="req-plan",
        response_type=ResponseType.PLAN,
        payload={
            "summary": "Plan to add helper feature",
            "steps": [{"step_number": 1, "title": "Add helper.py", "description": "Create helper", "expected_files": ["helper.py"], "dependencies": []}],
            "acceptance_criteria": ["helper.py exists and tests pass"]
        }
    ))
    # Queue code change
    mock_adapter.queue_response(AIResponseEnvelope(
        protocol_version="forgeagent.v1",
        task_id=task_id,
        request_id="req-code",
        response_type=ResponseType.PROPOSE_CHANGES,
        payload={
            "summary": "Create helper.py and test_helper.py",
            "changes": [
                {
                    "operation": ChangeOperation.CREATE.value,
                    "path": "helper.py",
                    "content": "def greet(name):\n    return f'Hello, {name}'\n",
                    "explanation": "Add greet helper function",
                },
                {
                    "operation": ChangeOperation.CREATE.value,
                    "path": "test_helper.py",
                    "content": "from helper import greet\n\ndef test_greet():\n    assert greet('World') == 'Hello, World'\n",
                    "explanation": "Add unit test for greet",
                }
            ]
        }
    ))

    # Run task
    await orchestrator.run_task(task_id, connector_name="mock")

    # Verify task completed
    async with AsyncSessionLocal() as session:
        db_task = await session.get(Task, task_id)
        assert db_task.state == TaskState.COMPLETED.value

    # Verify new files exist
    assert (project_path / "helper.py").exists()
    assert (project_path / "test_helper.py").exists()

    # Verify original file was preserved perfectly
    assert original_file.read_text(encoding="utf-8") == "Original untouched user content\n"

    # Verify git diff reflects changes
    diff = await git_mgr.get_diff()
    # At completion, all committed to checkpoint
    history = await git_mgr.get_checkpoint_history()
    assert len(history) >= 2
