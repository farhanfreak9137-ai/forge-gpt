import asyncio
import logging
import uuid
from datetime import datetime
from app.utils.clock import utcnow
from typing import Dict, Any, Optional, List, Set, Tuple
from pydantic import ValidationError
from sqlalchemy import select, update

from app.config.settings import settings
from app.core.state_machine.states import TaskState, validate_transition, StateMachineError
from app.core.permissions.policy import permission_policy, PermissionLevel
from app.events.event_bus import event_bus
from app.memory.database import AsyncSessionLocal
from app.memory.models.models import (
    Project,
    Task,
    TaskStep,
    AIRequestRecord,
    ProposedChangeRecord,
    ExecutionRecord,
    TestResultRecord,
    ApprovalRequestRecord,
    CheckpointRecord,
)
from app.ai.protocol.protocol import (
    AIResponseEnvelope,
    ResponseType,
    PlanPayload,
    ProposeChangesPayload,
    CodeChangeItem,
    FinishPayload,
)
from app.ai.adapters.base import AIConnectorBase
from app.ai.adapters.mock_adapter import MockAIAdapter
from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.adapters.ollama_adapter import OllamaAdapter
from app.ai.adapters.browser_handoff_adapter import BrowserHandoffAdapter
from app.ai.adapters.browser_automation_adapter import BrowserAutomationAdapter
from app.ai.adapters.chatgpt_edge_adapter import ChatGPTEdgeAdapter
from app.ai.context.context_builder import ContextBuilder
from app.workspace.files.file_manager import SafeFileManager
from app.workspace.patches.patcher import PatchApplicator
from app.workspace.git.git_manager import GitManager
from app.execution.commands.runner import SafeCommandRunner
from app.execution.tests.test_runner import TestRunner

logger = logging.getLogger("forgeagent.orchestrator")


class AIResponseError(Exception):
    """The AI provider kept returning responses that fail protocol validation."""


class TaskPaused(Exception):
    """Raised inside a running task when the user paused it; the task is left in PAUSED."""


def summarize_validation_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'payload'}: {err['msg']}" for err in exc.errors()[:6]
        )
    return str(exc)


class _TaskContext:
    """Per-run collaborators for one task."""

    def __init__(self, task, project, connector, manifest_ctx=None):
        workspace_path = project.path
        self.task = task
        self.project = project
        self.connector = connector
        self.manifest_ctx = manifest_ctx or {}
        self.file_manager = SafeFileManager(workspace_path)
        self.patcher = PatchApplicator(self.file_manager)
        self.git = GitManager(workspace_path)
        self.cmd_runner = SafeCommandRunner(workspace_path)
        self.test_runner = TestRunner(self.cmd_runner)


