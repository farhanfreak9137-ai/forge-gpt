import asyncio
import json
import logging
from typing import Dict, Any, Optional
from app.ai.adapters.base import AIConnectorBase
from app.ai.protocol.protocol import AIResponseEnvelope
from app.browser.manager.browser_manager import browser_manager

logger = logging.getLogger("forgeagent.ai.browser_automation")


class BrowserAutomationAdapter(AIConnectorBase):
    """Playwright-based adapter for provider-permitted chatbot interfaces."""

    def __init__(self, name: str = "browser_automation", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.target_url = self.config.get("target_url", "http://127.0.0.1:8000/mock-chatbot")
        self.timeout_ms = int(self.config.get("timeout_ms", 30000))
        self.is_permitted = self.config.get("is_permitted", True)  # Safety gate per specification

    async def initialize(self) -> bool:
        self.is_initialized = True
        return True

    async def check_availability(self) -> bool:
        return self.is_permitted

    async def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "browser_automation",
            "target_url": self.target_url,
            "permitted": self.is_permitted,
            "browser": "chromium",
            "streaming_detection": True,
        }

    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        if not self.is_permitted:
            raise PermissionError("Browser automation adapter is disabled because automated interaction is not confirmed permitted.")

        page = await browser_manager.new_page()
        state = "PREPARED"

        try:
            logger.info(f"Navigating to {self.target_url} for request {request_id}")
            state = "SUBMITTING"
            await page.goto(self.target_url, timeout=self.timeout_ms)

            # Wait for input elements
            await page.wait_for_selector("#prompt-input", timeout=self.timeout_ms)
            await page.wait_for_selector("#send-button", timeout=self.timeout_ms)

            # Fill prompt including metadata
            full_prompt = f"task-{task_id} req-{request_id}\n{prompt}"
            await page.fill("#prompt-input", full_prompt)
            await page.click("#send-button")

            state = "AWAITING_RESPONSE"
            logger.info(f"Prompt submitted. Waiting for chatbot response...")

            # Wait for completion or error
            try:
                # Race condition: either .completed-response appears, or #error-box appears
                done_element = await page.wait_for_selector(
                    ".completed-response, #error-box",
                    timeout=self.timeout_ms,
                )
            except Exception as e:
                state = "UNCERTAIN"
                raise TimeoutError(f"Chatbot failed to respond within {self.timeout_ms}ms: {e}")

            # Check if it was an error box
            is_error = await page.query_selector("#error-box")
            if is_error:
                err_text = await is_error.text_content()
                state = "FAILED"
                raise RuntimeError(f"Chatbot indicated error state: {err_text}")

            state = "CAPTURED"
            raw_text = await done_element.text_content()

            state = "VALIDATING"
            cleaned_text = raw_text.strip()
            parsed_data = json.loads(cleaned_text)
            parsed_data["task_id"] = task_id
            parsed_data["request_id"] = request_id

            envelope = AIResponseEnvelope.model_validate(parsed_data)
            state = "VALIDATED"
            return envelope

        except Exception as e:
            logger.error(f"Browser automation failed at state {state}: {e}")
            raise
        finally:
            await page.close()

