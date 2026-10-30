from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    description: Optional[str] = None
    is_new: bool = False  # If True, create folder and initialize git


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    project_metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionCreate(BaseModel):
    project_id: str
    title: str = Field(..., min_length=1)


class SessionResponse(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    created_at: datetime


class TaskCreate(BaseModel):
    project_id: str
    session_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    connector_name: Optional[str] = None
    max_repair_attempts: Optional[int] = 4


class TaskStepResponse(BaseModel):
    id: str
    step_index: int
    step_type: str
    title: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class ProposedChangeResponse(BaseModel):
    id: str
    file_path: str
    operation: str
    proposed_content: Optional[str] = None
    patch_diff: Optional[str] = None
    explanation: Optional[str] = None
    status: str
    created_at: datetime


class ExecutionResponse(BaseModel):
    id: str
    command: str
    working_dir: str
    exit_code: Optional[int]
    stdout: Optional[str]
    stderr: Optional[str]
    duration_ms: int
    status: str
    created_at: datetime


class TestResultResponse(BaseModel):
    id: str
    test_command: str
    passed: bool
    total_tests: int
    failed_tests: int
    error_details: Optional[str]
    created_at: datetime


class CheckpointResponse(BaseModel):
    id: str
    git_ref: str
    description: str
    files_affected: List[str] = Field(default_factory=list)
    created_at: datetime


class ApprovalResponse(BaseModel):
    id: str
    task_id: str
    action_type: str
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    status: str
    decision_reason: Optional[str] = None
    requested_at: datetime
    decided_at: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: str
    project_id: str
    session_id: Optional[str] = None
    title: str
    description: str
    state: str
    current_step_index: int
    repair_attempts: int
    max_repair_attempts: int
    error_message: Optional[str] = None
    result_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskDetailResponse(TaskResponse):
    steps: List[TaskStepResponse] = Field(default_factory=list)
    proposed_changes: List[ProposedChangeResponse] = Field(default_factory=list)
    executions: List[ExecutionResponse] = Field(default_factory=list)
    test_results: List[TestResultResponse] = Field(default_factory=list)
    approvals: List[ApprovalResponse] = Field(default_factory=list)
    checkpoints: List[CheckpointResponse] = Field(default_factory=list)


class AIConnectorConfigResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: Optional[str] = None
    model_id: Optional[str] = None
    is_default: bool
    enabled: bool
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class AIConnectorConfigCreate(BaseModel):
    name: str
    provider_type: str
    base_url: Optional[str] = None
    model_id: Optional[str] = None
    api_key: Optional[str] = None
    is_default: bool = False
    enabled: bool = True
    config_json: Dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None


class BrowserHandoffSubmitRequest(BaseModel):
    request_id: str
    response_text: str


class RollbackRequest(BaseModel):
    checkpoint_ref: str

