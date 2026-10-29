import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.memory.database import get_db
from app.memory.models.models import (
    Task,
    Project,
    TaskStep,
    ProposedChangeRecord,
    ExecutionRecord,
    TestResultRecord,
    ApprovalRequestRecord,
    CheckpointRecord,
)
from app.schemas.schemas import (
    TaskCreate,
    TaskResponse,
    TaskDetailResponse,
    TaskStepResponse,
    ProposedChangeResponse,
    ExecutionResponse,
    TestResultResponse,
    ApprovalResponse,
    CheckpointResponse,
    RollbackRequest,
)
from app.core.orchestrator.orchestrator import orchestrator
from app.workspace.git.git_manager import GitManager

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(
        project_id=data.project_id,
        session_id=data.session_id,
        title=data.title,
        description=data.description,
        max_repair_attempts=data.max_repair_attempts or 4,
        state="CREATED",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Automatically start task execution asynchronously
    asyncio.create_task(orchestrator.run_task(task.id, connector_name=data.connector_name))

    return task


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    project_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Task).order_by(Task.created_at.desc())
    if project_id:
        query = query.where(Task.project_id == project_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    query = (
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.steps),
            selectinload(Task.proposed_changes),
            selectinload(Task.executions),
            selectinload(Task.test_results),
            selectinload(Task.approvals),
            selectinload(Task.checkpoints),
        )
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskDetailResponse(
        id=task.id,
        project_id=task.project_id,
        session_id=task.session_id,
        title=task.title,
        description=task.description,
        state=task.state,
        current_step_index=task.current_step_index,
        repair_attempts=task.repair_attempts,
        max_repair_attempts=task.max_repair_attempts,
        error_message=task.error_message,
        result_summary=task.result_summary,
        created_at=task.created_at,
        updated_at=task.updated_at,
        steps=[
            TaskStepResponse(
                id=s.id,
                step_index=s.step_index,
                step_type=s.step_type,
                title=s.title,
                description=s.description,
                status=s.status,
                created_at=s.created_at,
                completed_at=s.completed_at,
            )
            for s in task.steps
        ],
        proposed_changes=[
            ProposedChangeResponse(
                id=c.id,
                file_path=c.file_path,
                operation=c.operation,
                proposed_content=c.proposed_content,
                patch_diff=c.patch_diff,
                explanation=c.explanation,
                status=c.status,
                created_at=c.created_at,
            )
            for c in task.proposed_changes
        ],
        executions=[
            ExecutionResponse(
                id=e.id,
                command=e.command,
                working_dir=e.working_dir,
                exit_code=e.exit_code,
                stdout=e.stdout,
                stderr=e.stderr,
                duration_ms=e.duration_ms,
                status=e.status,
                created_at=e.created_at,
            )
            for e in task.executions
        ],
        test_results=[
            TestResultResponse(
                id=t.id,
                test_command=t.test_command,
                passed=t.passed,
                total_tests=t.total_tests,
                failed_tests=t.failed_tests,
                error_details=t.error_details,
                created_at=t.created_at,
            )
            for t in task.test_results
        ],
        approvals=[
            ApprovalResponse(
                id=a.id,
                task_id=a.task_id,
                action_type=a.action_type,
                description=a.description,
                details=a.details_json or {},
                status=a.status,
                decision_reason=a.decision_reason,
                requested_at=a.requested_at,
                decided_at=a.decided_at,
            )
            for a in task.approvals
        ],
        checkpoints=[
            CheckpointResponse(
                id=cp.id,
                git_ref=cp.git_ref,
                description=cp.description,
                files_affected=cp.files_affected_json or [],
                created_at=cp.created_at,
            )
            for cp in task.checkpoints
        ],
    )


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    await orchestrator.pause_task(task_id)
    return {"status": "PAUSED", "task_id": task_id}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    await orchestrator.resume_task(task_id)
    return {"status": "RESUMED", "task_id": task_id}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    await orchestrator.cancel_task(task_id)
    return {"status": "CANCELLED", "task_id": task_id}


@router.post("/{task_id}/rollback")
async def rollback_task(
    task_id: str,
    data: RollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    project = await db.get(Project, task.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_mgr = GitManager(project.path)
    success = await git_mgr.rollback_to_checkpoint(data.checkpoint_ref)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to rollback git state to checkpoint")

    return {"status": "ROLLED_BACK", "checkpoint_ref": data.checkpoint_ref}
