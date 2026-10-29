from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.memory.database import get_db
from app.memory.models.models import ApprovalRequestRecord, Task
from app.schemas.schemas import ApprovalResponse, ApprovalDecisionRequest
from app.events.event_bus import event_bus
from app.core.orchestrator.orchestrator import orchestrator

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=List[ApprovalResponse])
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApprovalRequestRecord)
        .where(ApprovalRequestRecord.status == "PENDING")
        .order_by(ApprovalRequestRecord.requested_at.desc())
    )
    records = result.scalars().all()
    return [
        ApprovalResponse(
            id=r.id,
            task_id=r.task_id,
            action_type=r.action_type,
            description=r.description,
            details=r.details_json or {},
            status=r.status,
            decision_reason=r.decision_reason,
            requested_at=r.requested_at,
            decided_at=r.decided_at,
        )
        for r in records
    ]


@router.post("/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    data: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(ApprovalRequestRecord, approval_id)
    if not record:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if record.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Approval request already decided: {record.status}")

    record.status = "APPROVED" if data.approved else "REJECTED"
    record.decision_reason = data.reason or ("Approved by user" if data.approved else "Rejected by user")
    record.decided_at = datetime.utcnow()
    await db.commit()
    await db.refresh(record)

    await event_bus.publish(
        event_type="APPROVAL_DECIDED",
        message=f"Approval for task {record.task_id} {record.status.lower()}: {record.description}",
        task_id=record.task_id,
        severity="INFO" if data.approved else "WARNING",
        payload={"approved": data.approved, "reason": record.decision_reason},
    )

    # If approved, resume the task execution
    if data.approved:
        await orchestrator.resume_task(record.task_id)

    return ApprovalResponse(
        id=record.id,
        task_id=record.task_id,
        action_type=record.action_type,
        description=record.description,
        details=record.details_json or {},
        status=record.status,
        decision_reason=record.decision_reason,
        requested_at=record.requested_at,
        decided_at=record.decided_at,
    )
