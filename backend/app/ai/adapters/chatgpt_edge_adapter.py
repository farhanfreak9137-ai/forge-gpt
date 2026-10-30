import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional
from app.ai.adapters.base import AIConnectorBase
from app.ai.protocol.protocol import (
    AIResponseEnvelope,
    ResponseType,
    ReportAnalysisPayload,
    FinishPayload,
)
from app.browser.manager.browser_manager import browser_manager

logger = logging.getLogger("forgeagent.ai.chatgpt_edge")


class ChatGPTEdgeAdapter(AIConnectorBase):
    """
    Playwright-based Microsoft Edge adapter for interacting with ChatGPT (chatgpt.com).
    Uses persistent browser profile and Microsoft Edge channel to submit prompts and extract replies.
    Automatically recovers from closed/crashed browser contexts.
    """

    def __init__(self, name: str = "chatgpt_edge", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.website_url = self.config.get("website_url", "https://chatgpt.com")
        self.timeout_ms = int(self.config.get("timeout_ms", 60000))
        self.response_timeout_ms = int(self.config.get("response_timeout_ms", 600000))

    async def initialize(self) -> bool:
        self.is_initialized = True
        return True

    async def check_availability(self) -> bool:
        edge_path = browser_manager.find_edge_path()
        return edge_path is not None

    async def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "chatgpt_edge",
            "browser": "Microsoft Edge (msedge)",
            "website_url": self.website_url,
            "streaming_detection": True,
            "interactive": True,
            "response_timeout_ms": self.response_timeout_ms,
        }

    async def _wait_for_assistant_response(self, page, assistant_selector: str, prior_count: int, prompt: str) -> str:
        deadline = asyncio.get_running_loop().time() + self.response_timeout_ms / 1000
        extracted_text = ""
        last_text = ""
        stable_ticks = 0
        new_turn_detected = False

        logger.info(
            "Waiting up to %.0f seconds for ChatGPT to respond and finish streaming...",
            self.response_timeout_ms / 1000,
        )

        while asyncio.get_running_loop().time() < deadline:
            assistant_elements = await page.query_selector_all(assistant_selector)
            if len(assistant_elements) > prior_count:
                new_turn = assistant_elements[-1]
                if not new_turn_detected:
                    logger.info("New ChatGPT assistant turn detected.")
                    new_turn_detected = True

                current_text = (await new_turn.inner_text() or "").strip()
                is_login_wall = any(w in current_text.lower() for w in (
                    "log in to use",
                    "sign up or log in",
                    "get smarter responses, upload files",
                    "email is not valid",
                ))
                if is_login_wall:
                    raise RuntimeError(
                        "You are not logged into ChatGPT in Microsoft Edge. "
                        "Please log into your ChatGPT account in the Edge browser window, then send your message again."
                    )

                if current_text and current_text != prompt.strip():
                    extracted_text = current_text
                    if current_text == last_text:
                        stable_ticks += 1
                    else:
                        last_text = current_text
                        stable_ticks = 0

                    stop_button = await page.query_selector(
                        'button[data-testid="stop-button"], '
                        'button[aria-label="Stop generating"], '
                        'button[aria-label="Stop streaming"]'
                    )
                    if not stop_button and stable_ticks >= 2:
                        logger.info("ChatGPT response streaming completed (%s chars).", len(extracted_text))
                        return extracted_text
            else:
                extracted_text = ""
                last_text = ""
                stable_ticks = 0

            remaining_ms = int((deadline - asyncio.get_running_loop().time()) * 1000)
            if remaining_ms > 0:
                await page.wait_for_timeout(min(1000, remaining_ms))

        if extracted_text:
            raise TimeoutError(
                f"ChatGPT response did not finish within {self.response_timeout_ms / 1000:.0f} seconds."
            )
        raise TimeoutError(
            f"ChatGPT did not produce a new assistant response within {self.response_timeout_ms / 1000:.0f} seconds."
        )

    async def _get_page_with_recovery(self):
        """Get a browser page, forcing a full browser restart if the first attempt fails."""
        try:
            return await browser_manager.get_page()
        except Exception as exc:
            logger.warning(f"Initial get_page() failed ({exc}). Forcing full browser reset and retry.")
            await browser_manager.close()
            return await browser_manager.get_page()

    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        logger.info(f"Opening Microsoft Edge to communicate with ChatGPT at {self.website_url}...")
        
        # Always use recovery-aware page acquisition
        page = await self._get_page_with_recovery()
        browser_manager.focus_edge_window()
        await page.bring_to_front()

        try:
            if not page.url or "chatgpt.com" not in page.url:
                await page.goto(self.website_url, timeout=self.timeout_ms)
                await page.wait_for_timeout(3000)

            browser_manager.focus_edge_window()
            await page.bring_to_front()

            # Locate prompt input element (supports modern ChatGPT ProseMirror contenteditable div and classic textarea)
            ta_selector = (
                'div.ProseMirror, '
                'div[contenteditable="true"], '
                'div[role="textbox"], '
                '#prompt-textarea, '
                'textarea[name="prompt"], '
                'textarea'
            )
            ta = await page.wait_for_selector(ta_selector, timeout=20000)
            if not ta:
                raise RuntimeError("Could not find prompt input area on ChatGPT page")

            # Click, focus, clear existing text, and type prompt
            await ta.click()
            await ta.focus()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")

            # 1. Count assistant turns BEFORE submitting the new prompt
            assistant_selector = (
                '[class*="DilResponseRoot"], '
                '[class*="ResponseRoot"], '
                '[class*="DilRenderer"], '
                '[data-message-author-role="assistant"]'
            )
            prior_assistant_elements = await page.query_selector_all(assistant_selector)
            prior_count = len(prior_assistant_elements)
            logger.info(f"Prior assistant message count before sending: {prior_count}")

            # 2. Type the user's prompt
            full_prompt = prompt
            await page.keyboard.type(full_prompt, delay=10)
            await page.wait_for_timeout(500)

            # 3. Click Send button or press Enter
            send_btn = await page.query_selector(
                'button[data-testid="send-button"], button[aria-label="Send prompt"], button[aria-label="Send message"]'
            )
            if send_btn and not (await send_btn.is_disabled()):
                await send_btn.click()
                logger.info("Clicked Send button in Edge.")
            else:
                await page.keyboard.press("Enter")
                logger.info("Pressed Enter to submit prompt in Edge.")

            # 4. Wait for a new assistant turn and its complete response.
            extracted_text = await self._wait_for_assistant_response(
                page,
                assistant_selector,
                prior_count,
                full_prompt,
            )

            logger.info(f"Extracted reply from ChatGPT: {extracted_text[:200]}...")

            # Attempt to parse as forgeagent.v1 protocol JSON
            json_candidate = None
            code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", extracted_text, re.DOTALL)
            if code_block_match:
                json_candidate = code_block_match.group(1)
            elif extracted_text.strip().startswith("{") and extracted_text.strip().endswith("}"):
                json_candidate = extracted_text.strip()

            if json_candidate:
                try:
                    parsed = json.loads(json_candidate)
                    parsed["task_id"] = task_id
                    parsed["request_id"] = request_id
                    return AIResponseEnvelope.model_validate(parsed)
                except Exception as e:
                    logger.warning(f"Could not parse JSON payload from ChatGPT: {e}")

            # Check for login wall one final time
            is_login_wall = any(w.lower() in extracted_text.lower() for w in [
                "log in to use",
                "sign up or log in",
                "get smarter responses, upload files",
                "email is not valid",
            ])
            if is_login_wall:
                raise RuntimeError(
                    "You are not logged into ChatGPT in Microsoft Edge. "
                    "Please log into your ChatGPT account in the Edge browser window, then send your message again."
                )

            # Wrap natural language reply in the standard protocol envelope
            clean_reply = re.sub(r"\[ForgeAgent Metadata:[^\]]*\]", "", extracted_text).strip()
            return AIResponseEnvelope(
                protocol_version="forgeagent.v1",
                task_id=task_id,
                request_id=request_id,
                response_type=ResponseType.REPORT_ANALYSIS,
                payload={
                    "analysis": clean_reply or extracted_text,
                    "findings": ["Received live conversational reply from ChatGPT in Microsoft Edge"],
                    "suggested_next_steps": ["Proceed with verified Edge-to-ChatGPT communication"],
                },
            )

        except Exception as e:
            logger.error(f"ChatGPT Edge interaction failed: {e}")
            raise
