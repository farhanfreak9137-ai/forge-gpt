import asyncio
from datetime import datetime
from app.utils.clock import utcnow
from typing import Dict, List, Optional, Any, Callable, Awaitable
from pydantic import BaseModel, Field

from app.memory.database import AsyncSessionLocal
from app.memory.models.models import ActivityEventRecord
from sqlalchemy import select


class ActivityEvent(BaseModel):
    id: Optional[str] = None
    sequence_number: Optional[int] = None
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    event_type: str
    severity: str = "INFO"  # INFO, WARNING, ERROR, SUCCESS
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utcnow)


class EventBus:
    def __init__(self):
        self._subscribers: List[Callable[[ActivityEvent], Awaitable[None]]] = []
        self._sequence_counter = 0
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Callable[[ActivityEvent], Awaitable[None]]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ActivityEvent], Awaitable[None]]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def publish(
        self,
        event_type: str,
        message: str,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        severity: str = "INFO",
        payload: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        payload = payload or {}
        async with self._lock:
            self._sequence_counter += 1
            seq = self._sequence_counter

        event = ActivityEvent(
            event_type=event_type,
            sequence_number=seq,
            message=message,
            task_id=task_id,
            project_id=project_id,
            severity=severity,
            payload=payload,
            timestamp=utcnow(),
        )

        # Persist to database
        async with AsyncSessionLocal() as session:
            db_record = ActivityEventRecord(
                task_id=task_id,
                project_id=project_id,
                sequence_number=seq,
                event_type=event_type,
                severity=severity,
                message=message,
                payload_json=payload,
                timestamp=event.timestamp,
            )
            session.add(db_record)
            await session.commit()
            await session.refresh(db_record)
            event.id = db_record.id

        # Broadcast to all async subscribers (WebSockets, monitors)
        for sub in list(self._subscribers):
            try:
                await sub(event)
            except Exception:
                # Never allow subscriber failure to break the publisher
                pass

        return event

    async def get_events(
        self,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        since_sequence: Optional[int] = None,
        limit: int = 200,
    ) -> List[ActivityEvent]:
        async with AsyncSessionLocal() as session:
            query = select(ActivityEventRecord)
            if task_id:
                query = query.where(ActivityEventRecord.task_id == task_id)
            if project_id:
                query = query.where(ActivityEventRecord.project_id == project_id)
            if since_sequence is not None:
                query = query.where(ActivityEventRecord.sequence_number > since_sequence)

            query = query.order_by(ActivityEventRecord.sequence_number.asc()).limit(limit)
            result = await session.execute(query)
            records = result.scalars().all()

            return [
                ActivityEvent(
                    id=rec.id,
                    sequence_number=rec.sequence_number,
                    task_id=rec.task_id,
                    project_id=rec.project_id,
                    event_type=rec.event_type,
                    severity=rec.severity,
                    message=rec.message,
                    payload=rec.payload_json or {},
                    timestamp=rec.timestamp,
                )
                for rec in records
            ]


# Global EventBus singleton
event_bus = EventBus()
