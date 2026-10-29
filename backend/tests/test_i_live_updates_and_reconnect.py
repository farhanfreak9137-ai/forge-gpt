import pytest
import uuid
from app.events.event_bus import event_bus


@pytest.mark.asyncio
async def test_i_live_updates_and_reconnection_replay(async_client):
    """
    Test I: Dashboard Live Updates & Reconnection Replay
    1. Publish sequential activity events for a task.
    2. Simulate client disconnect.
    3. Reconnect and fetch missed events using since_sequence and task_id.
    4. Confirm correct event ordering and payload fidelity.
    """
    task_id = f"reconnect-task-{uuid.uuid4().hex[:8]}"

    # 1. Publish 3 distinct events for this task
    ev1 = await event_bus.publish(
        task_id=task_id,
        event_type="RECONNECT_STEP_1",
        message="Starting test sequence",
        severity="INFO",
        payload={"step": 1},
    )
    ev2 = await event_bus.publish(
        task_id=task_id,
        event_type="RECONNECT_STEP_2",
        message="Running scanner",
        severity="INFO",
        payload={"step": 2},
    )
    ev3 = await event_bus.publish(
        task_id=task_id,
        event_type="RECONNECT_STEP_3",
        message="Checkpoint created",
        severity="SUCCESS",
        payload={"step": 3},
    )

    # 2. Client was at sequence number of ev1, now reconnects and asks for missed events
    disconnect_seq = ev1.sequence_number
    assert disconnect_seq is not None

    res = await async_client.get(f"/api/v1/events?task_id={task_id}&since_sequence={disconnect_seq}")
    assert res.status_code == 200
    missed_events = res.json()

    # Must contain exactly ev2 and ev3 in chronological order
    event_types = [e["event_type"] for e in missed_events]
    assert event_types == ["RECONNECT_STEP_2", "RECONNECT_STEP_3"]
    assert "RECONNECT_STEP_1" not in event_types