class Orchestrator:
    """Core orchestration engine managing task lifecycles, execution, and repair loops."""

    def __init__(self):
        self.active_connectors: Dict[str, AIConnectorBase] = {
            "mock": MockAIAdapter("mock"),
            "openai": OpenAIAdapter("openai", {
                "base_url": settings.openai_base_url,
                "api_key": settings.openai_api_key,
                "model_id": settings.openai_model_id,
            }),
            "ollama": OllamaAdapter("ollama", {
                "base_url": settings.ollama_base_url,
                "model_id": settings.ollama_model_id,
            }),
            "browser_handoff": BrowserHandoffAdapter("browser_handoff"),
            "browser_automation": BrowserAutomationAdapter("browser_automation"),
            "chatgpt_edge": ChatGPTEdgeAdapter("chatgpt_edge"),
        }
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.pause_flags: Dict[str, bool] = {}
        self.cancel_flags: Dict[str, bool] = {}
        self.task_connectors: Dict[str, str] = {}

    def get_connector(self, name: Optional[str] = None) -> AIConnectorBase:
        conn_name = name or settings.default_ai_connector
        if conn_name not in self.active_connectors:
            logger.warning(f"Connector '{conn_name}' not found, falling back to mock")
            conn_name = "mock"
        return self.active_connectors[conn_name]

    def set_connector(self, name: str, connector: AIConnectorBase) -> None:
        self.active_connectors[name] = connector

    async def _get_task_state(self, task_id: str) -> Optional[TaskState]:
        async with AsyncSessionLocal() as session:
            db_task = await session.get(Task, task_id)
            return TaskState(db_task.state) if db_task else None

    async def _transition_state(self, task_id: str, new_state: TaskState, message: str) -> None:
        # Cooperative pause: a running task stops at its next transition instead of racing the PAUSED state.
        if self.pause_flags.get(task_id) and new_state not in (TaskState.PAUSED, TaskState.CANCELLED, TaskState.FAILED):
            raise TaskPaused(task_id)

        async with AsyncSessionLocal() as session:
            db_task = await session.get(Task, task_id)
            if not db_task:
                return

            current_state = TaskState(db_task.state)
            validate_transition(current_state, new_state)

            project_id = db_task.project_id
            db_task.state = new_state.value
            db_task.updated_at = utcnow()
            await session.commit()

        await event_bus.publish(
            event_type="TASK_STATE_CHANGED",
            message=message,
            task_id=task_id,
            project_id=project_id,
            payload={"old_state": current_state.value, "new_state": new_state.value},
        )

    async def pause_task(self, task_id: str) -> None:
        self.pause_flags[task_id] = True
        await self._transition_state(task_id, TaskState.PAUSED, f"Task {task_id} paused by user.")

    async def resume_task(self, task_id: str) -> None:
        """Resume a paused task, or continue an approved task that was waiting for approval."""
        self.pause_flags[task_id] = False
        state = await self._get_task_state(task_id)
        if state == TaskState.WAITING_FOR_APPROVAL:
            asyncio.create_task(self.run_approved_changes(task_id))
        else:
            # Paused tasks restart from SCANNING (PAUSED -> SCANNING is a legal transition)
            asyncio.create_task(self.run_task(task_id, connector_name=self.task_connectors.get(task_id)))

    async def reject_task(self, task_id: str, reason: Optional[str] = None) -> None:
        """A rejected approval ends the task instead of leaving it waiting forever."""
        state = await self._get_task_state(task_id)
        if state != TaskState.WAITING_FOR_APPROVAL:
            return
        async with AsyncSessionLocal() as session:
            db_task = await session.get(Task, task_id)
            if db_task:
                db_task.error_message = f"Rejected by user: {reason or 'no reason given'}"
                await session.commit()
        await self._transition_state(task_id, TaskState.CANCELLED, f"Task {task_id} cancelled: approval rejected.")

    async def cancel_task(self, task_id: str) -> None:
        self.cancel_flags[task_id] = True
        if task_id in self.active_tasks and not self.active_tasks[task_id].done():
            self.active_tasks[task_id].cancel()
        await self._transition_state(task_id, TaskState.CANCELLED, f"Task {task_id} cancelled by user.")

    # ------------------------------------------------------------------ AI requests

    async def _request_validated(
        self,
        ctx: _TaskContext,
        *,
        prompt: str,
        request_prefix: str,
        expected: Optional[Set[ResponseType]] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ):
        """Ask the AI and validate the typed payload; on a malformed reply, show the AI its
        validation errors and ask again (bounded by settings.response_retry_limit)."""
        task_id = ctx.task.id
        attempts = settings.response_retry_limit + 1
        current_prompt = prompt
        last_error = "no response"

        for attempt in range(1, attempts + 1):
            envelope = await ctx.connector.send_request(
                prompt=current_prompt,
                task_id=task_id,
                request_id=f"{request_prefix}-{uuid.uuid4().hex[:8]}",
                context_data=context_data if context_data is not None else ctx.manifest_ctx,
            )
            typed = None
            try:
                if expected is not None and envelope.response_type not in expected:
                    wanted = ", ".join(sorted(t.value for t in expected))
                    raise ValueError(f"expected response_type in [{wanted}] but got '{envelope.response_type.value}'")
                typed = envelope.parse_typed_payload()
                error = None
            except (ValidationError, ValueError) as exc:
                error = summarize_validation_error(exc)

            async with AsyncSessionLocal() as session:
                session.add(AIRequestRecord(
                    task_id=task_id,
                    connector_name=ctx.connector.name,
                    prompt_text=current_prompt,
                    raw_response=envelope.model_dump_json(),
                    parsed_response_json=envelope.payload,
                    status="SUCCESS" if error is None else "INVALID",
                ))
                await session.commit()

            if error is None:
                return envelope, typed

            last_error = error
            logger.warning(f"Task {task_id}: invalid AI response (attempt {attempt}/{attempts}): {error}")
            await event_bus.publish(
                "AI_RESPONSE_INVALID",
                f"AI response failed validation (attempt {attempt}/{attempts}): {error}",
                task_id=task_id,
                project_id=ctx.project.id,
                severity="WARNING",
            )
            current_prompt = (
                f"{prompt}\n\nYour previous response was rejected by protocol validation: {error}\n"
                "Reply again with a complete, valid forgeagent.v1 response. Every change needs an "
                "operation, a relative string path, an explanation, and content when creating or replacing."
            )

        raise AIResponseError(f"AI returned an invalid response {attempts} times in a row. Last error: {last_error}")

    # ------------------------------------------------------------------ task execution

    async def _load_context(self, task_id: str, connector_name: Optional[str]) -> Optional[_TaskContext]:
        async with AsyncSessionLocal() as session:
            task = await session.get(Task, task_id)
            if not task:
                logger.error(f"Task {task_id} not found in database")
                return None
            project = await session.get(Project, task.project_id)
            if not project:
                logger.error(f"Project {task.project_id} not found")
                return None
        if connector_name:
            self.task_connectors[task_id] = connector_name
        return _TaskContext(task, project, self.get_connector(self.task_connectors.get(task_id)))

    async def _guarded(self, task_id: str, project_id: Optional[str], body) -> None:
        """Run a task body, mapping pause, cancel and failure onto task state."""
        runner_task = asyncio.current_task()
        if runner_task:
            self.active_tasks[task_id] = runner_task
        try:
            await body
        except TaskPaused:
            logger.info(f"Task {task_id} paused; stopping execution.")
        except asyncio.CancelledError:
            logger.info(f"Task {task_id} execution was cancelled.")
            try:
                await self._transition_state(task_id, TaskState.CANCELLED, "Task cancelled")
            except StateMachineError:
                pass
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            async with AsyncSessionLocal() as session:
                db_t = await session.get(Task, task_id)
                if db_t:
                    db_t.state = TaskState.FAILED.value
                    db_t.error_message = str(e)
                    await session.commit()
            await event_bus.publish(
                "TASK_FAILED",
                f"Task failed: {str(e)}",
                task_id=task_id,
                project_id=project_id,
                severity="ERROR",
            )
        finally:
            self.active_tasks.pop(task_id, None)

    async def run_task(self, task_id: str, connector_name: Optional[str] = None) -> None:
        """Main execution loop for a task."""
        ctx = await self._load_context(task_id, connector_name)
        if ctx is None:
            return
        await self._guarded(task_id, ctx.project.id, self._run_task_body(ctx))

    async def _run_task_body(self, ctx: _TaskContext) -> None:
        task, project, task_id = ctx.task, ctx.project, ctx.task.id

        # 1. SCANNING
        await self._transition_state(task_id, TaskState.SCANNING, "Scanning project workspace")
        ctx.manifest_ctx = ContextBuilder(project.path).build_context(task.description)
        await ctx.git.init_repo()

        # 2. PLANNING
        await self._transition_state(task_id, TaskState.PLANNING, "Requesting development plan from AI")
        plan_prompt = (
            f"Plan development for: {task.description}\n"
            f"Available project scripts: {ctx.manifest_ctx.get('scripts')}"
        )
        await self._transition_state(task_id, TaskState.WAITING_FOR_AI, "Waiting for AI plan response")
        plan_envelope, typed_plan = await self._request_validated(ctx, prompt=plan_prompt, request_prefix="plan")

        if plan_envelope.response_type == ResponseType.PLAN:
            async with AsyncSessionLocal() as session:
                for s in typed_plan.steps:
                    session.add(TaskStep(
                        task_id=task_id,
                        step_index=s.step_number,
                        step_type="PLAN_STEP",
                        title=s.title,
                        description=s.description,
                        status="PENDING",
                    ))
                await session.commit()
            await event_bus.publish(
                "PLAN_CREATED",
                f"Plan created with {len(typed_plan.steps)} steps",
                task_id=task_id,
                project_id=project.id,
                payload={"summary": typed_plan.summary, "steps": [s.model_dump() for s in typed_plan.steps]},
            )

        # 3. CODE GENERATION / PROPOSE CHANGES
        await self._transition_state(task_id, TaskState.WAITING_FOR_AI, "Requesting code implementation from AI")
        code_envelope, changes_payload = await self._request_validated(
            ctx,
            prompt=f"Implement changes for task: {task.description}",
            request_prefix="code",
            expected={ResponseType.PROPOSE_CHANGES, ResponseType.FINISH},
        )

        # 4. PARSING & VALIDATION
        await self._transition_state(task_id, TaskState.PARSING, "Parsing AI code proposal")
        await self._transition_state(task_id, TaskState.VALIDATING, "Validating proposed changes and permissions")

        if code_envelope.response_type == ResponseType.PROPOSE_CHANGES:
            reasons = []
            for change in changes_payload.changes:
                perm, reason = permission_policy.evaluate_file_change(change)
                if perm == PermissionLevel.EXPLICIT_APPROVAL_REQUIRED:
                    reasons.append(reason)

            if reasons:
                await self._transition_state(
                    task_id,
                    TaskState.WAITING_FOR_APPROVAL,
                    f"Action requires user approval: {'; '.join(reasons)}",
                )
                async with AsyncSessionLocal() as session:
                    session.add(ApprovalRequestRecord(
                        task_id=task_id,
                        action_type="FILE_OPERATION",
                        description="; ".join(reasons),
                        details_json={"changes": [c.model_dump() for c in changes_payload.changes]},
                        status="PENDING",
                    ))
                    await session.commit()
                return  # Execution halts until the user decides via the approval endpoint

            await self._apply_and_verify(ctx, changes_payload)

        await self._finalize(ctx)

    async def run_approved_changes(self, task_id: str) -> None:
        """Continue a task whose pending file operations the user has approved."""
        ctx = await self._load_context(task_id, None)
        if ctx is None:
            return
        await self._guarded(task_id, ctx.project.id, self._approved_body(ctx))

    async def _approved_body(self, ctx: _TaskContext) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ApprovalRequestRecord)
                .where(ApprovalRequestRecord.task_id == ctx.task.id, ApprovalRequestRecord.status == "APPROVED")
                .order_by(ApprovalRequestRecord.decided_at.desc())
            )
            approval = result.scalars().first()
        if approval is None or not (approval.details_json or {}).get("changes"):
            raise RuntimeError("No approved change set found for this task; nothing to apply.")

        changes = ProposeChangesPayload(
            summary=approval.description or "Approved changes",
            changes=[CodeChangeItem.model_validate(c) for c in approval.details_json["changes"]],
        )
        await self._apply_and_verify(ctx, changes)
        await self._finalize(ctx)

    async def _record_change(self, task_id: str, change: CodeChangeItem, diff: Optional[str], status: str) -> None:
        async with AsyncSessionLocal() as session:
            session.add(ProposedChangeRecord(
                task_id=task_id,
                file_path=change.path,
                operation=change.operation.value,
                proposed_content=change.content,
                patch_diff=diff,
                explanation=change.explanation,
                status=status,
            ))
            await session.commit()

    async def _apply_and_verify(self, ctx: _TaskContext, changes_payload: ProposeChangesPayload) -> None:
        task_id = ctx.task.id

        # 5. APPLYING
        await self._transition_state(task_id, TaskState.APPLYING, "Applying code changes")

        checkpoint_sha = await ctx.git.create_checkpoint(task_id, "Pre-change checkpoint")
        if checkpoint_sha:
            async with AsyncSessionLocal() as session:
                session.add(CheckpointRecord(
                    task_id=task_id,
                    git_ref=checkpoint_sha,
                    description="Pre-change checkpoint",
                    files_affected_json=[c.path for c in changes_payload.changes],
                ))
                await session.commit()

        applied_files = []
        for change in changes_payload.changes:
            success, msg, diff = ctx.patcher.apply_change(change)
            if not success:
                await self._record_change(task_id, change, diff, "FAILED")
                raise RuntimeError(f"Failed to apply patch to {change.path}: {msg}")
            applied_files.append(change.path)
            await self._record_change(task_id, change, diff, "APPLIED")

        await event_bus.publish(
            "CHANGES_APPLIED",
            f"Applied changes to {len(applied_files)} files: {', '.join(applied_files)}",
            task_id=task_id,
            project_id=ctx.project.id,
        )

        # 6. TESTING & AUTOMATIC REPAIR LOOP
        await self._transition_state(task_id, TaskState.TESTING, "Running verification tests")
        repair_attempts = 0
        max_repairs = ctx.task.max_repair_attempts or settings.max_repair_attempts
        apply_error: Optional[str] = None

        while True:
            test_res = await ctx.test_runner.run_tests()

            async with AsyncSessionLocal() as session:
                session.add(TestResultRecord(
                    task_id=task_id,
                    test_command=test_res["test_command"],
                    passed=test_res["passed"],
                    total_tests=1,
                    failed_tests=0 if test_res["passed"] else 1,
                    error_details=test_res["stderr"] or test_res["stdout"],
                ))
                await session.commit()

            if test_res["passed"]:
                logger.info("Verification tests passed successfully.")
                return

            repair_attempts += 1
            if repair_attempts > max_repairs:
                raise RuntimeError(
                    f"Exceeded maximum repair attempts ({max_repairs}). Last error: {test_res['failure_details']}"
                )

            await self._transition_state(
                task_id,
                TaskState.REPAIRING,
                f"Test failed. Initiating repair attempt {repair_attempts}/{max_repairs}",
            )

            async with AsyncSessionLocal() as session:
                db_t = await session.get(Task, task_id)
                if db_t:
                    db_t.repair_attempts = repair_attempts
                    await session.commit()

            diag = test_res.get("failure_details") or {}
            repair_prompt = (
                f"Test execution failed with error:\n{diag.get('error_message')}\n"
                f"Failing file: {diag.get('failing_file')}\n"
                f"Propose corrected code changes to resolve this failure."
            )
            if apply_error:
                repair_prompt += f"\nYour previous patch could not be applied: {apply_error}"

            await self._transition_state(task_id, TaskState.WAITING_FOR_AI, f"Waiting for AI repair proposal ({repair_attempts})")
            _, rep_changes = await self._request_validated(
                ctx,
                prompt=repair_prompt,
                request_prefix=f"repair-{repair_attempts}",
                expected={ResponseType.PROPOSE_CHANGES},
                context_data=diag,
            )

            await self._transition_state(task_id, TaskState.APPLYING, f"Applying repair patch {repair_attempts}")
            apply_error = None
            for rc in rep_changes.changes:
                perm, reason = permission_policy.evaluate_file_change(rc)
                if perm == PermissionLevel.EXPLICIT_APPROVAL_REQUIRED:
                    # Repairs must not slip a sensitive change past the approval gate
                    apply_error = f"{rc.path} was not applied: {reason}"
                    await self._record_change(task_id, rc, None, "REJECTED")
                    continue
                ok, msg, diff = ctx.patcher.apply_change(rc)
                if not ok:
                    apply_error = msg
                await self._record_change(task_id, rc, diff, "APPLIED" if ok else "FAILED")

            await self._transition_state(task_id, TaskState.TESTING, f"Re-testing after repair attempt {repair_attempts}")

    async def _finalize(self, ctx: _TaskContext) -> None:
        task_id = ctx.task.id

        # 7. VERIFYING & COMPLETION
        await self._transition_state(task_id, TaskState.VERIFYING, "Finalizing and verifying task completion")

        final_sha = await ctx.git.create_checkpoint(task_id, f"Completed: {ctx.task.title}")
        if final_sha:
            async with AsyncSessionLocal() as session:
                session.add(CheckpointRecord(
                    task_id=task_id,
                    git_ref=final_sha,
                    description="Task completion checkpoint",
                ))
                await session.commit()

        async with AsyncSessionLocal() as session:
            db_t = await session.get(Task, task_id)
            if db_t:
                db_t.state = TaskState.COMPLETED.value
                db_t.result_summary = "All code changes applied and verified by tests."
                await session.commit()

        await event_bus.publish(
            "TASK_COMPLETED",
            f"Task {task_id} completed successfully.",
            task_id=task_id,
            project_id=ctx.project.id,
            severity="SUCCESS",
        )


# Global orchestrator singleton
orchestrator = Orchestrator()
