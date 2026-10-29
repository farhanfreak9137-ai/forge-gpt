import asyncio
import json
import logging
from typing import Dict, Any, Optional
from app.ai.adapters.base import AIConnectorBase
from app.ai.protocol.protocol import AIResponseEnvelope

logger = logging.getLogger("forgeagent.ai.browser_handoff")


class BrowserHandoffAdapter(AIConnectorBase):
    """User-controlled browser handoff workflow for manual copy/paste interactions."""

    def __init__(self, name: str = "browser_handoff", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.response_futures: Dict[str, asyncio.Future] = {}
        self.website_url = self.config.get("website_url", "https://chatgpt.com")

    async def initialize(self) -> bool:
        self.is_initialized = True
        return True

    async def check_availability(self) -> bool:
        return True

    async def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "browser_handoff",
            "manual": True,
            "website_url": self.website_url,
            "description": "User-assisted copy/paste browser interaction with any web chatbot",
        }

    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        # Construct the complete handoff payload for the user to copy
        handoff_prompt = (
            "ForgeAgent Protocol Request (forgeagent.v1)\n"
            f"Task ID: {task_id}\n"
            f"Request ID: {request_id}\n\n"
            "INSTRUCTIONS:\n"
            "You must return ONLY a single valid JSON object following the forgeagent.v1 protocol:\n"
            '{\n  "protocol_version": "forgeagent.v1",\n  "task_id": "' + task_id + '",\n'
            '  "request_id": "' + request_id + '",\n  "response_type": "plan" | "propose_changes" | "finish",\n'
            '  "payload": { ... }\n}\n\n'
            f"TASK REQUEST:\n{prompt}\n"
        )

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.response_futures[request_id] = future
        self.pending_requests[request_id] = {
            "task_id": task_id,
            "request_id": request_id,
            "prepared_prompt": handoff_prompt,
            "website_url": self.website_url,
            "status": "AWAITING_USER_INPUT",
        }

        logger.info(f"Browser handoff prepared for request {request_id}. Awaiting user input.")
        try:
            # Wait for user input via API or dashboard
            envelope = await asyncio.wait_for(future, timeout=600.0)  # 10 min user timeout
            return envelope
        finally:
            self.response_futures.pop(request_id, None)
            self.pending_requests.pop(request_id, None)

    def submit_user_response(self, request_id: str, raw_response_text: str) -> AIResponseEnvelope:
        """Called by the frontend API when user pastes the chatbot response."""
        if request_id not in self.response_futures:
            raise KeyError(f"No pending browser handoff for request_id {request_id}")

        try:
            cleaned = raw_response_text.strip()
            # Strip markdown json blocks if present
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            envelope = AIResponseEnvelope.model_validate(parsed)
            future = self.response_futures[request_id]
            if not future.done():
                future.set_result(envelope)
            return envelope
        except Exception as e:
            logger.error(f"Failed to validate user pasted response: {e}")
            raise ValueError(f"Invalid forgeagent.v1 response: {e}")
