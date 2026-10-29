from typing import List, Optional
from fastapi import APIRouter, Query
from app.events.event_bus import event_bus, ActivityEvent

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=List[ActivityEvent])
async def get_activity_events(
    task_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    since_sequence: Optional[int] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    return await event_bus.get_events(
        task_id=task_id,
        project_id=project_id,
        since_sequence=since_sequence,
        limit=limit,
    )
