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
    """

    def __init__(self, name: str = "chatgpt_edge", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.website_url = self.config.get("website_url", "https://chatgpt.com")
        self.timeout_ms = int(self.config.get("timeout_ms", 60000))

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
        }

    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        logger.info(f"Opening Microsoft Edge to communicate with ChatGPT at {self.website_url}...")
        page = await browser_manager.get_page()

        try:
            if not page.url or "chatgpt.com" not in page.url:
                await page.goto(self.website_url, timeout=self.timeout_ms)
                await page.wait_for_timeout(3000)

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
            # Modern ChatGPT uses DilResponseRoot / ResponseRoot containers
            assistant_selector = (
                '[class*="DilResponseRoot"], '
                '[class*="ResponseRoot"], '
                '[class*="DilRenderer"], '
                '[data-message-author-role="assistant"]'
            )
            prior_assistant_elements = await page.query_selector_all(assistant_selector)
            prior_count = len(prior_assistant_elements)
            logger.info(f"Prior assistant message count before sending: {prior_count}")

            # 2. Type prompt directly as user wrote it
            full_prompt = prompt
            await page.keyboard.type(full_prompt, delay=10)
            await page.wait_for_timeout(500)

            # 3. Locate and click send button or press Enter
            send_btn = await page.query_selector(
                'button[data-testid="send-button"], button[aria-label="Send prompt"], button[aria-label="Send message"]'
            )
            if send_btn and not (await send_btn.is_disabled()):
                await send_btn.click()
                logger.info("Clicked Send button in Edge.")
            else:
                await page.keyboard.press("Enter")
                logger.info("Pressed Enter to submit prompt in Edge.")

            # 4. Wait for the NEW assistant message container to appear
            logger.info("Waiting for new assistant turn to appear in Edge...")
            new_turn = None
            for _ in range(25):  # wait up to 12.5 seconds for new turn to spawn
                await page.wait_for_timeout(500)
                current_assistant_elements = await page.query_selector_all(assistant_selector)
                if len(current_assistant_elements) > prior_count:
                    new_turn = current_assistant_elements[-1]
                    logger.info(f"New assistant turn detected (turn #{len(current_assistant_elements)}).")
                    break

            if not new_turn:
                current_assistant_elements = await page.query_selector_all(assistant_selector)
                if current_assistant_elements:
                    new_turn = current_assistant_elements[-1]

            # 5. Wait for ChatGPT to FINISH streaming the full response
            logger.info("Waiting for ChatGPT to finish generating response...")
            extracted_text = ""
            last_text_len = 0
            stable_ticks = 0

            for _ in range(60):  # poll up to 60-120 seconds
                await page.wait_for_timeout(1000)

                # Check if stop generating button is active
                stop_btn = await page.query_selector(
                    'button[data-testid="stop-button"], button[aria-label="Stop generating"], button[aria-label="Stop streaming"]'
                )

                # Always extract ONLY from the specific new turn container
                if new_turn:
                    current_text = (await new_turn.inner_text() or "").strip()
                else:
                    current_assistant_elements = await page.query_selector_all(assistant_selector)
                    if current_assistant_elements:
                        current_text = (await current_assistant_elements[-1].inner_text() or "").strip()
                    else:
                        current_text = ""

                # Check for login modal error
                is_login_wall = any(w.lower() in current_text.lower() for w in [
                    "log in to use",
                    "sign up or log in",
                    "get smarter responses, upload files",
                    "email is not valid",
                ])
                if is_login_wall:
                    raise RuntimeError(
                        "You are not logged into ChatGPT in Microsoft Edge. Please log into your ChatGPT account in the Edge browser window on your screen, then send your message again."
                    )

                if current_text and current_text != full_prompt.strip():
                    extracted_text = current_text
                    if len(current_text) == last_text_len and len(current_text) > 0:
                        stable_ticks += 1
                    else:
                        stable_ticks = 0
                        last_text_len = len(current_text)

                # Response is complete when stop button is gone AND text has stabilized
                if not stop_btn and len(extracted_text) > 0 and stable_ticks >= 2:
                    logger.info(f"ChatGPT response streaming completed ({len(extracted_text)} chars).")
                    break

                if current_text and current_text != full_prompt.strip():
                    extracted_text = current_text
                    if len(current_text) == last_text_len and len(current_text) > 0:
                        stable_ticks += 1
                    else:
                        stable_ticks = 0
                        last_text_len = len(current_text)

                # Response is complete when stop button is gone AND text has stabilized
                if not stop_btn and len(extracted_text) > 0 and stable_ticks >= 2:
                    logger.info(f"ChatGPT response streaming completed ({len(extracted_text)} chars).")
                    break

            if not extracted_text:
                raise TimeoutError("ChatGPT did not produce a response within the timeout limit.")

            logger.info(f"Extracted reply from ChatGPT: {extracted_text[:200]}...")

            # Attempt to parse as forgeagent.v1 protocol JSON
            # First check for code block ```json ... ```
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

            # Check if ChatGPT returned a login gate / guest session modal instead of an actual answer
            is_login_wall = any(w.lower() in extracted_text.lower() for w in [
                "log in to use",
                "sign up or log in",
                "get smarter responses, upload files",
                "email is not valid",
            ])
            if is_login_wall:
                raise RuntimeError(
                    "You are not logged into ChatGPT in Microsoft Edge. Please log into your ChatGPT account in the Edge browser window on your screen, then send your message again."
                )

            # If natural language text response, wrap in protocol report
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

