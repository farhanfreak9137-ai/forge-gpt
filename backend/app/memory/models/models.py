from datetime import datetime
from typing import Optional, Any, Dict, List
import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    path = Column(String(1024), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    project_metadata = Column(JSON, default=dict)

    sessions = relationship("ProjectSession", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class ProjectSession(Base):
    __tablename__ = "project_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="sessions")
    tasks = relationship("Task", back_populates="session", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("project_sessions.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    state = Column(String(50), nullable=False, default="CREATED", index=True)
    current_step_index = Column(Integer, default=0, nullable=False)
    repair_attempts = Column(Integer, default=0, nullable=False)
    max_repair_attempts = Column(Integer, default=4, nullable=False)
    error_message = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="tasks")
    session = relationship("ProjectSession", back_populates="tasks")
    steps = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan", order_by="TaskStep.step_index")
    ai_requests = relationship("AIRequestRecord", back_populates="task", cascade="all, delete-orphan")
    proposed_changes = relationship("ProposedChangeRecord", back_populates="task", cascade="all, delete-orphan")
    executions = relationship("ExecutionRecord", back_populates="task", cascade="all, delete-orphan")
    test_results = relationship("TestResultRecord", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("ApprovalRequestRecord", back_populates="task", cascade="all, delete-orphan")
    checkpoints = relationship("CheckpointRecord", back_populates="task", cascade="all, delete-orphan")


class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    step_index = Column(Integer, nullable=False)
    step_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    input_payload = Column(JSON, default=dict)
    output_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="steps")


class AIConnectorConfig(Base):
    __tablename__ = "ai_connectors"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    provider_type = Column(String(50), nullable=False)  # mock, openai, ollama, browser_handoff, browser_automation
    base_url = Column(String(500), nullable=True)
    model_id = Column(String(200), nullable=True)
    api_key_encrypted = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    config_json = Column(JSON, default=dict)


class AIRequestRecord(Base):
    __tablename__ = "ai_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    step_id = Column(String(36), ForeignKey("task_steps.id"), nullable=True)
    connector_name = Column(String(100), nullable=False)
    protocol_version = Column(String(50), default="forgeagent.v1", nullable=False)
    prompt_text = Column(Text, nullable=False)
    raw_response = Column(Text, nullable=True)
    parsed_response_json = Column(JSON, nullable=True)
    status = Column(String(50), default="SUCCESS", nullable=False)
    tokens_used = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="ai_requests")


class ProposedChangeRecord(Base):
    __tablename__ = "proposed_changes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    file_path = Column(String(1024), nullable=False)
    operation = Column(String(50), nullable=False)  # CREATE, REPLACE, PATCH, DELETE, MOVE
    original_hash = Column(String(128), nullable=True)
    proposed_content = Column(Text, nullable=True)
    patch_diff = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, APPLIED, REJECTED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="proposed_changes")


class ExecutionRecord(Base):
    __tablename__ = "executions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    command = Column(Text, nullable=False)
    working_dir = Column(String(1024), nullable=False)
    exit_code = Column(Integer, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    execution_mode = Column(String(50), default="native", nullable=False)
    duration_ms = Column(Integer, default=0)
    status = Column(String(50), default="COMPLETED", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="executions")


class TestResultRecord(Base):
    __tablename__ = "test_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    test_command = Column(Text, nullable=False)
    passed = Column(Boolean, nullable=False)
    total_tests = Column(Integer, default=0)
    failed_tests = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="test_results")


class ApprovalRequestRecord(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    details_json = Column(JSON, default=dict)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED
    decision_reason = Column(Text, nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="approvals")


class CheckpointRecord(Base):
    __tablename__ = "checkpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    git_ref = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    files_affected_json = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="checkpoints")


class ActivityEventRecord(Base):
    __tablename__ = "activity_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sequence_number = Column(Integer, primary_key=False, autoincrement=True, index=True)
    task_id = Column(String(36), nullable=True, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), default="INFO", nullable=False)  # INFO, WARNING, ERROR, SUCCESS
    message = Column(Text, nullable=False)
    payload_json = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
