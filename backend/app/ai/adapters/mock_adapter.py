import json
import logging
from typing import Dict, Any, Optional, List
from app.ai.adapters.base import AIConnectorBase
from app.ai.protocol.protocol import (
    AIResponseEnvelope,
    ResponseType,
    ChangeOperation,
    PlanPayload,
    PlanStep,
    CodeChangeItem,
    ProposeChangesPayload,
    FinishPayload,
)

logger = logging.getLogger("forgeagent.ai.mock")


class MockAIAdapter(AIConnectorBase):
    """Deterministic scriptable mock AI adapter for testing and offline development."""

    def __init__(self, name: str = "mock", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.queued_responses: List[Any] = []
        self.call_history: List[Dict[str, Any]] = []
        self.is_initialized = True

    async def initialize(self) -> bool:
        self.is_initialized = True
        return True

    def queue_response(self, response: Any) -> None:
        """Queue a scripted response (dict, AIResponseEnvelope, or raw string)."""
        self.queued_responses.append(response)

    def clear_queue(self) -> None:
        self.queued_responses.clear()

    async def check_availability(self) -> bool:
        return True

    async def get_capabilities(self) -> Dict[str, Any]:
        return {
            "streaming": False,
            "offline": True,
            "deterministic": True,
            "model": "forge-mock-v1",
        }

    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        self.call_history.append({
            "task_id": task_id,
            "request_id": request_id,
            "prompt": prompt,
            "system_instruction": system_instruction,
            "context_data": context_data,
        })

        # 1. If user queued a scripted response, use it
        if self.queued_responses:
            next_resp = self.queued_responses.pop(0)
            if isinstance(next_resp, AIResponseEnvelope):
                return next_resp
            if isinstance(next_resp, dict):
                next_resp["task_id"] = task_id
                next_resp["request_id"] = request_id
                return AIResponseEnvelope.model_validate(next_resp)
            if isinstance(next_resp, str):
                parsed = json.loads(next_resp)
                parsed["task_id"] = task_id
                parsed["request_id"] = request_id
                return AIResponseEnvelope.model_validate(parsed)

        # 2. Intelligent deterministic fallback based on prompt content
        lower_prompt = prompt.lower()

        # Repair / Debugging prompt
        if "repair" in lower_prompt or "error" in lower_prompt or "failure" in lower_prompt or "fix" in lower_prompt:
            logger.info(f"Mock AI generating repair changes for task {task_id}")
            failing_path = (context_data.get("failing_file") if context_data else None) or "calc.py"
            return AIResponseEnvelope(
                protocol_version="forgeagent.v1",
                task_id=task_id,
                request_id=request_id,
                response_type=ResponseType.PROPOSE_CHANGES,
                payload={
                    "summary": "Fix syntax or assertion error identified during test execution",
                    "changes": [
                        {
                            "operation": ChangeOperation.REPLACE.value,
                            "path": failing_path,
                            "content": "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n",
                            "explanation": "Corrected function implementation to satisfy test assertion",
                        }
                    ],
                },
            )

        # Planning phase
        if "plan" in lower_prompt or "create a plan" in lower_prompt or "step" in lower_prompt:
            logger.info(f"Mock AI generating plan for task {task_id}")
            return AIResponseEnvelope(
                protocol_version="forgeagent.v1",
                task_id=task_id,
                request_id=request_id,
                response_type=ResponseType.PLAN,
                payload={
                    "summary": "Plan for task execution",
                    "steps": [
                        {
                            "step_number": 1,
                            "title": "Create project implementation files",
                            "description": "Generate core logic and source files",
                            "expected_files": ["calc.py"],
                            "dependencies": [],
                        },
                        {
                            "step_number": 2,
                            "title": "Create test suite",
                            "description": "Generate test cases to verify implementation",
                            "expected_files": ["test_calc.py"],
                            "dependencies": [1],
                        },
                    ],
                    "acceptance_criteria": [
                        "All source files created",
                        "Tests run and pass with exit code 0",
                    ],
                },
            )

        # Propose changes / code generation
        if "generate" in lower_prompt or "code" in lower_prompt or "implement" in lower_prompt or "feature" in lower_prompt:
            logger.info(f"Mock AI proposing code changes for task {task_id}")
            return AIResponseEnvelope(
                protocol_version="forgeagent.v1",
                task_id=task_id,
                request_id=request_id,
                response_type=ResponseType.PROPOSE_CHANGES,
                payload={
                    "summary": "Generate calculator implementation and unit test",
                    "changes": [
                        {
                            "operation": ChangeOperation.CREATE.value,
                            "path": "calc.py",
                            "content": "def add(a, b):\n    return a + b\n",
                            "explanation": "Add addition function",
                        },
                        {
                            "operation": ChangeOperation.CREATE.value,
                            "path": "test_calc.py",
                            "content": "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                            "explanation": "Add test for addition function",
                        },
                    ],
                },
            )

        # Default completion finish
        logger.info(f"Mock AI returning finish for task {task_id}")
        return AIResponseEnvelope(
            protocol_version="forgeagent.v1",
            task_id=task_id,
            request_id=request_id,
            response_type=ResponseType.FINISH,
            payload={
                "summary": "All requested changes and verification steps completed successfully.",
                "verification_passed": True,
                "notes_for_user": "Project ready for review.",
            },
        )
