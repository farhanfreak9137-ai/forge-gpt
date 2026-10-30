import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import select, update

from app.config.settings import settings
from app.core.state_machine.states import TaskState, validate_transition
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

    def get_connector(self, name: Optional[str] = None) -> AIConnectorBase:
        conn_name = name or settings.default_ai_connector
        if conn_name not in self.active_connectors:
            logger.warning(f"Connector '{conn_name}' not found, falling back to mock")
            conn_name = "mock"
        return self.active_connectors[conn_name]

    def set_connector(self, name: str, connector: AIConnectorBase) -> None:
        self.active_connectors[name] = connector

    async def _transition_state(self, task_id: str, new_state: TaskState, message: str) -> None:
        async with AsyncSessionLocal() as session:
            db_task = await session.get(Task, task_id)
            if not db_task:
                return

            current_state = TaskState(db_task.state)
            validate_transition(current_state, new_state)

            db_task.state = new_state.value
            db_task.updated_at = datetime.utcnow()
            await session.commit()

        await event_bus.publish(
            event_type="TASK_STATE_CHANGED",
            message=message,
            task_id=task_id,
            project_id=db_task.project_id if db_task else None,
            payload={"old_state": current_state.value, "new_state": new_state.value},
        )

    async def pause_task(self, task_id: str) -> None:
        self.pause_flags[task_id] = True
        await self._transition_state(task_id, TaskState.PAUSED, f"Task {task_id} paused by user.")

    async def resume_task(self, task_id: str) -> None:
        self.pause_flags[task_id] = False
        # Re-launch task execution from last state
        asyncio.create_task(self.run_task(task_id))

    async def cancel_task(self, task_id: str) -> None:
        self.cancel_flags[task_id] = True
        if task_id in self.active_tasks and not self.active_tasks[task_id].done():
            self.active_tasks[task_id].cancel()
        await self._transition_state(task_id, TaskState.CANCELLED, f"Task {task_id} cancelled by user.")

    async def run_task(self, task_id: str, connector_name: Optional[str] = None) -> None:
        """Main execution loop for a task."""
        runner_task = asyncio.current_task()
        if runner_task:
            self.active_tasks[task_id] = runner_task

        async with AsyncSessionLocal() as session:
            task = await session.get(Task, task_id)
            if not task:
                logger.error(f"Task {task_id} not found in database")
                return
            project = await session.get(Project, task.project_id)
            if not project:
                logger.error(f"Project {task.project_id} not found")
                return

        workspace_path = project.path
        connector = self.get_connector(connector_name)
        context_builder = ContextBuilder(workspace_path)
        file_manager = SafeFileManager(workspace_path)
        patcher = PatchApplicator(file_manager)
        git_mgr = GitManager(workspace_path)
        cmd_runner = SafeCommandRunner(workspace_path)
        test_runner = TestRunner(cmd_runner)

        try:
            # 1. SCANNING
            await self._transition_state(task_id, TaskState.SCANNING, "Scanning project workspace")
            manifest_ctx = context_builder.build_context(task.description)
            await git_mgr.init_repo()

            # 2. PLANNING
            await self._transition_state(task_id, TaskState.PLANNING, "Requesting development plan from AI")
            req_id = f"plan-{uuid.uuid4().hex[:8]}"
            plan_prompt = f"Plan development for: {task.description}\nAvailable project scripts: {manifest_ctx.get('scripts')}"
            
            await self._transition_state(task_id, TaskState.WAITING_FOR_AI, "Waiting for AI plan response")
            plan_envelope = await connector.send_request(
                prompt=plan_prompt,
                task_id=task_id,
                request_id=req_id,
                context_data=manifest_ctx,
            )

            # Record AI Request
            async with AsyncSessionLocal() as session:
                session.add(AIRequestRecord(
                    task_id=task_id,
                    connector_name=connector.name,
                    prompt_text=plan_prompt,
                    raw_response=plan_envelope.model_dump_json(),
                    parsed_response_json=plan_envelope.payload,
                    status="SUCCESS",
                ))
                await session.commit()

            # Save plan steps
            if plan_envelope.response_type == ResponseType.PLAN:
                typed_plan: PlanPayload = plan_envelope.parse_typed_payload()
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
            req_id = f"code-{uuid.uuid4().hex[:8]}"
            code_prompt = f"Implement changes for task: {task.description}"
            
            code_envelope = await connector.send_request(
                prompt=code_prompt,
                task_id=task_id,
                request_id=req_id,
                context_data=manifest_ctx,
            )

            # Record AI Request
            async with AsyncSessionLocal() as session:
                session.add(AIRequestRecord(
                    task_id=task_id,
                    connector_name=connector.name,
                    prompt_text=code_prompt,
                    raw_response=code_envelope.model_dump_json(),
                    parsed_response_json=code_envelope.payload,
                    status="SUCCESS",
                ))
                await session.commit()

            # 4. PARSING & VALIDATION
            await self._transition_state(task_id, TaskState.PARSING, "Parsing AI code proposal")
            await self._transition_state(task_id, TaskState.VALIDATING, "Validating proposed changes and permissions")
            
            if code_envelope.response_type == ResponseType.PROPOSE_CHANGES:
                changes_payload: ProposeChangesPayload = code_envelope.parse_typed_payload()
                
                # Check permissions for each change
                needs_approval = False
                approval_reasons = []
                for change in changes_payload.changes:
                    perm, reason = permission_policy.evaluate_file_change(change)
                    if perm == PermissionLevel.EXPLICIT_APPROVAL_REQUIRED:
                        needs_approval = True
                        approval_reasons.append(reason)

                if needs_approval:
                    await self._transition_state(
                        task_id,
                        TaskState.WAITING_FOR_APPROVAL,
                        f"Action requires user approval: {'; '.join(approval_reasons)}",
                    )
                    # Create approval record
                    async with AsyncSessionLocal() as session:
                        session.add(ApprovalRequestRecord(
                            task_id=task_id,
                            action_type="FILE_OPERATION",
                            description="; ".join(approval_reasons),
                            details_json={"changes": [c.model_dump() for c in changes_payload.changes]},
                            status="PENDING",
                        ))
                        await session.commit()
                    return  # Execution halts until user approves via approval endpoint

                # 5. APPLYING
                await self._transition_state(task_id, TaskState.APPLYING, "Applying code changes")
                
                # Create pre-change git checkpoint
                checkpoint_sha = await git_mgr.create_checkpoint(task_id, "Pre-change checkpoint")
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
                    success, msg, diff = patcher.apply_change(change)
                    if not success:
                        raise RuntimeError(f"Failed to apply patch to {change.path}: {msg}")
                    applied_files.append(change.path)
                    
                    # Store change record
                    async with AsyncSessionLocal() as session:
                        session.add(ProposedChangeRecord(
                            task_id=task_id,
                            file_path=change.path,
                            operation=change.operation.value,
                            proposed_content=change.content,
                            patch_diff=diff,
                            explanation=change.explanation,
                            status="APPLIED",
                        ))
                        await session.commit()

                await event_bus.publish(
                    "CHANGES_APPLIED",
                    f"Applied changes to {len(applied_files)} files: {', '.join(applied_files)}",
                    task_id=task_id,
                    project_id=project.id,
                )

                # 6. TESTING & AUTOMATIC REPAIR LOOP
                await self._transition_state(task_id, TaskState.TESTING, "Running verification tests")
                repair_attempts = 0
                max_repairs = settings.max_repair_attempts

                while True:
                    test_res = await test_runner.run_tests()

                    # Record test result
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
                        break

                    # Test failed -> Attempt repair
                    repair_attempts += 1
                    if repair_attempts > max_repairs:
                        raise RuntimeError(f"Exceeded maximum repair attempts ({max_repairs}). Last error: {test_res['failure_details']}")

                    await self._transition_state(
                        task_id,
                        TaskState.REPAIRING,
                        f"Test failed. Initiating repair attempt {repair_attempts}/{max_repairs}",
                    )

                    # Update repair count in database
                    async with AsyncSessionLocal() as session:
                        db_t = await session.get(Task, task_id)
                        if db_t:
                            db_t.repair_attempts = repair_attempts
                            await session.commit()

                    # Build repair request
                    diag = test_res.get("failure_details", {})
                    repair_prompt = (
                        f"Test execution failed with error:\n{diag.get('error_message')}\n"
                        f"Failing file: {diag.get('failing_file')}\n"
                        f"Propose corrected code changes to resolve this failure."
                    )
                    
                    await self._transition_state(task_id, TaskState.WAITING_FOR_AI, f"Waiting for AI repair proposal ({repair_attempts})")
                    repair_envelope = await connector.send_request(
                        prompt=repair_prompt,
                        task_id=task_id,
                        request_id=f"repair-{repair_attempts}-{uuid.uuid4().hex[:6]}",
                        context_data=diag,
                    )

                    if repair_envelope.response_type == ResponseType.PROPOSE_CHANGES:
                        rep_changes: ProposeChangesPayload = repair_envelope.parse_typed_payload()
                        await self._transition_state(task_id, TaskState.APPLYING, f"Applying repair patch {repair_attempts}")
                        for rc in rep_changes.changes:
                            patcher.apply_change(rc)
                    
                    # Loop back to TESTING
                    await self._transition_state(task_id, TaskState.TESTING, f"Re-testing after repair attempt {repair_attempts}")

            # 7. VERIFYING & COMPLETION
            await self._transition_state(task_id, TaskState.VERIFYING, "Finalizing and verifying task completion")
            
            # Create post-task checkpoint
            final_sha = await git_mgr.create_checkpoint(task_id, f"Completed: {task.title}")
            if final_sha:
                async with AsyncSessionLocal() as session:
                    session.add(CheckpointRecord(
                        task_id=task_id,
                        git_ref=final_sha,
                        description="Task completion checkpoint",
                    ))
                    await session.commit()

            # Mark completed
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
                project_id=project.id,
                severity="SUCCESS",
            )

        except asyncio.CancelledError:
            logger.info(f"Task {task_id} execution was cancelled.")
            await self._transition_state(task_id, TaskState.CANCELLED, "Task cancelled")
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
                project_id=project.id if 'project' in locals() and project else None,
                severity="ERROR",
            )


# Global orchestrator singleton
orchestrator = Orchestrator()
