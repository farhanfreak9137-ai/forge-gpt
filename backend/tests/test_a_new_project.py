import pytest
from pathlib import Path
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import Project, Task
from app.core.orchestrator.orchestrator import orchestrator
from app.core.state_machine.states import TaskState
from app.workspace.git.git_manager import GitManager


@pytest.mark.asyncio
async def test_a_new_project_creation(temp_workspace: Path):
    """
    Test A: New Project Creation
    1. Create a new test project.
    2. Generate a simple working application.
    3. Write required project files.
    4. Initialize Git.
    5. Run its tests.
    6. Verify the expected files exist.
    7. Verify the task shows completed status.
    """
    project_path = temp_workspace / "new_app"
    project_path.mkdir()

    # 1. Register new project
    async with AsyncSessionLocal() as session:
        proj = Project(
            name="New Calculator App",
            path=str(project_path),
            description="A simple math calculator application",
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        project_id = proj.id

        # Create task
        task = Task(
            project_id=project_id,
            title="Create calculator app",
            description="Implement calc.py and unit tests in test_calc.py",
            state="CREATED",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = task.id

    # 2. Run orchestrator
    await orchestrator.run_task(task_id, connector_name="mock")

    # 3. Verify task state in database
    async with AsyncSessionLocal() as session:
        completed_task = await session.get(Task, task_id)
        assert completed_task is not None
        assert completed_task.state == TaskState.COMPLETED.value
        assert completed_task.result_summary is not None

    # 4. Verify generated files exist
    assert (project_path / "calc.py").exists(), "calc.py was not created"
    assert (project_path / "test_calc.py").exists(), "test_calc.py was not created"

    # 5. Verify Git initialization and checkpoints
    git_mgr = GitManager(str(project_path))
    assert git_mgr.is_git_repo(), "Git repository was not initialized"
    history = await git_mgr.get_checkpoint_history()
    assert len(history) > 0, "No git checkpoints recorded"
