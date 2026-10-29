import logging
from typing import List, Dict, Any
from sqlalchemy import select
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import Task, Project, CheckpointRecord
from app.core.state_machine.states import TaskState
from app.events.event_bus import event_bus
from app.workspace.git.git_manager import GitManager

logger = logging.getLogger("forgeagent.recovery")


class CrashRecoveryManager:
    """Detects and reconciles unfinished tasks after an unexpected server restart."""

    async def scan_and_recover(self) -> List[Dict[str, Any]]:
        recovered = []
        async with AsyncSessionLocal() as session:
            # Query tasks that were left in transient non-terminal states
            transient_states = [
                TaskState.SCANNING.value,
                TaskState.PLANNING.value,
                TaskState.WAITING_FOR_AI.value,
                TaskState.PARSING.value,
                TaskState.VALIDATING.value,
                TaskState.APPLYING.value,
                TaskState.TESTING.value,
                TaskState.REPAIRING.value,
                TaskState.VERIFYING.value,
            ]
            query = select(Task).where(Task.state.in_(transient_states))
            result = await session.execute(query)
            unfinished_tasks = result.scalars().all()

            for t in unfinished_tasks:
                project = await session.get(Project, t.project_id)
                workspace_path = project.path if project else None

                # Reconcile Git state
                reconciled_clean = True
                if workspace_path:
                    git_mgr = GitManager(workspace_path)
                    status = await git_mgr.get_status()
                    reconciled_clean = status.get("clean", True)

                # If the task was interrupted mid-applying or uncertain, mark RECOVERY_REQUIRED
                old_state = t.state
                if old_state in (TaskState.APPLYING.value, TaskState.REPAIRING.value) and not reconciled_clean:
                    t.state = TaskState.RECOVERY_REQUIRED.value
                    t.error_message = "Task interrupted during uncommitted file changes. Review or rollback needed."
                else:
                    # Safe to pause so user can resume
                    t.state = TaskState.PAUSED.value
                    t.error_message = "Task paused automatically following server restart."

                await session.commit()
                recovered.append({
                    "task_id": t.id,
                    "title": t.title,
                    "old_state": old_state,
                    "new_state": t.state,
                })

                await event_bus.publish(
                    "TASK_RECOVERED",
                    f"Recovered unfinished task {t.id} from {old_state} to {t.state}",
                    task_id=t.id,
                    project_id=t.project_id,
                    severity="WARNING",
                    payload={"old_state": old_state, "new_state": t.state},
                )

        logger.info(f"Crash recovery completed: reconciled {len(recovered)} tasks.")
        return recovered


crash_recovery_manager = CrashRecoveryManager()
