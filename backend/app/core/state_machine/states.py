from enum import Enum
from typing import Set, Dict


class TaskState(str, Enum):
    CREATED = "CREATED"
    SCANNING = "SCANNING"
    PLANNING = "PLANNING"
    WAITING_FOR_AI = "WAITING_FOR_AI"
    PARSING = "PARSING"
    VALIDATING = "VALIDATING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPLYING = "APPLYING"
    TESTING = "TESTING"
    REPAIRING = "REPAIRING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


# Strict allowable transitions map
ALLOWED_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
    TaskState.CREATED: {TaskState.SCANNING, TaskState.PAUSED, TaskState.CANCELLED},
    TaskState.SCANNING: {TaskState.PLANNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.PLANNING: {TaskState.WAITING_FOR_AI, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.WAITING_FOR_AI: {TaskState.PARSING, TaskState.VALIDATING, TaskState.APPLYING, TaskState.FAILED, TaskState.PAUSED, TaskState.CANCELLED},
    TaskState.PARSING: {TaskState.VALIDATING, TaskState.WAITING_FOR_AI, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.VALIDATING: {TaskState.APPLYING, TaskState.WAITING_FOR_APPROVAL, TaskState.WAITING_FOR_AI, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.WAITING_FOR_APPROVAL: {TaskState.APPLYING, TaskState.PLANNING, TaskState.PAUSED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.APPLYING: {TaskState.TESTING, TaskState.VERIFYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.TESTING: {TaskState.VERIFYING, TaskState.REPAIRING, TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.REPAIRING: {TaskState.WAITING_FOR_AI, TaskState.VALIDATING, TaskState.APPLYING, TaskState.TESTING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.REPAIRING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),  # Terminal
    TaskState.PAUSED: {TaskState.SCANNING, TaskState.PLANNING, TaskState.WAITING_FOR_AI, TaskState.APPLYING, TaskState.TESTING, TaskState.CANCELLED},
    TaskState.FAILED: {TaskState.RECOVERY_REQUIRED, TaskState.PLANNING},
    TaskState.CANCELLED: set(),  # Terminal
    TaskState.RECOVERY_REQUIRED: {TaskState.CREATED, TaskState.SCANNING, TaskState.PAUSED, TaskState.FAILED},
}


class StateMachineError(Exception):
    pass


def validate_transition(current_state: TaskState, new_state: TaskState) -> None:
    """Validates state transition; raises StateMachineError if illegal."""
    if current_state == new_state:
        return
    allowed = ALLOWED_TRANSITIONS.get(current_state, set())
    if new_state not in allowed:
        raise StateMachineError(
            f"Illegal state transition from {current_state.value} to {new_state.value}. "
            f"Allowed next states: {[s.value for s in allowed]}"
        )
