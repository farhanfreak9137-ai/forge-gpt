from enum import Enum
from typing import List, Optional, Union, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class ProtocolVersion(str, Enum):
    V1 = "forgeagent.v1"


class ResponseType(str, Enum):
    PLAN = "plan"
    REQUEST_CONTEXT = "request_context"
    PROPOSE_CHANGES = "propose_changes"
    PROPOSE_COMMAND = "propose_command"
    REPORT_ANALYSIS = "report_analysis"
    FINISH = "finish"


class ChangeOperation(str, Enum):
    CREATE = "create"
    REPLACE = "replace"
    PATCH = "patch"
    DELETE = "delete"
    MOVE = "move"


class PlanStep(BaseModel):
    step_number: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    expected_files: List[str] = Field(default_factory=list)
    dependencies: List[int] = Field(default_factory=list)


class PlanPayload(BaseModel):
    summary: str = Field(..., min_length=1)
    steps: List[PlanStep] = Field(..., min_length=1)
    acceptance_criteria: List[str] = Field(..., min_length=1)


class RequestContextPayload(BaseModel):
    requested_paths: List[str] = Field(default_factory=list)
    requested_symbols: List[str] = Field(default_factory=list)
    reason: str = Field(..., min_length=1)
    scope_limits: Optional[int] = Field(default=5000, description="Max lines or chars requested")

    @field_validator("requested_paths")
    @classmethod
    def validate_paths(cls, paths: List[str]) -> List[str]:
        for p in paths:
            if ".." in p or p.startswith("/") or p.startswith("\\") or ":" in p:
                raise ValueError(f"Path traversal or absolute path not permitted in context request: {p}")
        return paths


class CodeChangeItem(BaseModel):
    operation: ChangeOperation
    path: str = Field(..., min_length=1)
    expected_hash: Optional[str] = None
    content: Optional[str] = None
    patch: Optional[str] = None
    destination_path: Optional[str] = None
    explanation: str = Field(..., min_length=1)

    @field_validator("path", "destination_path")
    @classmethod
    def validate_relative_path(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.replace("\\", "/").strip()
        if ".." in cleaned.split("/") or cleaned.startswith("/") or ":" in cleaned:
            raise ValueError(f"Path traversal or absolute path forbidden: {v}")
        return cleaned

    @model_validator(mode="after")
    def validate_operation_payload(self) -> "CodeChangeItem":
        if self.operation in (ChangeOperation.CREATE, ChangeOperation.REPLACE):
            if self.content is None:
                raise ValueError(f"Operation {self.operation.value} requires 'content'")
        elif self.operation == ChangeOperation.PATCH:
            if self.patch is None and self.content is None:
                raise ValueError("Operation patch requires 'patch' or updated 'content'")
        elif self.operation == ChangeOperation.MOVE:
            if not self.destination_path:
                raise ValueError("Operation move requires 'destination_path'")
        return self


class ProposeChangesPayload(BaseModel):
    changes: List[CodeChangeItem] = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)


class ProposeCommandPayload(BaseModel):
    command: str = Field(..., min_length=1)
    working_dir: Optional[str] = Field(default=".")
    reason: str = Field(..., min_length=1)
    timeout_seconds: Optional[int] = Field(default=60, ge=1, le=300)


class ReportAnalysisPayload(BaseModel):
    analysis: str = Field(..., min_length=1)
    findings: List[str] = Field(default_factory=list)
    suggested_next_steps: List[str] = Field(default_factory=list)


class FinishPayload(BaseModel):
    summary: str = Field(..., min_length=1)
    verification_passed: bool = Field(default=True)
    notes_for_user: Optional[str] = None


PayloadUnion = Union[
    PlanPayload,
    RequestContextPayload,
    ProposeChangesPayload,
    ProposeCommandPayload,
    ReportAnalysisPayload,
    FinishPayload,
]


class AIResponseEnvelope(BaseModel):
    protocol_version: str = Field(default="forgeagent.v1")
    task_id: str = Field(..., min_length=1)
    request_id: str = Field(..., min_length=1)
    response_type: ResponseType
    payload: Dict[str, Any]

    @field_validator("protocol_version")
    @classmethod
    def validate_protocol_version(cls, v: str) -> str:
        if v != ProtocolVersion.V1.value:
            raise ValueError(f"Unsupported protocol version: {v}. Expected {ProtocolVersion.V1.value}")
        return v

    def parse_typed_payload(self) -> PayloadUnion:
        t = self.response_type
        if t == ResponseType.PLAN:
            return PlanPayload.model_validate(self.payload)
        elif t == ResponseType.REQUEST_CONTEXT:
            return RequestContextPayload.model_validate(self.payload)
        elif t == ResponseType.PROPOSE_CHANGES:
            return ProposeChangesPayload.model_validate(self.payload)
        elif t == ResponseType.PROPOSE_COMMAND:
            return ProposeCommandPayload.model_validate(self.payload)
        elif t == ResponseType.REPORT_ANALYSIS:
            return ReportAnalysisPayload.model_validate(self.payload)
        elif t == ResponseType.FINISH:
            return FinishPayload.model_validate(self.payload)
        raise ValueError(f"Unknown response type: {t}")

